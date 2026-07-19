from unittest.mock import patch

from django.core.files.base import ContentFile
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
