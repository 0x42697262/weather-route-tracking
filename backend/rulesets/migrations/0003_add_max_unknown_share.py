"""Upgrade an active schema-1 rule set to schema 2 by publishing a new version with
`max_unknown_share` set to the default; earlier versions stay as they were."""

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.utils import timezone

from rulesets.constants import CURRENT_SCHEMA_VERSION, FIRST_SCHEMA_VERSION
from rulesets.domain.defaults import default_rule_set_document
from rulesets.domain.validator import validate_rule_set
from rulesets.keys import Key
from rulesets.text import UNKNOWN_SHARE_UPGRADE_NOTE


def publish_upgraded_version(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:  # noqa: ARG001
    """Publish and activate the active version's document with the new field, if it is schema 1."""
    rule_set_version = apps.get_model("rulesets", "RuleSetVersion")
    active = rule_set_version.objects.filter(is_active=True).first()
    if active is None or active.data.get(Key.SCHEMA_VERSION) != FIRST_SCHEMA_VERSION:
        return
    document = dict(active.data)
    document[Key.SCHEMA_VERSION] = CURRENT_SCHEMA_VERSION
    document[Key.MAX_UNKNOWN_SHARE] = default_rule_set_document()[Key.MAX_UNKNOWN_SHARE]
    validate_rule_set(document)
    latest_version = max(rule_set_version.objects.values_list("version", flat=True))
    now = timezone.now()
    rule_set_version.objects.filter(pk=active.pk).update(is_active=False)
    rule_set_version.objects.create(
        version=latest_version + 1,
        data=document,
        note=UNKNOWN_SHARE_UPGRADE_NOTE,
        is_active=True,
        created_at=now,
        activated_at=now,
    )


class Migration(migrations.Migration):
    dependencies = [("rulesets", "0002_seed_version_one")]

    operations = [migrations.RunPython(publish_upgraded_version, migrations.RunPython.noop)]
