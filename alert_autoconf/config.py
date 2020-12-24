import codecs

import yaml
from typing import Optional

from alert_autoconf.models import Alerts


CLUSTER_NAME_PLACEHOLDER = "{cluster}"


def read_from_file(filename: str, cluster_name: Optional[str]) -> Alerts:
    """
    Читает данные из конфиг файла
    :param filename: имя файла
    :return: словарь конфигурации
    """
    with codecs.open(filename, "r", encoding="UTF-8") as stream:
        data = Alerts(**yaml.load(stream, Loader=yaml.FullLoader))

        if data.version < 1.1:
            return data

        prefix = data.prefix

        # применяем prefix
        if len(prefix):
            skip = ("ERROR", "WARN", "OK", "NODATA", "MONAD")

            for trigger in data.triggers:
                trigger.name = prefix + trigger.name
                trigger.tags = [
                    prefix + tag for tag in trigger.tags if tag not in skip
                ] + [tag for tag in trigger.tags if tag in skip]

            for alerting in data.alerting:
                alerting.tags = [
                    prefix + tag for tag in alerting.tags if tag not in skip
                ] + [tag for tag in alerting.tags if tag in skip]

        # применяем cluster_name
        for trigger in data.triggers:
            _apply_cluster_name(trigger.tags, cluster_name)
            _apply_cluster_name(trigger.targets, cluster_name)
            if trigger.parents:
                for parent in trigger.parents:
                    _apply_cluster_name(parent.tags, cluster_name)
        for alerting in data.alerting:
            _apply_cluster_name(alerting.tags, cluster_name)

        return data


def _apply_cluster_name(strings, cluster_name):
    for i in range(len(strings)):
        if CLUSTER_NAME_PLACEHOLDER in strings[i]:
            if not cluster_name:
                raise ValueError(
                    "Config file uses {} but cluster name is not set".format(CLUSTER_NAME_PLACEHOLDER),
                )
            strings[i] = strings[i].replace(CLUSTER_NAME_PLACEHOLDER, cluster_name)
