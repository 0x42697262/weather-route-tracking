"""Admin screens for rule set versions: list, add (validated), read-only view and activation."""

import json
from typing import TYPE_CHECKING, ClassVar, cast

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.base_user import AbstractBaseUser
from django.db.models import QuerySet
from django.forms.fields import InvalidJSONInput
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.safestring import SafeString

from rulesets import text
from rulesets.constants import ADMIN_JSON_INDENT
from rulesets.keys import ACTION_ACTIVATE, ACTIVATE_PERMISSION
from rulesets.models import RuleSetVersion
from rulesets.services.versions import activate_version, save_new_version

ADD_FIELDS = ("data", "note")
VIEW_FIELDS = (
    "version",
    "note",
    "is_active",
    "created_by",
    "created_at",
    "activated_by",
    "activated_at",
    "document",
)
DOCUMENT_ROWS = 40
DOCUMENT_COLUMNS = 100
DOCUMENT_HTML = "<pre>{}</pre>"


if TYPE_CHECKING:
    _RuleSetVersionModelForm = forms.ModelForm[RuleSetVersion]
    _RuleSetVersionModelAdmin = admin.ModelAdmin[RuleSetVersion]
else:
    _RuleSetVersionModelForm = forms.ModelForm
    _RuleSetVersionModelAdmin = admin.ModelAdmin


class PrettyJSONField(forms.JSONField):
    """A JSON form field that shows its value indented."""

    def prepare_value(self, value: object) -> str:
        """The value as indented JSON, or the raw text when it did not parse."""
        if isinstance(value, InvalidJSONInput):
            return value
        return json.dumps(value, indent=ADMIN_JSON_INDENT, ensure_ascii=False)


class RuleSetVersionForm(_RuleSetVersionModelForm):
    """The add form: a document and a note. `RuleSetVersion.clean` runs the validator."""

    class Meta:
        model = RuleSetVersion
        fields = ADD_FIELDS
        field_classes: ClassVar = {"data": PrettyJSONField}
        widgets: ClassVar = {
            "data": forms.Textarea(attrs={"rows": DOCUMENT_ROWS, "cols": DOCUMENT_COLUMNS})
        }
        help_texts: ClassVar = {"data": text.ADMIN_DATA_HELP}


def _staff_user(request: HttpRequest) -> AbstractBaseUser | None:
    user = request.user
    return user if isinstance(user, AbstractBaseUser) else None


@admin.register(RuleSetVersion)
class RuleSetVersionAdmin(_RuleSetVersionModelAdmin):
    """Versions are added and activated, never edited or deleted."""

    form = RuleSetVersionForm
    list_display = (
        "version",
        "note",
        "is_active",
        "created_by",
        "created_at",
        "activated_by",
        "activated_at",
    )
    list_select_related = ("created_by", "activated_by")
    actions = (ACTION_ACTIVATE,)

    def get_fields(
        self,
        request: HttpRequest,  # noqa: ARG002
        obj: RuleSetVersion | None = None,
    ) -> tuple[str, ...]:
        """The add form shows the document and note; a saved version shows everything."""
        return ADD_FIELDS if obj is None else VIEW_FIELDS

    def get_readonly_fields(
        self,
        request: HttpRequest,  # noqa: ARG002
        obj: RuleSetVersion | None = None,
    ) -> tuple[str, ...]:
        """Nothing is editable on a saved version."""
        return () if obj is None else VIEW_FIELDS

    def get_changeform_initial_data(
        self,
        request: HttpRequest,  # noqa: ARG002
    ) -> dict[str, str | list[str]]:
        """Pre-fill the add form with the active version's document.

        The document is a JSON object, not a string; the form field indents it for display.
        """
        active = RuleSetVersion.objects.filter(is_active=True).only("data").first()
        initial = {} if active is None else {"data": active.data}
        return cast("dict[str, str | list[str]]", initial)

    def has_change_permission(
        self,
        request: HttpRequest,  # noqa: ARG002
        obj: RuleSetVersion | None = None,  # noqa: ARG002
    ) -> bool:
        """Saved versions are immutable."""
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,  # noqa: ARG002
        obj: RuleSetVersion | None = None,  # noqa: ARG002
    ) -> bool:
        """Versions are never deleted, so every past result stays traceable."""
        return False

    def has_activate_permission(self, request: HttpRequest) -> bool:
        """The user may activate versions."""
        return request.user.has_perm(f"{self.opts.app_label}.{ACTIVATE_PERMISSION}")

    def save_model(
        self,
        request: HttpRequest,
        obj: RuleSetVersion,
        form: _RuleSetVersionModelForm,  # noqa: ARG002
        change: bool,  # noqa: ARG002, FBT001
    ) -> None:
        """Insert the new version through the service, which numbers it."""
        save_new_version(obj, _staff_user(request))

    @admin.display(description=text.DOCUMENT_LABEL)
    def document(self, obj: RuleSetVersion) -> SafeString:
        """The stored document, indented."""
        return format_html(
            DOCUMENT_HTML, json.dumps(obj.data, indent=ADMIN_JSON_INDENT, ensure_ascii=False)
        )

    @admin.action(description=text.ADMIN_ACTIVATE_DESCRIPTION, permissions=[ACTION_ACTIVATE])
    def activate(self, request: HttpRequest, queryset: QuerySet[RuleSetVersion]) -> None:
        """Activate the one selected version."""
        if queryset.count() != 1:
            self.message_user(request, text.ADMIN_ACTIVATE_EXACTLY_ONE, messages.ERROR)
            return
        activated = activate_version(queryset.get().version, _staff_user(request))
        message = text.admin_activated(activated.version)
        self.log_change(request, activated, message)
        self.message_user(request, message, messages.SUCCESS)
