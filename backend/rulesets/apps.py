"""The rule sets Django app."""

from django.apps import AppConfig


class RulesetsConfig(AppConfig):
    """Versioned business rules, edited by staff in admin."""

    name = "rulesets"
    default_auto_field = "django.db.models.BigAutoField"
