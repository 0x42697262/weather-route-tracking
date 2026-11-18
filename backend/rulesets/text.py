"""Messages of rule sets: validator problems and admin strings."""

from collections.abc import Iterable

NOT_AN_OBJECT = "Must be an object."
NOT_A_LIST = "Must be a list."
NOT_A_NUMBER = "Must be a finite number."
NOT_A_BOOLEAN = "Must be true or false."
NOT_A_STRING = "Must be a string."
MISSING_KEY = "This key is required."
UNKNOWN_KEY = "This key is not allowed."
MUST_BE_POSITIVE = "Must be greater than 0."
MUST_NOT_BE_EMPTY = "Must not be empty."
LOW_BAND = "A band cannot have the lowest level; values below the first band are already at it."
BAND_BOUND_NOT_ASCENDING = "Each band must start strictly above the band before it."
BAND_LEVEL_NOT_ASCENDING = "Each band must have a strictly worse level than the band before it."
LOAD_RULE_RANGE_EMPTY = "'from' must be below 'to'."
DUPLICATE_VARIABLE = "Each variable may have only one condition."
DUPLICATE_SPACING = "Each spacing may appear only once."
DEFAULT_SPACING_NOT_ALLOWED = "The default spacing must be one of the allowed spacings."
BREAK_LIMIT_ABOVE_SHIFT_DRIVING = (
    "The driving limit before a break must not exceed the driving limit per shift."
)
SHIFT_DRIVING_ABOVE_SHIFT_LENGTH = "The driving limit per shift must not exceed the shift length."

SEED_NOTE = "Defaults from docs/SPEC.md"
UNKNOWN_SHARE_UPGRADE_NOTE = (
    "Previous active version plus max_unknown_share 0.25: a route more than a quarter without "
    "forecast is not recommended"
)
ADMIN_ACTIVATE_DESCRIPTION = "Activate the selected version"
ADMIN_ACTIVATE_EXACTLY_ONE = "Select exactly one version to activate."
ADMIN_DATA_HELP = (
    "The rule set document as JSON. It is pre-filled from the active version. "
    "Saving creates a new version; it is not active until you activate it."
)
VERSION_IMMUTABLE = "A saved rule set version cannot be changed; save a new version instead."
DOCUMENT_LABEL = "Document"
VERBOSE_NAME = "rule set version"
VERBOSE_NAME_PLURAL = "rule set versions"
ACTIVATE_PERMISSION_NAME = "Can activate rule set version"


def admin_activated(version: int) -> str:
    """Admin message after a version was activated."""
    return f"Rule set version {version} is now active."


def version_label(version: int) -> str:
    """How a version is named in admin."""
    return f"Version {version}"


def rule_set_invalid(problem_count: int) -> str:
    """Summary of a rejected document."""
    return f"The rule set has {problem_count} problem(s)."


def unknown_schema_version(known: Iterable[int]) -> str:
    """Problem: the schema version is not one this server reads."""
    listed = ", ".join(str(version) for version in sorted(known))
    return f"Unknown schema version; known versions: {listed}."


def not_one_of(allowed: Iterable[str]) -> str:
    """Problem: a value outside a fixed set."""
    listed = ", ".join(sorted(allowed))
    return f"Must be one of: {listed}."


def too_many(maximum: int) -> str:
    """Problem: a list longer than its cap."""
    return f"At most {maximum} items are allowed."


def out_of_bounds(minimum: float, maximum: float) -> str:
    """Problem: a plain number outside its bounds."""
    return f"Must be between {minimum:g} and {maximum:g}."


def out_of_bounds_in_unit(minimum: float, maximum: float, unit: str) -> str:
    """Problem: a quantity outside its bounds, stated in the unit the bounds are kept in."""
    return f"Must be between {minimum:g} {unit} and {maximum:g} {unit}."


def problem_line(field: str, message: str) -> str:
    """One problem as shown on the admin form."""
    return f"{field}: {message}"
