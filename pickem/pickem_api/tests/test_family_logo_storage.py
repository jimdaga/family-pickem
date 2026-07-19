from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from pickem_api.models import Family, family_logo_upload_to
from pickem_api.storage import FamilyLogoStorage


class FamilyLogoStorageTests(TestCase):
    def test_generated_logo_key_uses_family_id_and_ignores_browser_filename(self):
        family = Family.objects.create(name="Storage Family", slug="storage-family")

        with patch("pickem_api.models.uuid.uuid4") as mock_uuid:
            mock_uuid.return_value.hex = "a" * 32
            generated_name = family_logo_upload_to(family, "../../untrusted-source.png")

        self.assertEqual(generated_name, f"{family.pk}/{'a' * 32}.webp")
        self.assertNotIn("untrusted-source", generated_name)
        self.assertEqual(
            f"{FamilyLogoStorage.location}/{generated_name}",
            f"family-logos/{family.pk}/{'a' * 32}.webp",
        )

    def test_storage_contract_is_private_signed_and_webp_only(self):
        storage = FamilyLogoStorage()

        self.assertEqual(storage.location, "family-logos")
        self.assertIsNone(storage.default_acl)
        self.assertFalse(storage.file_overwrite)
        self.assertTrue(storage.querystring_auth)
        self.assertEqual(storage.get_object_parameters("ignored.webp"), {
            "ContentType": "image/webp",
            "CacheControl": "private, max-age=31536000, immutable",
        })

    @override_settings(AWS_STORAGE_BUCKET_NAME="", MEDIA_ROOT="/tmp/family-pickem-logo-test-media")
    def test_without_a_bucket_storage_uses_local_media_urls(self):
        storage = FamilyLogoStorage()
        name = storage.save("test-logo.webp", ContentFile(b"webp"))
        self.addCleanup(storage.delete, name)

        self.assertTrue(storage.exists(name))
        self.assertEqual(storage.url(name), "/media/family-logos/test-logo.webp")

    @override_settings(
        FAMILY_LOGO_STORAGE_BUCKET_NAME="family-pickem",
        FAMILY_LOGO_AWS_S3_REGION_NAME="us-east-1",
        FAMILY_LOGO_AWS_ACCESS_KEY_ID="logo-key",
        FAMILY_LOGO_AWS_SECRET_ACCESS_KEY="logo-secret",
        FAMILY_LOGO_AWS_QUERYSTRING_EXPIRE=300,
    )
    @patch("pickem_api.storage.S3Boto3Storage.__init__", return_value=None)
    def test_complete_logo_configuration_uses_only_dedicated_credentials(self, mock_init):
        FamilyLogoStorage()

        self.assertEqual(mock_init.call_count, 1)
        self.assertEqual(mock_init.call_args.kwargs, {
            "bucket_name": "family-pickem",
            "region_name": "us-east-1",
            "access_key": "logo-key",
            "secret_key": "logo-secret",
            "querystring_expire": 300,
        })

    @override_settings(
        AWS_STORAGE_BUCKET_NAME="generic-bucket",
        AWS_S3_REGION_NAME="us-east-1",
        AWS_ACCESS_KEY_ID="generic-key",
        AWS_SECRET_ACCESS_KEY="generic-secret",
        FAMILY_LOGO_STORAGE_BUCKET_NAME="",
        FAMILY_LOGO_AWS_S3_REGION_NAME="",
        FAMILY_LOGO_AWS_ACCESS_KEY_ID="",
        FAMILY_LOGO_AWS_SECRET_ACCESS_KEY="",
    )
    def test_generic_aws_credentials_do_not_enable_logo_s3_storage(self):
        storage = FamilyLogoStorage()

        self.assertIsNotNone(storage._local_storage)

    @override_settings(
        FAMILY_LOGO_STORAGE_BUCKET_NAME="family-pickem",
        FAMILY_LOGO_AWS_S3_REGION_NAME="",
        FAMILY_LOGO_AWS_ACCESS_KEY_ID="logo-key",
        FAMILY_LOGO_AWS_SECRET_ACCESS_KEY="logo-secret",
    )
    def test_partial_logo_configuration_fails_closed(self):
        with self.assertRaises(ImproperlyConfigured):
            FamilyLogoStorage()

    @override_settings(
        FAMILY_LOGO_STORAGE_BUCKET_NAME="family-pickem",
        FAMILY_LOGO_AWS_S3_REGION_NAME="us-east-1",
        FAMILY_LOGO_AWS_ACCESS_KEY_ID="logo-key",
        FAMILY_LOGO_AWS_SECRET_ACCESS_KEY="logo-secret",
        FAMILY_LOGO_AWS_QUERYSTRING_EXPIRE=300,
    )
    @patch("pickem_api.storage.S3Boto3Storage.url", return_value="https://example.test/signed")
    def test_s3_urls_always_use_fixed_five_minute_expiry(self, mock_url):
        storage = FamilyLogoStorage()

        self.assertEqual(storage.url("123/logo.webp", expire=1), "https://example.test/signed")
        self.assertEqual(mock_url.call_args.kwargs["expire"], 300)
