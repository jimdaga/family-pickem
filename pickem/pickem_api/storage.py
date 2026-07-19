"""Dedicated storage settings for server-generated family logo assets."""

import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage

from storages.backends.s3boto3 import S3Boto3Storage


class FamilyLogoStorage(S3Boto3Storage):
    """Keep generated logos private in S3, with an isolated local-dev fallback."""

    location = "family-logos"
    default_acl = None
    file_overwrite = False
    querystring_auth = True
    object_parameters = {
        "ContentType": "image/webp",
        "CacheControl": "private, max-age=31536000, immutable",
    }

    def __init__(self, *args, **kwargs):
        self._local_storage = None
        logo_settings = {
            "bucket_name": getattr(settings, "FAMILY_LOGO_STORAGE_BUCKET_NAME", ""),
            "region_name": getattr(settings, "FAMILY_LOGO_AWS_S3_REGION_NAME", ""),
            "access_key": getattr(settings, "FAMILY_LOGO_AWS_ACCESS_KEY_ID", ""),
            "secret_key": getattr(settings, "FAMILY_LOGO_AWS_SECRET_ACCESS_KEY", ""),
        }
        configured_values = tuple(logo_settings.values())
        if any(configured_values) and not all(configured_values):
            raise ImproperlyConfigured(
                "Family logo S3 storage requires all FAMILY_LOGO_* credential settings."
            )

        if not any(configured_values):
            self._local_storage = FileSystemStorage(
                location=os.path.join(settings.MEDIA_ROOT, self.location),
                base_url=f"{settings.MEDIA_URL}{self.location}/",
            )
            return

        querystring_expire = getattr(settings, "FAMILY_LOGO_AWS_QUERYSTRING_EXPIRE", 300)
        if not isinstance(querystring_expire, int) or querystring_expire <= 0:
            raise ImproperlyConfigured(
                "FAMILY_LOGO_AWS_QUERYSTRING_EXPIRE must be a positive integer."
            )
        super().__init__(
            *args,
            **logo_settings,
            querystring_expire=querystring_expire,
            **kwargs,
        )

    def _open(self, name, mode="rb"):
        if self._local_storage:
            return self._local_storage._open(name, mode)
        return super()._open(name, mode)

    def _save(self, name, content):
        if self._local_storage:
            return self._local_storage._save(name, content)
        return super()._save(name, content)

    def delete(self, name):
        if self._local_storage:
            return self._local_storage.delete(name)
        return super().delete(name)

    def exists(self, name):
        if self._local_storage:
            return self._local_storage.exists(name)
        return super().exists(name)

    def listdir(self, path):
        if self._local_storage:
            return self._local_storage.listdir(path)
        return super().listdir(path)

    def size(self, name):
        if self._local_storage:
            return self._local_storage.size(name)
        return super().size(name)

    def url(self, name, parameters=None, expire=None, http_method=None):
        if self._local_storage:
            return self._local_storage.url(name)
        return super().url(
            name,
            parameters=parameters,
            expire=self.querystring_expire,
            http_method=http_method,
        )
