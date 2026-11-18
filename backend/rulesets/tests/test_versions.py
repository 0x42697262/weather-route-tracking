import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction

from planning.errors import NoActiveRuleSet
from rulesets.domain.defaults import default_rule_set_document
from rulesets.domain.validator import RuleSetInvalid
from rulesets.models import RuleSetVersion, RuleSetVersionImmutable
from rulesets.services.active import get_active_rule_set, has_active_rule_set
from rulesets.services.versions import (
    RuleSetVersionNotFound,
    activate_version,
    create_version,
)

pytestmark = pytest.mark.django_db


def _faster_document() -> dict[str, object]:
    document = default_rule_set_document()
    document["truck_speed_factor"] = 1.1
    return document


def _active_versions() -> list[int]:
    return list(RuleSetVersion.objects.filter(is_active=True).values_list("version", flat=True))


def test_version_one_is_seeded_active_from_the_defaults() -> None:
    seeded = RuleSetVersion.objects.get()

    assert seeded.version == 1
    assert seeded.is_active is True
    assert seeded.data == default_rule_set_document()
    assert seeded.activated_at is not None


def test_create_version_numbers_it_and_leaves_it_inactive(admin_user: User) -> None:
    created = create_version(_faster_document(), "faster trucks", admin_user)

    assert created.version == 2
    assert created.is_active is False
    assert created.created_by == admin_user
    assert _active_versions() == [1]


def test_create_version_rejects_an_invalid_document() -> None:
    document = default_rule_set_document()
    document["truck_speed_factor"] = 9

    with pytest.raises(RuleSetInvalid):
        create_version(document, "", None)

    assert RuleSetVersion.objects.count() == 1


def test_activation_leaves_exactly_one_active(admin_user: User) -> None:
    create_version(_faster_document(), "", None)

    activated = activate_version(2, admin_user)

    assert _active_versions() == [2]
    assert activated.activated_by == admin_user
    assert activated.activated_at is not None
    activate_version(1, admin_user)
    assert _active_versions() == [1]


def test_activating_an_unknown_version_fails() -> None:
    with pytest.raises(RuleSetVersionNotFound):
        activate_version(99, None)


def test_the_database_allows_only_one_active_version() -> None:
    create_version(_faster_document(), "", None)

    with pytest.raises(IntegrityError), transaction.atomic():
        RuleSetVersion.objects.filter(version=2).update(is_active=True)


@pytest.mark.parametrize("update_fields", [None, ["note"], ["data", "is_active"]])
def test_a_saved_version_cannot_be_edited(update_fields: list[str] | None) -> None:
    seeded = RuleSetVersion.objects.get()
    seeded.note = "changed"

    with pytest.raises(RuleSetVersionImmutable):
        seeded.save(update_fields=update_fields)

    assert RuleSetVersion.objects.get().note != "changed"


def test_active_rule_set_is_version_one_in_metric() -> None:
    versioned = async_to_sync(get_active_rule_set)()

    assert versioned.version == 1
    assert versioned.rules.truck_speed_factor == 1.0
    assert async_to_sync(has_active_rule_set)() is True


def test_activating_another_version_needs_no_cache_flush() -> None:
    async_to_sync(get_active_rule_set)()
    create_version(_faster_document(), "", None)
    activate_version(2, None)

    versioned = async_to_sync(get_active_rule_set)()

    assert versioned.version == 2
    assert versioned.rules.truck_speed_factor == 1.1


def test_no_active_version_is_a_named_error() -> None:
    RuleSetVersion.objects.all().update(is_active=False)

    assert async_to_sync(has_active_rule_set)() is False
    with pytest.raises(NoActiveRuleSet):
        async_to_sync(get_active_rule_set)()
