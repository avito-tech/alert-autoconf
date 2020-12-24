from uuid import UUID
from datetime import time
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, AnyHttpUrl, validator, root_validator


class ContactTypeEnum(Enum):
    JIRA = "jira"
    MAIL = "mail"
    PUSHOVER = "pushover"
    SEND_SMS = "send-sms"
    SLACK = "slack"
    TELEGRAM = "telegram"
    TWILIO_SMS = "twilio sms"
    TWILIO_VOICE = "twilio voice"


class DaysEnum(Enum):
    MON = "Mon"
    TUE = "Tue"
    WED = "Wed"
    THU = "Thu"
    FRI = "Fri"
    SAT = "Sat"
    SUN = "Sun"


class TtlStateEnum(Enum):
    DEL = "DEL"
    ERROR = "ERROR"
    NODATA = "NODATA"
    OK = "OK"
    WARN = "WARN"


class ParentTriggerRef(BaseModel):
    tags: List[str]
    name: str

    def __hash__(self):
        return hash((
            frozenset(tags),
            name,
        ))

    def __eq__(self, other):
        return (
            set(self.tags) == set(other.tags)
            and self.name == other.name
        )


class Saturation(BaseModel):
    type: str
    fallback: Optional[str] = None
    parameters: Optional[dict] = None

    def to_custom_dict(self) -> Dict:
        result = {
            "type": self.type,
        }
        if self.fallback is not None:
            result["fallback"] = self.fallback
        if self.parameters is not None:
            result["extra_parameters"] = self.parameters
        return result

    @classmethod
    def from_moira_client_model(cls, moira_saturation: "moira_client.models.trigger.Saturation"):
        d = moira_saturation.to_dict()
        d["parameters"] = d.pop("extra_parameters", None)
        return cls(**d)

    def __hash__(self):
        dct = self.to_custom_dict()
        return hash(_freeze_dict(dct))

    def __eq__(self, other):
        if isinstance(other, Saturation):
            return self.to_custom_dict() == other.to_custom_dict()
        else:
            raise ValueError("Incomparable types")


def _freeze_dict(dct):
    """Tries to freeze a dict to make it hashable."""
    result = []
    for key, value in dct.items():
        if isinstance(value, dict):
            value = _freeze_dict(value)
        result.append((key, value))
    result.sort()
    return tuple(result)


class Trigger(BaseModel):
    id: Optional[str] = None
    name: str
    tags: List[str]
    targets: List[str]
    warn_value: Optional[int] = None
    error_value: Optional[int] = None
    desc: str = ""
    ttl: int = 600
    ttl_state: TtlStateEnum = TtlStateEnum.NODATA
    expression: Optional[str] = ""

    is_pull_type: bool = False
    dashboard: Optional[AnyHttpUrl] = None
    pending_interval: Optional[int] = 0

    day_disable: List[DaysEnum] = []
    time_start: Optional[time] = time(hour=0, minute=0)
    time_end: Optional[time] = time(hour=23, minute=59)

    parents: Optional[List[str]]

    saturation: Optional[List[Saturation]] = list()

    @validator("id")
    def id_uuid(cls, v):
        try:
            UUID(v)
        except ValueError:
            raise
        return v

    @root_validator
    def check_thresholds_values(cls, values):
        warn_value, error_value = (
            values.get('warn_value') is not None,
            values.get('error_value') is not None,
        )
        if warn_value ^ error_value:
            raise ValueError('must provide warn_value and error_value')

        if (
            warn_value & error_value
            and len(values.get('targets')) > 1
            and values.get('expression') is None
        ):
            raise ValueError('must use single target with warn_value and error_value')

        return values

    def to_custom_dict(self) -> Dict:
        return {
            'name': self.name,
            'tags': self.tags,
            'targets': self.targets,
            'warn_value': self.warn_value,
            'error_value': self.error_value,
            'desc': self.desc,
            'ttl': self.ttl,
            'ttl_state': self.ttl_state.value,
            'expression': self.expression,
            'is_pull_type': self.is_pull_type,
            'dashboard': self.dashboard,
            'pending_interval': self.pending_interval,
            'sched': {
                'startOffset': self.time_start.hour * 60 + self.time_start.minute,
                'endOffset': self.time_end.hour * 60 + self.time_end.minute,
                'tzOffset': 0,
                'days': [
                    {'name': day.value, 'enabled': day not in self.day_disable}
                    for day in DaysEnum
                ],
            },
            'parents': self.parents,
            'saturation': [
                s.to_custom_dict()
                for s in self.saturation
            ],
        }


class TriggerFile(Trigger):
    parents: Optional[List[ParentTriggerRef]]


class Contact(BaseModel):
    id: Optional[str] = None
    type: ContactTypeEnum
    value: str
    fallback_value: Optional[str] = None

    def __hash__(self):
        return f"{self.type}:{self.value}:{self.fallback_value}".__hash__()


class Escalation(BaseModel):
    contacts: List[Contact]
    offset_in_minutes: int = 0


class Subscription(BaseModel):
    tags: List[str]
    contacts: Optional[List[Contact]] = []
    escalations: Optional[List[Escalation]] = []
    day_disable: List[DaysEnum] = []
    time_start: Optional[time] = time(hour=0, minute=0)
    time_end: Optional[time] = time(hour=23, minute=59)

    def to_custom_dict(self) -> Dict:
        return {
            'tags': self.tags,
            'contacts': [c.id for c in self.contacts],
            'escalations': [
                {
                    'contacts': [c.id for c in e.contacts],
                    'offset_in_minutes': e.offset_in_minutes,
                }
                for e in self.escalations
            ],
            'sched': {
                'startOffset': self.time_start.hour * 60 + self.time_start.minute,
                'endOffset': self.time_end.hour * 60 + self.time_end.minute,
                'tzOffset': 0,
                'days': [
                    {'name': day.value, 'enabled': day not in self.day_disable}
                    for day in DaysEnum
                ],
            },
        }


class Alerts(BaseModel):
    version: float = 1
    prefix: str = ""
    triggers: List[TriggerFile] = []
    alerting: List[Subscription] = []
