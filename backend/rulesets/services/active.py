"""The active rule set: looked up per call, validated once per version and cached."""

import logging

from django.core.cache import cache

from planning.errors import NoActiveRuleSet
from rulesets.constants import RULE_SET_CACHE_TTL_S
from rulesets.domain.schema import VersionedRuleSet
from rulesets.domain.validator import validate_rule_set
from rulesets.keys import rule_set_cache_key
from rulesets.models import RuleSetVersion

logger = logging.getLogger(__name__)


async def has_active_rule_set() -> bool:
    """True when a version is active."""
    return await RuleSetVersion.objects.filter(is_active=True).aexists()


async def get_active_rule_set() -> VersionedRuleSet:
    """The active version, validated and in metric units.

    The active version number is read on every call; the validated rule set is cached under a
    key holding that version, so activating another version needs no cache flush.

    Raises:
        NoActiveRuleSet: no version is active.
        RuleSetInvalid: the stored document no longer validates (for example an unknown schema
            version after a rollback of the code).
    """
    active = (
        await RuleSetVersion.objects.filter(is_active=True)
        .values_list("version", "created_at")
        .afirst()
    )
    if active is None:
        raise NoActiveRuleSet
    version, created_at = active
    key = rule_set_cache_key(version, created_at.isoformat())
    cached = await cache.aget(key)
    if isinstance(cached, VersionedRuleSet):
        return cached
    stored = RuleSetVersion.objects.filter(version=version).values_list("data", flat=True)
    data = await stored.aget()
    versioned = VersionedRuleSet(version=version, rules=validate_rule_set(data))
    await cache.aset(key, versioned, RULE_SET_CACHE_TTL_S)
    return versioned
