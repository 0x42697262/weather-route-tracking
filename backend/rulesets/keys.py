"""Keys of the rule set document, its problem paths and its cache entries."""

from enum import StrEnum

ROOT_FIELD = "$"
CACHE_KEY_PREFIX = "rule_set"
CACHE_PAYLOAD_VERSION = 1
ACTIVATE_PERMISSION = "activate_rulesetversion"
ACTION_ACTIVATE = "activate"


class Key(StrEnum):
    """Every key a rule set document may hold."""

    SCHEMA_VERSION = "schema_version"
    CONDITIONS = "conditions"
    VARIABLE = "variable"
    UNIT = "unit"
    BANDS = "bands"
    LEVEL = "level"
    FROM = "from"
    TO = "to"
    INCLUSIVE = "inclusive"
    LOAD_RULES = "load_rules"
    LOAD_OVER = "load_over"
    VALUE = "value"
    TRUCK_SPEED_FACTOR = "truck_speed_factor"
    TRUCK_MAX_SPEED = "truck_max_speed"
    EMPTY_VEHICLE_WEIGHT = "empty_vehicle_weight"
    REST_RULES = "rest_rules"
    ENABLED = "enabled"
    MAX_DRIVING_BEFORE_BREAK_HOURS = "max_driving_before_break_hours"
    BREAK_MINUTES = "break_minutes"
    MAX_DRIVING_PER_SHIFT_HOURS = "max_driving_per_shift_hours"
    MAX_SHIFT_HOURS = "max_shift_hours"
    OFF_DUTY_HOURS = "off_duty_hours"
    STRETCH_METHOD = "stretch_method"
    FERRY_LEVEL = "ferry_level"
    MAX_UNKNOWN_SHARE = "max_unknown_share"
    CHECKPOINT_SPACINGS = "checkpoint_spacings"
    DEFAULT_CHECKPOINT_SPACING = "default_checkpoint_spacing"


def child_field(parent: str, key: str) -> str:
    """The path of a key inside an object at `parent`."""
    return key if parent == ROOT_FIELD else f"{parent}.{key}"


def item_field(parent: str, index: int) -> str:
    """The path of an item inside a list at `parent`."""
    return f"{parent}[{index}]"


def rule_set_cache_key(version: int, created_at_iso: str) -> str:
    """The cache key of one validated rule set version.

    The creation time guards against a reused version number after a database reset.
    """
    return f"{CACHE_KEY_PREFIX}:{CACHE_PAYLOAD_VERSION}:{version}:{created_at_iso}"
