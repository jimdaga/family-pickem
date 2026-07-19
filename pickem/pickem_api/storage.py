"""Dedicated storage settings for server-generated family logo assets."""

import os

from django.conf import settings
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
        super().__init__(*args, **kwargs)
        self._local_storage = None
        if not getattr(settings, "AWS_STORAGE_BUCKET_NAME", None):
            self._local_storage = FileSystemStorage(
                location=os.path.join(settings.MEDIA_ROOT, self.location),
                base_url=f"{settings.MEDIA_URL}{self.location}/",
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
        return super().url(name, parameters=parameters, expire=expire, http_method=http_method)
