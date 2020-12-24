import logging
from typing import List

import pydantic
from redis import Redis
import yaml

from alert_autoconf import models


# Redis keys
DEFAULT_PREFIX = "autoconf:defaults:"
DEFAULT_TRIGGER_KEY = DEFAULT_PREFIX + "triggers"


class DefaultCondition(pydantic.BaseModel):
    tags: List[str]

    def applies(self, trigger: models.TriggerFile):
        return set(self.tags).issubset(trigger.tags)


class DefaultValues(pydantic.BaseModel):
    parents: List[models.ParentTriggerRef]


class DefaultRule(pydantic.BaseModel):
    condition: DefaultCondition
    values: DefaultValues


class DefaultFile(pydantic.BaseModel):
    defaults: List[DefaultRule]


def apply_defaults(alerts: models.Alerts, redis: Redis):
    """Applies default values stored in Redis.
    As of version 0.4.15, the defaults are these:
    * all triggers with a MONAD tag get default parents.
    """

    default_file = redis.get(DEFAULT_TRIGGER_KEY)
    if default_file is None:
        logging.info("Defaults not found in Redis, skipping.")
    else:
        default_file = yaml.safe_load(default_file)
        default_file = DefaultFile(**default_file)
        default_rules = default_file.defaults

        for trigger in alerts.triggers:
            for default_rule in default_rules:
                if default_rule.condition.applies(trigger):
                    trigger.parents = _extend_without_duplicates(trigger.parents, default_rule.values.parents)


def _extend_without_duplicates(this, extension):
    if this is None:
        this = []
    for item in extension:
        if item not in this:
            this.append(item)
    return this
