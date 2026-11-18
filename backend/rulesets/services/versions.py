"""Creating and activating rule set versions. The admin screens call these."""

import logging

from django.contrib.auth.base_user import AbstractBaseUser
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from rulesets.domain.validator import RuleSetInvalid, validate_rule_set
from rulesets.events import RULE_SET_ACTIVATED, RULE_SET_CREATED, RULE_SET_REJECTED
from rulesets.models import RuleSetVersion

logger = logging.getLogger(__name__)

FIRST_VERSION = 1


class RuleSetVersionNotFound(Exception):
    """No version has the given number."""


def _user_id(user: AbstractBaseUser | None) -> int | str | None:
    return None if user is None else user.pk


def save_new_version(version: RuleSetVersion, user: AbstractBaseUser | None) -> RuleSetVersion:
    """Validate an unsaved version, give it the next number and insert it, inactive.

    Raises:
        RuleSetInvalid: the document is not a valid rule set.
    """
    try:
        validate_rule_set(version.data)
    except RuleSetInvalid as invalid:
        logger.info(RULE_SET_REJECTED, extra={"problem_count": len(invalid.problems)})
        raise
    with transaction.atomic():
        latest = RuleSetVersion.objects.aggregate(latest=Max("version"))["latest"]
        version.version = FIRST_VERSION if latest is None else latest + 1
        version.created_by_id = _user_id(user)
        version.is_active = False
        version.save()
    logger.info(RULE_SET_CREATED, extra={"version": version.version, "user_id": _user_id(user)})
    return version


def create_version(data: object, note: str, user: AbstractBaseUser | None) -> RuleSetVersion:
    """Create a new inactive version from a document.

    Raises:
        RuleSetInvalid: the document is not a valid rule set.
    """
    return save_new_version(RuleSetVersion(data=data, note=note), user)


def activate_version(version: int, user: AbstractBaseUser | None) -> RuleSetVersion:
    """Make one version the only active one, recording who activated it and when.

    Raises:
        RuleSetVersionNotFound: no version has that number.
    """
    with transaction.atomic():
        target = RuleSetVersion.objects.select_for_update().filter(version=version).first()
        if target is None:
            raise RuleSetVersionNotFound(version)
        RuleSetVersion.objects.filter(is_active=True).exclude(pk=target.pk).update(is_active=False)
        target.is_active = True
        target.activated_by_id = _user_id(user)
        target.activated_at = timezone.now()
        target.save(update_fields=["is_active", "activated_by", "activated_at"])
    logger.info(RULE_SET_ACTIVATED, extra={"version": version, "user_id": _user_id(user)})
    return target
