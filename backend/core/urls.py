"""URL routes: the staff admin at `ADMIN_URL` and the API at `/api/`."""

from django.conf import settings
from django.contrib import admin
from django.urls import path

from core.api import api
from core.keys import API_PREFIX

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path(API_PREFIX, api.urls),
]
