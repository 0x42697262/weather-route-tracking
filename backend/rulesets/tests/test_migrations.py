import importlib

import pytest
from django.apps import apps
from django.utils import timezone

from rulesets.domain.defaults import default_rule_set_document
from rulesets.models import RuleSetVersion

upgrade = importlib.import_module("rulesets.migrations.0003_add_max_unknown_share")


def _schema_one_document() -> dict[str, object]:
    document = default_rule_set_document()
    del document["max_unknown_share"]
    document["schema_version"] = 1
    document["truck_speed_factor"] = 1.1
    return document


@pytest.mark.django_db
def test_active_schema_one_version_is_upgraded_into_a_new_active_version() -> None:
    RuleSetVersion.objects.all().delete()
    now = timezone.now()
    RuleSetVersion.objects.create(
        version=3, data=_schema_one_document(), note="", is_active=True, created_at=now
    )

    upgrade.publish_upgraded_version(apps, None)

    old = RuleSetVersion.objects.get(version=3)
    new = RuleSetVersion.objects.get(is_active=True)
    assert old.is_active is False
    assert old.data["schema_version"] == 1
    assert new.version == 4
    assert new.data["schema_version"] == 2
    assert new.data["max_unknown_share"] == 0.25
    assert new.data["truck_speed_factor"] == 1.1


@pytest.mark.django_db
def test_active_schema_two_version_is_left_alone() -> None:
    before = list(RuleSetVersion.objects.values_list("version", "is_active"))

    upgrade.publish_upgraded_version(apps, None)

    assert list(RuleSetVersion.objects.values_list("version", "is_active")) == before
