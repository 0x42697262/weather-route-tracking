"""Rule set storage: one immutable row per version, at most one active (`docs/rule-sets.md`)."""

import logging
from collections.abc import Iterable
from typing import ClassVar, Final

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from rulesets import text
from rulesets.constants import NOTE_MAX_LENGTH
from rulesets.domain.validator import RuleSetInvalid, validate_rule_set
from rulesets.events import RULE_SET_REJECTED
from rulesets.keys import ACTIVATE_PERMISSION

logger = logging.getLogger(__name__)

ACTIVATION_FIELDS: Final = frozenset({"is_active", "activated_by", "activated_at"})
ONE_ACTIVE_CONSTRAINT: Final = "rulesets_one_active_version"


class RuleSetVersionImmutable(Exception):
    """A saved version's document, number or note was about to change."""


class RuleSetVersion(models.Model):
    """One version of the business rules. The document keeps the units staff entered."""

    version = models.PositiveIntegerField(unique=True)
    data = models.JSONField()
    note = models.CharField(max_length=NOTE_MAX_LENGTH, blank=True)
    is_active = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering: ClassVar = ["-version"]
        verbose_name = text.VERBOSE_NAME
        verbose_name_plural = text.VERBOSE_NAME_PLURAL
        permissions: ClassVar = [(ACTIVATE_PERMISSION, text.ACTIVATE_PERMISSION_NAME)]
        constraints: ClassVar = [
            models.UniqueConstraint(
                fields=["is_active"],
                condition=models.Q(is_active=True),
                name=ONE_ACTIVE_CONSTRAINT,
            ),
        ]

    def __str__(self) -> str:
        """The version as admin names it."""
        return text.version_label(self.version)

    def save(
        self,
        *,
        force_insert: bool | tuple[models.base.ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        """Insert a new version, or update only its activation fields.

        Raises:
            RuleSetVersionImmutable: an update of a saved version touches other fields.
        """
        is_update = not self._state.adding
        if is_update and (update_fields is None or not ACTIVATION_FIELDS.issuperset(update_fields)):
            raise RuleSetVersionImmutable(text.VERSION_IMMUTABLE)
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def clean(self) -> None:
        """Run the rule set validator; every problem is reported on the `data` field."""
        try:
            validate_rule_set(self.data)
        except RuleSetInvalid as invalid:
            logger.info(RULE_SET_REJECTED, extra={"problem_count": len(invalid.problems)})
            raise ValidationError(
                {
                    "data": [
                        text.problem_line(problem.field, problem.message)
                        for problem in invalid.problems
                    ]
                }
            ) from invalid
