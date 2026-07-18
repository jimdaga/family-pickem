from io import BytesIO
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image, PngImagePlugin

from pickem_api.logo_processing import (
    MAX_INPUT_PIXELS,
    MAX_UPLOAD_BYTES,
    LogoValidationError,
    process_family_logo,
    validate_square_crop,
)


def image_bytes(image_format, size=(400, 300), **save_kwargs):
    image = Image.new("RGB", size, "navy")
    output = BytesIO()
    image.save(output, format=image_format, **save_kwargs)
    return output.getvalue()


class FamilyLogoProcessorTests(SimpleTestCase):
    def uploaded_image(self, image_format, *, name="logo.bin", content_type="text/plain", **kwargs):
        return SimpleUploadedFile(
            name,
            image_bytes(image_format, **kwargs),
            content_type=content_type,
        )

    def assert_validation_code(self, expected_code, uploaded_file, crop_data=None):
        with self.assertRaises(LogoValidationError) as raised:
            process_family_logo(uploaded_file, crop_data=crop_data)
        self.assertEqual(raised.exception.code, expected_code)

    def test_decoder_verified_jpeg_png_and_webp_become_fresh_webp(self):
        for image_format in ("JPEG", "PNG", "WEBP"):
            with self.subTest(image_format=image_format):
                result = process_family_logo(
                    self.uploaded_image(image_format, name="misleading.exe")
                )

                self.assertEqual(result.name, "family-logo.webp")
                self.assertEqual(result.content_type, "image/webp")
                self.assertNotIn(b"misleading.exe", result.read())
                result.seek(0)
                with Image.open(result) as output:
                    self.assertEqual(output.format, "WEBP")
                    self.assertEqual(output.size, (256, 256))

    def test_browser_filename_and_claimed_mime_do_not_grant_acceptance(self):
        html = SimpleUploadedFile(
            "logo.png", b"<script>alert('not an image')</script>", content_type="image/png"
        )
        self.assert_validation_code("invalid_image", html)

        random_bytes = SimpleUploadedFile(
            "logo.webp", b"\x00\x01\x02not-a-raster", content_type="image/webp"
        )
        self.assert_validation_code("invalid_image", random_bytes)

    def test_unsupported_and_truncated_rasters_are_rejected(self):
        gif = SimpleUploadedFile("logo.jpg", image_bytes("GIF"), content_type="image/jpeg")
        svg = SimpleUploadedFile("logo.webp", b"<svg xmlns='http://www.w3.org/2000/svg'/>")
        truncated_png = SimpleUploadedFile("logo.png", image_bytes("PNG")[:-12])

        for uploaded_file in (gif, svg, truncated_png):
            with self.subTest(name=uploaded_file.name):
                self.assert_validation_code("invalid_image", uploaded_file)

    def test_source_byte_limit_is_enforced_before_decoding(self):
        too_large = SimpleUploadedFile(
            "logo.jpg", b"x" * (MAX_UPLOAD_BYTES + 1), content_type="image/jpeg"
        )

        self.assert_validation_code("file_too_large", too_large)

    def test_header_advertised_pixel_limit_rejects_before_load_or_transform(self):
        probe = MagicMock()
        probe.format = "PNG"
        probe.__enter__.return_value = probe
        reopened = MagicMock()
        reopened.format = "PNG"
        reopened.width = MAX_INPUT_PIXELS + 1
        reopened.height = 1
        reopened.__enter__.return_value = reopened

        uploaded_file = self.uploaded_image("PNG")
        with patch("pickem_api.logo_processing.Image.open", side_effect=[probe, reopened]):
            self.assert_validation_code("too_many_pixels", uploaded_file)

        probe.verify.assert_called_once_with()
        reopened.load.assert_not_called()
        reopened.crop.assert_not_called()
        reopened.resize.assert_not_called()

    def test_crop_contract_requires_strict_bounded_square_integer_rectangle(self):
        valid_crop = {"x": "20", "y": "10", "width": "100", "height": "100"}
        self.assertEqual(validate_square_crop(valid_crop, (400, 300)), (20, 10, 120, 110))

        invalid_crops = (
            {"x": 0, "y": 0, "width": 10},
            {"x": True, "y": 0, "width": 10, "height": 10},
            {"x": 0.0, "y": 0, "width": 10, "height": 10},
            {"x": "1e2", "y": 0, "width": 10, "height": 10},
            {"x": 0, "y": 0, "width": 0, "height": 0},
            {"x": -1, "y": 0, "width": 10, "height": 10},
            {"x": 390, "y": 0, "width": 20, "height": 20},
            {"x": 0, "y": 0, "width": 10, "height": 9},
        )
        for crop in invalid_crops:
            with self.subTest(crop=crop):
                with self.assertRaises(LogoValidationError) as raised:
                    validate_square_crop(crop, (400, 300))
                self.assertEqual(raised.exception.code, "invalid_crop")

    def test_default_crop_is_center_square(self):
        result = process_family_logo(self.uploaded_image("PNG", size=(400, 200)))
        with Image.open(result) as output:
            self.assertEqual(output.size, (256, 256))

    def test_fresh_webp_omits_source_png_text_metadata(self):
        png_info = PngImagePlugin.PngInfo()
        png_info.add_text("untrusted-sentinel", "do-not-copy")
        uploaded_file = SimpleUploadedFile(
            "logo.png", image_bytes("PNG", pnginfo=png_info), content_type="image/png"
        )

        result = process_family_logo(uploaded_file)
        with Image.open(result) as output:
            self.assertNotIn("untrusted-sentinel", output.info)
            self.assertNotIn("do-not-copy", output.info.values())
