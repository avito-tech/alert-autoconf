import logging

import uuid

from unittest import TestCase
from unittest.mock import patch
from unittest.mock import Mock

from pydantic import ValidationError

from moira_client import Moira
from moira_client.client import Client
from moira_client.models.tag import TagManager
from moira_client.models.trigger import TriggerManager, Trigger
from moira_client.models.contact import ContactManager, Contact
from moira_client.models.subscription import SubscriptionManager

from redis import Redis

from alert_autoconf.moira import MoiraAlert
from alert_autoconf.config import read_from_file
from alert_autoconf import LOG_FORMAT

logging.basicConfig(level=logging.ERROR, format=LOG_FORMAT)

logger = logging.getLogger('alert')


class MoiraAlertTest(TestCase):
    def assertDictKeysEqual(self, custom, expected):
        """
        Проверка ключей словарей
        :param expected: - словарь, который ожидаем
        :param custom: - словарь, который вернул запрос
        :return:
        """
        self.assertIsInstance(expected, dict, msg='expected are not dict')
        self.assertIsInstance(custom, dict, msg='custom are not dict')
        if expected.keys() == custom.keys():
            for k in expected:
                if isinstance(expected[k], dict):
                    self.assertDictKeysEqual(custom[k], expected[k])
        else:
            custom_error = expected.keys() ^ (expected.keys() | custom.keys())
            expected_error = custom.keys() ^ (expected.keys() | custom.keys())

            self.assertEqual(
                custom,
                set(),
                msg='Key(s) [{}] are not found in expected dictionary'.format(
                    custom_error
                ),
            )
            self.assertEqual(
                expected,
                set(),
                msg='Key(s) [{}] are not found in custom dictionary'.format(
                    expected_error
                ),
            )

    def setUp(self):
        self.url = 'http://localhost:1234/api/'
        self.token = 'test'
        self.redis_token_storage = 'redis://localhost:5678/10'

        self.moira = Moira(self.url)
        self.redis = Redis.from_url(self.redis_token_storage)

    def createCustomTriggers(self):
        current_triggers = {}
        trigger_id = str(uuid.uuid4())
        current_triggers[trigger_id] = Trigger(
            client=None,
            id=trigger_id,
            name='Trigger_1',
            targets=['stats.timer_1', 'stats.timer_2'],
            desc='Test description 1',
            warn_value=15,
            error_value=10,
            ttl=100,
            tags=['service_1'],
            ttl_state='ERROR',
            sched={
                'days': [{'enabled': False, 'name': 'Tue'}],
                'startOffset': 750,
                'endOffset': 1439,
            },
        )
        trigger_id = str(uuid.uuid4())
        current_triggers[trigger_id] = Trigger(
            client=None,
            id=trigger_id,
            name='Trigger_2',
            targets=['stats.timer_3', 'stats.timer4'],
            desc='Test description 2',
            warn_value=10,
            error_value=20,
            ttl=20,
            tags=['service_2'],
            ttl_state='NODATA',
            expression='(t1 > 10) ? ERROR : ((t2 > 4) ? WARN : OK)',
            sched={
                'days': [
                    {'enabled': False, 'name': 'Tue'},
                    {'enabled': False, 'name': 'Wed'},
                ],
                'startOffset': 750,
                'endOffset': 1439,
            },
        )

        return current_triggers

    def test_invalid_config_read_raises_ValidationError(self):
        invalid_config = 'tests/invalid_config.yaml'

        with self.assertRaises(ValidationError):
            read_from_file(invalid_config)

    def test_invalid_constructor_call_raises_TypeError(self):
        with self.assertRaises(TypeError):
            MoiraAlert('')

    def test_call_setup_with_incorrect_argument_raise_AttributeError(self):
        alert = MoiraAlert(self.moira, self.redis, self.token)

        with self.assertRaises(AttributeError):
            alert.setup('')

    def test_config_prefix(self):
        data = read_from_file('tests/valid_config_second.yaml')
        prefix = data.prefix
        for trigger in data.triggers:
            self.assertTrue(trigger.name.startswith(prefix), 'Trigger name with prefix')
            for tag in trigger.tags:
                self.assertTrue(tag.startswith(prefix), 'Trigger tag with prefix')

        for alerting in data.alerting:
            for tag in alerting.tags:
                self.assertTrue(tag.startswith(prefix), 'Alerting tag with prefix')

    def test_create_fake_moira_trigger_and_alerting_prefix_not_exists_token_not_exists(
        self
    ):
        valid_config = 'tests/valid_config.yaml'
        data = read_from_file(valid_config)
        client = Client(self.url)

        with patch.object(client, 'get', return_value={'list': []}), patch.object(
            client, 'put', return_value={}
        ):
            trigger_manager = TriggerManager(client)
            tag_manager = TagManager(client)
            contact_manager = ContactManager(client)
            subscription_manager = SubscriptionManager(client)

            with patch.object(
                self.moira, '_trigger', return_value=trigger_manager
            ) as _trigger_mock, patch.object(
                self.moira, '_contact', return_value=contact_manager
            ) as _contact_mock, patch.object(
                self.moira, '_tag', return_value=tag_manager
            ) as _tag_mock, patch.object(
                self.moira, '_subscription', return_value=subscription_manager
            ), patch.object(
                self.redis, 'exists', return_value=0
            ), patch.object(
                self.redis, 'sadd', return_value=1
            ) as _redis_sadd_mock:
                _contact_mock.fetch_by_current_user.return_value = []
                _contact_mock.add = Mock(
                    side_effect=lambda value, contact_type: Contact(
                        id=str(uuid.uuid4()), type=contact_type, value=value
                    )
                )
                trigger_orig = MoiraAlert(self.moira, self.redis, self.token)
                trigger_orig.setup(data)

            args, kwargs = _trigger_mock.create.call_args_list[0]
            kwargs.pop('name')
            count_contacts_in_alerting_block = self._get_count_key_by_dict(
                data.alerting, 'contacts'
            )
            count_contacts_in_alerting_block += 2  # + 2 contacts from escalations

            self.assertFalse(_tag_mock.fetch_assigned_triggers_by_tags.called)
            self.assertDictKeysEqual(
                {
                    k: v
                    for k, v in data.triggers[0].to_custom_dict().items()
                    if k not in ('name',)
                },
                kwargs,
            )
            self.assertTrue(_contact_mock.add.called)
            self.assertTrue(_trigger_mock.create.called)
            self.assertEqual(
                _contact_mock.add.call_count, count_contacts_in_alerting_block
            )
            self.assertEqual(_trigger_mock.create.call_count, len(data.triggers))
            self.assertEqual(_redis_sadd_mock.call_count, len(data.triggers))

    def test_create_fake_moira_trigger_and_alerting_prefix_exists_token_not_exists(
        self
    ):
        valid_config = 'tests/valid_config_second.yaml'
        data = read_from_file(valid_config)
        trigger_count = len(data.triggers)
        client = Client(self.url)

        with patch.object(client, 'get', return_value={'list': []}), patch.object(
            client, 'put', return_value={}
        ):
            trigger_manager = TriggerManager(client)
            tag_manager = TagManager(client)
            contact_manager = ContactManager(client)
            subscription_manager = SubscriptionManager(client)

            with patch.object(
                self.moira, '_trigger', return_value=trigger_manager
            ) as _trigger_mock, patch.object(
                self.moira, '_contact', return_value=contact_manager
            ) as _contact_mock, patch.object(
                self.moira, '_tag', return_value=tag_manager
            ) as _tag_mock, patch.object(
                self.moira, '_subscription', return_value=subscription_manager
            ), patch.object(
                self.redis, 'exists', return_value=0
            ) as _redis_exists, patch.object(
                self.redis, 'sadd', return_value=1
            ) as _redis_sadd:
                _contact_mock.fetch_by_current_user.return_value = []
                _contact_mock.add = Mock(
                    side_effect=lambda value, contact_type: Contact(
                        id=str(uuid.uuid4()), type=contact_type, value=value
                    )
                )
                trigger_orig = MoiraAlert(self.moira, self.redis, self.token)
                trigger_orig.setup(data)

            args, kwargs = _trigger_mock.create.call_args_list[0]
            kwargs.pop('name')
            count_contacts_in_alerting_block = self._get_count_key_by_dict(
                data.alerting, 'contacts'
            )
            count_contacts_in_alerting_block += 2  # + 2 contacts from escalations

            self.assertTrue(_tag_mock.fetch_assigned_triggers_by_tags.called)
            self.assertDictKeysEqual(
                {
                    k: v
                    for k, v in data.triggers[0].to_custom_dict().items()
                    if k not in ('name',)
                },
                kwargs,
            )
            self.assertTrue(_contact_mock.add.called)
            self.assertTrue(_trigger_mock.create.called)
            self.assertEqual(
                _contact_mock.add.call_count, count_contacts_in_alerting_block
            )
            self.assertEqual(_trigger_mock.create.call_count, trigger_count)
            self.assertEqual(_redis_exists.call_count, 1)
            self.assertEqual(_redis_sadd.call_count, trigger_count)

    def test_create_fake_moira_trigger_and_alerting_token_exists_and_empty(self):
        valid_config = 'tests/valid_config.yaml'
        data = read_from_file(valid_config)
        trigger_count = len(data.triggers)
        client = Client(self.url)

        with patch.object(client, 'get', return_value={'list': []}), patch.object(
            client, 'put', return_value={}
        ):
            trigger_manager = TriggerManager(client)
            tag_manager = TagManager(client)
            contact_manager = ContactManager(client)
            subscription_manager = SubscriptionManager(client)

            with patch.object(
                self.moira, '_trigger', return_value=trigger_manager
            ) as _trigger_mock, patch.object(
                self.moira, '_contact', return_value=contact_manager
            ) as _contact_mock, patch.object(
                self.moira, '_tag', return_value=tag_manager
            ) as _tag_mock, patch.object(
                self.moira, '_subscription', return_value=subscription_manager
            ), patch.object(
                self.redis, 'exists', return_value=1
            ) as _redis_exists_mock, patch.object(
                self.redis, 'smembers', return_value=set()
            ), patch.object(
                self.redis, 'sadd', return_value=1
            ) as _redis_sadd_mock:
                _contact_mock.fetch_by_current_user.return_value = []
                _contact_mock.add = Mock(
                    side_effect=lambda value, contact_type: Contact(
                        id=str(uuid.uuid4()), type=contact_type, value=value
                    )
                )
                trigger_orig = MoiraAlert(self.moira, self.redis, self.token)
                trigger_orig.setup(data)

            args, kwargs = _trigger_mock.create.call_args_list[0]
            kwargs.pop('name')
            count_contacts_in_alerting_block = self._get_count_key_by_dict(
                data.alerting, 'contacts'
            )
            count_contacts_in_alerting_block += 2  # + 2 contacts from escalations

            self.assertFalse(_tag_mock.fetch_assigned_triggers_by_tags.called)
            self.assertDictKeysEqual(
                {
                    k: v
                    for k, v in data.triggers[0].to_custom_dict().items()
                    if k not in ('name',)
                },
                kwargs,
            )
            self.assertTrue(_contact_mock.add.called)
            self.assertFalse(_trigger_mock.fetch_by_id.called)
            self.assertTrue(_trigger_mock.create.called)
            self.assertEqual(
                _contact_mock.add.call_count, count_contacts_in_alerting_block
            )
            self.assertEqual(_trigger_mock.create.call_count, trigger_count)
            self.assertTrue(_redis_exists_mock.called)
            self.assertEqual(_redis_sadd_mock.call_count, trigger_count)

    def test_create_fake_moira_trigger_and_alerting_token_exists_and_not_empty(self):
        valid_config = 'tests/valid_config.yaml'
        data = read_from_file(valid_config)
        current_triggers = self.createCustomTriggers()
        moira_triggers = dict([current_triggers.popitem()])
        client = Client(self.url)

        redis_trigger_ids = set(i.encode('utf-8') for i in moira_triggers.keys())
        redis_trigger_ids = redis_trigger_ids | {str(uuid.uuid4()).encode('utf-8')}

        with patch.object(client, 'get', return_value={'list': []}), patch.object(
            client, 'put', return_value={}
        ):
            trigger_manager = TriggerManager(client)
            tag_manager = TagManager(client)
            contact_manager = ContactManager(client)
            subscription_manager = SubscriptionManager(client)

            with patch.object(
                self.moira, '_trigger', return_value=trigger_manager
            ) as _trigger_mock, patch.object(
                self.moira, '_contact', return_value=contact_manager
            ) as _contact_mock, patch.object(
                self.moira, '_tag', return_value=tag_manager
            ) as _tag_mock, patch.object(
                self.moira, '_subscription', return_value=subscription_manager
            ), patch.object(
                self.redis, 'exists', return_value=1
            ) as _redis_exists_mock, patch.object(
                self.redis, 'smembers', return_value=redis_trigger_ids
            ) as _redis_smembers_mock, patch.object(
                self.redis, 'sadd', return_value=1
            ) as _redis_sadd_mock, patch.object(
                self.redis, 'srem', return_value=1
            ) as _redis_srem_mock:
                _trigger_mock.fetch_by_id = Mock(
                    side_effect=lambda id: moira_triggers.get(id, None)
                )
                _contact_mock.fetch_by_current_user.return_value = []
                _contact_mock.add = Mock(
                    side_effect=lambda value, contact_type: Contact(
                        id=str(uuid.uuid4()), type=contact_type, value=value
                    )
                )
                trigger_orig = MoiraAlert(self.moira, self.redis, self.token)
                trigger_orig.setup(data)

            args, kwargs = _trigger_mock.create.call_args_list[0]
            kwargs.pop('name')
            count_contacts_in_alerting_block = self._get_count_key_by_dict(
                data.alerting, 'contacts'
            )
            count_contacts_in_alerting_block += 2  # + 2 contacts from escalations

            self.assertFalse(_tag_mock.fetch_assigned_triggers_by_tags.called)
            self.assertDictKeysEqual(
                {
                    k: v
                    for k, v in data.triggers[0].to_custom_dict().items()
                    if k not in ('name',)
                },
                kwargs,
            )
            self.assertTrue(_contact_mock.add.called)
            self.assertEqual(_trigger_mock.fetch_by_id.call_count, 2)
            self.assertTrue(_trigger_mock.create.called)
            self.assertEqual(
                _contact_mock.add.call_count, count_contacts_in_alerting_block
            )
            self.assertEqual(_trigger_mock.create.call_count, 1)
            self.assertTrue(_redis_exists_mock.call_count)
            self.assertTrue(_redis_smembers_mock.call_count)
            self.assertEqual(_redis_sadd_mock.call_count, 1)
            self.assertEqual(_redis_srem_mock.call_count, 1)

    def _get_count_key_by_dict(self, data: list, key: str) -> int:
        cnt = 0
        for alert in data:
            contacts = alert.__getattribute__(key)
            if contacts:
                cnt += len(contacts)
        return cnt
