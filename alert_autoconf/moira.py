import logging
import re

from datetime import time
from typing import List
from urllib import parse

from redis import Redis

from alert_autoconf.models import Alerts, Contact, Escalation, Subscription, Trigger, Saturation

from moira_client import Moira
from moira_client.models import (
    Subscription as MoiraSubscription,
    Trigger as MoiraTrigger,
)
from moira_client.models.subscription import SubscriptionManager


def trigger_moira_to_model(trigger: MoiraTrigger) -> Trigger:
    trigger_dict = trigger.__dict__

    if "dashboard" in trigger_dict and not trigger_dict["dashboard"]:
        trigger_dict.pop("dashboard")

    keys = Trigger.__fields__.keys()

    _start_hour = trigger_dict.get("_start_hour", None)
    _start_minute = trigger_dict.get("_start_minute", None)
    time_start = (
        time(hour=_start_hour, minute=_start_minute)
        if _start_hour and _start_minute
        else Trigger.__fields__['time_start'].default
    )
    _end_hour = trigger_dict.get("_end_hour", None)
    _end_minute = trigger_dict.get("_end_minute", None)
    time_end = (
        time(hour=_end_hour, minute=_end_minute)
        if _end_hour and _end_minute
        else Trigger.__fields__['time_end'].default
    )

    saturation = list()
    if trigger_dict["saturation"]:
        saturation = [Saturation.from_moira_client_model(s) for s in trigger_dict["saturation"]]

    return Trigger(
        **{
            **{k: trigger_dict[k] for k in keys if k in trigger_dict},
            "id": trigger_dict.get("_id", None),
            "time_start": time_start,
            "time_end": time_end,
            "day_disable": [
                d["name"]
                for d in trigger_dict.get("sched", {}).get('days', {})
                if not d["enabled"]
            ],
            "saturation": saturation,
        }
    )


def _is_same_trigger_but_changed(left: Trigger, right: Trigger):
    """This only checks some fields of the two triggers.
    If _is_same_trigger_but_changed(l, r) is True but _is_equal_trigger(l, r) is False,
    we decide that `l` is actually `r` but with some fields changed,
    so alert-autoconf will edit `l` to make it `r`.
    """
    return (
        left.name == right.name
        and set(left.tags) == set(right.tags)
        and left.targets == right.targets
    )


def _is_equal_trigger(left: Trigger, right: Trigger, ignore_inheritance: bool) -> bool:
    """This checks ALL fields of the triggers for equality."""

    trigger_id = getattr(left, "id", None) or getattr(right, "id", None)

    attrs = left.__fields__.keys()
    for attr in attrs:
        if attr in ("id",):
            continue
        if ignore_inheritance and attr == "parents":
            continue

        lv = left.__getattribute__(attr)
        rv = right.__getattribute__(attr)

        # For fields: dashboard:
        if attr == "dashboard":
            l_dashboard = parse.parse_qs(parse.urlsplit(lv).query)
            r_dashboard = parse.parse_qs(parse.urlsplit(rv).query)
            if l_dashboard.get("panelId", None) == r_dashboard.get("panelId", None):
                continue

        # For fields: list (tags, targets, parents):
        if type(lv) == list and set(lv) == set(rv):
            continue

        # For fields: any
        if lv == rv:
            continue

        if attr != "name":
            logging.info(f"Detected difference in trigger {trigger_id}, field {attr}: {lv} != {rv}")
        break
    else:
        return True

    return False


class MoiraAlert:
    TRIGGER_TOKEN_PREFIX = "autoconf:token:"
    ALERTING_TOKEN_PREFIX = "autoconf:token-alerting:"

    def __init__(self, moira: Moira, redis: Redis, token: str):
        """

        :param moira: экземпляр объекта moira_client.Moira
        :param redis: экземпляр объекта redis.Redis
        :param token: уникальный ключ для синхронизации триггеров
        """
        if not isinstance(moira, Moira):
            raise TypeError("Input argument must be moira_client.Moira instance")
        self.moira = moira

        if not isinstance(redis, Redis):
            raise TypeError("Input argument must be redis.Redis instance")
        self.redis = redis

        if not isinstance(token, str):
            raise TypeError("Input argument must be str instance")
        self.base_token = token
        self.trigger_token = self.TRIGGER_TOKEN_PREFIX + token
        self.alerting_token = self.ALERTING_TOKEN_PREFIX + token

        self._is_prefixed = False

    def setup(self, data: Alerts):
        """
        Функция создает триггеры и оповещатели на события.
        Триггеры создаются из блока 'triggers'
        Оповещатели создаются из блока 'alerting'
        :param data: данные из файла конфигурации
        :return: None
        """

        self._is_prefixed = data.version >= 1.1 and len(data.prefix)
        self._triggers_worker(data.triggers, ignore_inheritance=True)
        self._triggers_worker(data.triggers, ignore_inheritance=False)
        self._create_alerting(data.alerting)

    def _triggers_worker(self, triggers_from_file: List[Trigger], ignore_inheritance: bool):
        """
        Проверяет соответствие триггеров в Мойре с описанными в alert.yaml
        :param triggers: список триггеров
        :param is_prefixed: наличие префикса в файле конфигурации
        :return: None
        """

        # ищем parent'ов для триггеров из файла
        triggers = []
        _triggers_from_file_by_id = dict()
        for trigger in triggers_from_file:
            trigger_fields = trigger.dict()
            if not ignore_inheritance and trigger.parents:
                trigger_fields["parents"] = self._find_trigger_parents(trigger.parents)
            else:
                trigger_fields["parents"] = list()
            del trigger_fields["id"]
            triggers.append(Trigger(**trigger_fields))

        api_triggers = []
        # Ищем триггеры по токену в Redis
        redis_has_triggers = self.redis.exists(self.trigger_token)
        if redis_has_triggers:
            logging.debug("Getting trigger IDs from redis")
            trigger_ids = self.redis.smembers(self.trigger_token)
            logging.debug("Trigger IDs: {!r}".format(sorted(trigger_ids)))
            for trigger_id in trigger_ids:
                tid = trigger_id.decode("utf-8")
                api_trigger = self.moira.trigger.fetch_by_id(tid)
                if not api_trigger:
                    text = "Trigger present in Redis but absent in Moira :: ({})"
                    logging.debug(text.format(tid))
                    self.redis.srem(self.trigger_token, tid)
                else:
                    api_triggers.append(api_trigger)
        # Триггеры в Redis не зарегистрированы, пробуем найти их по тегам
        else:
            # Актуально только для alert.yaml с указанным prefix
            if self._is_prefixed:
                logging.debug("Getting trigger IDs from YAML tags")
                custom_tags = {tag for trigger in triggers for tag in trigger.tags} - {
                    "ERROR",
                    "WARN",
                    "OK",
                    "NODATA",
                    "MONAD",
                }
                api_triggers = self.moira.tag.fetch_assigned_triggers_by_tags(
                    custom_tags
                )
                api_triggers = [self.moira.trigger.fetch_by_id(t) for t in api_triggers]
                logging.debug("Tags: {!r}".format(sorted(custom_tags)))
                _trigger_ids = [t.id for t in api_triggers]
                logging.debug("Trigger IDs: {!r}".format(sorted(_trigger_ids)))

        if not triggers_from_file and not redis_has_triggers:
            # если триггеров нет ни в файле, ни в Редисе -- выходим, чтобы не удалить лишнего
            return

        # Ни одного триггера не найдено
        if not api_triggers:
            # Создаем триггеры в Мойре
            logging.info(f"Triggers by RedisToken: {self.trigger_token} not found!")
            self._create_trigger(triggers)
            return

        # Конвертируем api_triggers в Trigger
        alerts_api_triggers = [trigger_moira_to_model(t) for t in api_triggers]
        # Что то да нашлось
        # Исключаем триггеры, в которых ничего не поменялось
        triggers_to_create = triggers.copy()
        for l in triggers:
            for r in alerts_api_triggers:
                try:
                    if triggers_to_create and _is_equal_trigger(l, r, ignore_inheritance):
                        triggers_to_create.remove(l)
                except Exception as e:
                    logging.exception(e)

        # Удаляем все триггеры, которые не соответствуют alert.yaml
        for api_trigger in alerts_api_triggers:
            if [
                trigger
                for trigger in triggers
                if _is_same_trigger_but_changed(trigger, api_trigger)
            ]:
                for trigger in [
                    trigger_to_create
                    for trigger_to_create in triggers_to_create
                    if _is_same_trigger_but_changed(trigger_to_create, api_trigger)
                ]:
                    # Триггер присутствует и в Мойре и в alert.yaml,
                    # но какие то его поля были изменены.
                    # Приведем триггер в Мойре к соотвествию с alert.yaml
                    logging.info(f"Updating trigger: {api_trigger.id}")
                    trigger.id = api_trigger.id
                    if ignore_inheritance:
                        trigger.parents = api_trigger.parents
                    self._create_trigger([trigger])
                    triggers_to_create.remove(trigger)
                    break
            else:
                # Триггер присутствует в Редисе и в Мойре, но в alert.yaml его нет. Удаляем.
                logging.debug(
                    f"Delete trigger (id :: {api_trigger.id}; name :: {api_trigger.name}; tags :: {{{api_trigger.tags}}})"
                )
                if self.moira.trigger.delete(api_trigger.id):
                    self.redis.srem(self.trigger_token, api_trigger.id)

        # Создаем новые триггеры
        self._create_trigger(triggers_to_create)

    def _create_trigger(self, triggers: List[Trigger]):
        """
        Создает триггеры по конфигурационному файлу
        :param triggers: список триггеров
        :param is_prefixed: наличие префикса в файле конфигурации
        :return: None
        """

        for trigger in triggers:
            trigger_fields = trigger.to_custom_dict()
            if trigger.id:
                trigger_fields["id"] = trigger.id
                log_text = "Update trigger (id :: {}; name :: {}; tags :: {{{}}} )"
            else:
                log_text = "Create trigger (id :: {}; name :: {}; tags :: {{{}}} )"
            tr = self.moira.trigger.create(**trigger_fields)
            tr.save()
            self.redis.sadd(self.trigger_token, tr.id)
            logging.debug(log_text.format(tr.id, tr.name, tr.tags))

    def _find_trigger_parents(self, parents: "moira_client.models.ParentTriggerRef") -> List[str]:
        found_parent_ids = []
        all_triggers = self.moira.trigger.fetch_all()
        for parent_ref in parents:
            parent_candidates = [
                t for t in all_triggers
                if t.name == parent_ref.name
                and set(t.tags) == set(parent_ref.tags)
            ]
            if len(parent_candidates) == 0:
                message = "Could not find trigger with name={name}, tags={tags}"
                raise ValueError(message.format(
                    name=parent_ref.name,
                    tags=", ".join(parent_ref.tags),
                ))
            elif len(parent_candidates) > 1:
                message = "Found {num} > 1 triggers with name={name}, tags={tags}"
                raise ValueError(message.format(
                    num=len(parent_candidates),
                    name=parent_ref.name,
                    tags=", ".join(parent_ref.tags),
                ))
            else:
                found_parent_ids.append(parent_candidates[0].id)
        return found_parent_ids

    def _get_remote_subscriptions(
        self, alerts: List[Subscription], subscription_manager: SubscriptionManager
    ) -> List[MoiraSubscription]:
        """
        Возвращает список всех подписок, которые принадлежат пользователю и имеют тег из конфиг файла
        :param alerts: список оповещателей
        :return:
        """
        tags = {t for s in alerts for t in s.tags}
        excludes = [
            "ERROR",
            "OK",
            "NODATA",
            "CRITICAL",
            "WARN",
            "Critical",
            "critical",
            "MONAD",
        ]

        subscriptions = subscription_manager.fetch_all()

        def filter_by_tags(s):
            return (tags & set(s.tags)) - set(excludes)

        return list(filter(filter_by_tags, subscriptions))

    def _get_contacts(
        self, contacts: List[Contact], current_contacts: list
    ) -> List[Contact]:
        """
        Функция возвращает список контактов из current_contacts. Если в
        current_contacts контакт отсутствует, посылается запрос на сервер на создание
        нового контакта. (из ответа берется только поле id)
        :param contacts: список контактов
        :return:
        """
        contact_array = []
        for yaml_contact in contacts:
            if not yaml_contact.value:
                continue
            for current_contact in current_contacts:
                if (
                    current_contact.type == yaml_contact.type
                    and current_contact.value == yaml_contact.value
                    and current_contact.fallback_value == yaml_contact.fallback_value
                ):
                    contact = current_contact
                    break
            else:
                contact = self.moira.contact.add(
                    contact_type=yaml_contact.type.value,
                    value=yaml_contact.value,
                    fallback_value=yaml_contact.fallback_value,
                )

            contact_array.append(
                Contact(
                    id=contact.id,
                    type=contact.type,
                    value=contact.value,
                    fallback_value=contact.fallback_value,
                )
            )

        return contact_array

    @staticmethod
    def _escalations_to_set(escalations):
        s = sorted(escalations, key=lambda e: e["offset_in_minutes"])
        return set((e["offset_in_minutes"], tuple(sorted(e["contacts"]))) for e in s)

    @classmethod
    def _subscription_not_changed(cls, first, second):
        changed = any(set(first[f]) != set(second[f]) for f in ("tags", "contacts"))

        if changed:
            return False

        changed = any(
            first['sched'][f] != second['sched'][f]
            for f in ("startOffset", "endOffset", "tzOffset")
        )

        if changed:
            return False

        if first['sched']['days'] != second['sched']['days']:
            return False

        return cls._escalations_to_set(first["escalations"]) == cls._escalations_to_set(
            second["escalations"]
        )

    def _create_alerting(self, alerts: List[Subscription]):
        """
        Функция анализирует, какие контакты нужно удалить/добавить.
        При обновлении списка - те подписки, которые были установлены в Мойре и которые никак
        не меняют файл конфигурации и не удаляются. Сравнение происходит по списку контактов и тегов подписки.
        :param alerts: список оповещателей
        :return:
        """

        redis_has_alerting = self.redis.exists(self.alerting_token)
        if redis_has_alerting:
            logging.debug("Subscription id's from redis")

            all_subscriptions = self.moira.subscription.fetch_all()
            all_subscriptions = {s.id: s for s in all_subscriptions}
            current_subscriptions = []

            for subscription_id in self.redis.smembers(self.alerting_token):
                subscription_id = subscription_id.decode("utf-8")
                api_subscription = all_subscriptions.get(subscription_id)
                if not api_subscription:
                    text = "Moira subscription absent :: ({})"
                    logging.debug(text.format(subscription_id))
                    self.redis.srem(self.alerting_token, subscription_id)
                else:
                    current_subscriptions.append(api_subscription)

        else:
            current_subscriptions = self._get_remote_subscriptions(
                alerts, self.moira.subscription
            )

        if not alerts and not redis_has_alerting:
            # if the file and Redis both don't have alerting then exit
            return

        # protect all subscriptions that are already registered in Redis
        # they should not be deleted
        protected_sub_ids = dict()
        for key in self.redis.keys(self.ALERTING_TOKEN_PREFIX + "*"):
            if key != bytes(self.alerting_token, "ascii"):
                protected_sub_ids.update({
                    sub_id: key
                    for sub_id in self.redis.smembers(key)
                })
        # convert bytes to str
        protected_sub_ids = {k.decode(): v.decode() for k, v in protected_sub_ids.items()}

        current_contacts = self.moira.contact.fetch_by_current_user()

        # Список подписок, которые нужно создать в Мойре
        new_subscriptions = []

        for item in alerts:
            if not item.contacts:
                continue

            if re.search("{", item.contacts[0].value):
                continue

            escalations = []
            for e in item.escalations:
                escalations.append(
                    Escalation(
                        contacts=self._get_contacts(e.contacts, current_contacts),
                        offset_in_minutes=e.offset_in_minutes,
                    )
                )

            contacts = self._get_contacts(item.contacts, current_contacts)

            if contacts:
                subscription = Subscription(
                    tags=item.tags,
                    contacts=contacts,
                    escalations=escalations,
                    day_disable=item.day_disable,
                    time_start=item.time_start,
                    time_end=item.time_end,
                )

                for i, current_subscription in enumerate(current_subscriptions):
                    if self._subscription_not_changed(
                        subscription.to_custom_dict(), current_subscription.__dict__
                    ):
                        del current_subscriptions[i]
                        break
                else:
                    new_subscriptions.append(subscription)

        for current_subscription in current_subscriptions:
            if current_subscription.id not in protected_sub_ids:
                if self.moira.subscription.delete(current_subscription.id):
                    self.redis.srem(self.alerting_token, current_subscription.id)
                log_text = "Remove subscription :: {}"
            else:
                log_text = "Not removing protected subscription :: {}, protected by token :: %s" % protected_sub_ids[current_subscription.id]
            logging.debug(log_text.format(current_subscription.id))

        for new_subscription in new_subscriptions:
            sub_id = self.moira.subscription.create(**new_subscription.to_custom_dict())
            sub_id.save()
            self.redis.sadd(self.alerting_token, sub_id.id)

            log_text = (
                "Save subscription (id :: {}; contacts :: {{{}}}; tags :: {{{}}} )"
            )
            logging.debug(
                log_text.format(
                    sub_id.id, new_subscription.contacts, new_subscription.tags
                )
            )
