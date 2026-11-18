import json
from http import HTTPStatus

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from rulesets.domain.defaults import default_rule_set_document
from rulesets.keys import ACTION_ACTIVATE
from rulesets.models import RuleSetVersion
from rulesets.services.versions import create_version

pytestmark = pytest.mark.django_db

ADD_URL = "admin:rulesets_rulesetversion_add"
LIST_URL = "admin:rulesets_rulesetversion_changelist"
CHANGE_URL = "admin:rulesets_rulesetversion_change"
DELETE_URL = "admin:rulesets_rulesetversion_delete"


def _active_versions() -> list[int]:
    return list(RuleSetVersion.objects.filter(is_active=True).values_list("version", flat=True))


def test_add_form_is_prefilled_with_the_active_document(admin_client: Client) -> None:
    response = admin_client.get(reverse(ADD_URL))

    assert response.status_code == HTTPStatus.OK
    assert "\n  &quot;schema_version&quot;: 2," in response.content.decode()


def test_adding_a_valid_document_creates_an_inactive_version(
    admin_client: Client, admin_user: User
) -> None:
    document = default_rule_set_document()
    document["truck_speed_factor"] = 1.1

    response = admin_client.post(reverse(ADD_URL), {"data": json.dumps(document), "note": "faster"})

    assert response.status_code == HTTPStatus.FOUND
    created = RuleSetVersion.objects.get(version=2)
    assert created.is_active is False
    assert created.created_by == admin_user
    assert created.note == "faster"
    assert _active_versions() == [1]


def test_adding_an_invalid_document_shows_every_problem(admin_client: Client) -> None:
    document = default_rule_set_document()
    document["truck_speed_factor"] = 9
    document["ferry_level"] = "calm"

    response = admin_client.post(reverse(ADD_URL), {"data": json.dumps(document), "note": ""})

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "truck_speed_factor: Must be between 0.5 and 1.5." in page
    assert "ferry_level: Must be one of:" in page
    assert RuleSetVersion.objects.count() == 1


def test_adding_text_that_is_not_json_is_rejected(admin_client: Client) -> None:
    response = admin_client.post(reverse(ADD_URL), {"data": "{not json", "note": ""})

    assert response.status_code == HTTPStatus.OK
    assert RuleSetVersion.objects.count() == 1


def test_activate_action_leaves_exactly_one_active(admin_client: Client, admin_user: User) -> None:
    created = create_version(default_rule_set_document(), "", None)

    response = admin_client.post(
        reverse(LIST_URL), {"action": ACTION_ACTIVATE, "_selected_action": [created.pk]}
    )

    assert response.status_code == HTTPStatus.FOUND
    assert _active_versions() == [2]
    assert RuleSetVersion.objects.get(version=2).activated_by == admin_user


def test_activate_action_needs_exactly_one_selection(admin_client: Client) -> None:
    created = create_version(default_rule_set_document(), "", None)
    seeded = RuleSetVersion.objects.get(version=1)

    admin_client.post(
        reverse(LIST_URL),
        {"action": ACTION_ACTIVATE, "_selected_action": [created.pk, seeded.pk]},
    )

    assert _active_versions() == [1]


def test_a_saved_version_opens_read_only(admin_client: Client) -> None:
    seeded = RuleSetVersion.objects.get()
    url = reverse(CHANGE_URL, args=[seeded.pk])

    page = admin_client.get(url)
    edit = admin_client.post(url, {"data": "{}", "note": "changed"})

    assert page.status_code == HTTPStatus.OK
    assert 'name="_save"' not in page.content.decode()
    assert edit.status_code == HTTPStatus.FORBIDDEN
    assert RuleSetVersion.objects.get().note != "changed"


def test_a_version_cannot_be_deleted(admin_client: Client) -> None:
    seeded = RuleSetVersion.objects.get()

    response = admin_client.post(reverse(DELETE_URL, args=[seeded.pk]), {"post": "yes"})

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert RuleSetVersion.objects.count() == 1
