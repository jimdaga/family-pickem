"""Dedicated storage settings for server-generated family logo assets."""

from storages.backends.s3boto3 import S3Boto3Storage


class FamilyLogoStorage(S3Boto3Storage):
    """Keep processed family logos private and separate from generic assets."""

    location = "family-logos"
    default_acl = None
    file_overwrite = False
    querystring_auth = True
    object_parameters = {
        "ContentType": "image/webp",
        "CacheControl": "private, max-age=31536000, immutable",
    }
