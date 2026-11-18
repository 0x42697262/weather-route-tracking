"""Seed rule set version 1 from the defaults, validated by the one validator, and activate it."""

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.utils import timezone

from rulesets.domain.defaults import default_rule_set_document
from rulesets.domain.validator import validate_rule_set
from rulesets.text import SEED_NOTE

SEED_VERSION = 1


def seed_version_one(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:  # noqa: ARG001
    """Create and activate version 1 unless any version exists."""
    rule_set_version = apps.get_model("rulesets", "RuleSetVersion")
    if rule_set_version.objects.exists():
        return
    document = default_rule_set_document()
    validate_rule_set(document)
    now = timezone.now()
    rule_set_version.objects.create(
        version=SEED_VERSION,
        data=document,
        note=SEED_NOTE,
        is_active=True,
        created_at=now,
        activated_at=now,
    )


class Migration(migrations.Migration):
    dependencies = [("rulesets", "0001_initial")]

    operations = [migrations.RunPython(seed_version_one, migrations.RunPython.noop)]
