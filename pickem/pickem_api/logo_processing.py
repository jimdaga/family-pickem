"""Fail-closed canonicalization for family logo uploads.

This module intentionally has no model, storage, or HTTP dependencies.  It
turns only decoder-proven raster inputs into a generated 256px WebP file.
"""

from io import BytesIO
import warnings

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError


ALLOWED_FORMATS = ("JPEG", "PNG", "WEBP")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_INPUT_PIXELS = 16_000_000
OUTPUT_SIZE = 256


class LogoValidationError(Exception):
    """A safe validation failure that can be rendered without decoder details."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _strict_integer(value):
    if isinstance(value, bool):
        raise LogoValidationError("invalid_crop")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    raise LogoValidationError("invalid_crop")


def validate_square_crop(crop_data, image_size):
    """Return a bounded Pillow crop box for an explicit square crop request."""
    if not isinstance(crop_data, dict):
        raise LogoValidationError("invalid_crop")

    try:
        x, y, width, height = (
            _strict_integer(crop_data[field])
            for field in ("x", "y", "width", "height")
        )
    except KeyError as error:
        raise LogoValidationError("invalid_crop") from error

    source_width, source_height = image_size
    if (
        x < 0
        or y < 0
        or width <= 0
        or height <= 0
        or width != height
        or x + width > source_width
        or y + height > source_height
    ):
        raise LogoValidationError("invalid_crop")
    return x, y, x + width, y + height


def _rewind(uploaded_file):
    try:
        uploaded_file.seek(0)
    except (AttributeError, OSError, ValueError) as error:
        raise LogoValidationError("invalid_image") from error


def process_family_logo(uploaded_file, crop_data=None):
    """Canonicalize an uploaded JPEG, PNG, or WebP into a new 256px WebP file."""
    if getattr(uploaded_file, "size", None) is None or uploaded_file.size > MAX_UPLOAD_BYTES:
        raise LogoValidationError("file_too_large")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            _rewind(uploaded_file)
            with Image.open(uploaded_file, formats=ALLOWED_FORMATS) as probe:
                if probe.format not in ALLOWED_FORMATS:
                    raise LogoValidationError("invalid_image")
                probe.verify()

            _rewind(uploaded_file)
            with Image.open(uploaded_file, formats=ALLOWED_FORMATS) as source:
                if source.format not in ALLOWED_FORMATS:
                    raise LogoValidationError("invalid_image")

                # This must stay ahead of load(), EXIF normalization, and transforms.
                if source.width * source.height > MAX_INPUT_PIXELS:
                    raise LogoValidationError("too_many_pixels")

                source.load()
                normalized = ImageOps.exif_transpose(source)
                # Preserve the entire logo by default. A square output remains
                # bounded and cacheable, while transparent padding avoids
                # cutting off wide or tall marks. Explicit crop coordinates
                # remain supported for trusted future editor controls.
                crop_source = (
                    normalized
                    if crop_data is None
                    else normalized.crop(validate_square_crop(crop_data, normalized.size))
                )
                resized = ImageOps.contain(
                    crop_source, (OUTPUT_SIZE, OUTPUT_SIZE), Image.Resampling.LANCZOS
                ).convert("RGBA")
                result = Image.new("RGBA", (OUTPUT_SIZE, OUTPUT_SIZE), (0, 0, 0, 0))
                result.alpha_composite(
                    resized,
                    ((OUTPUT_SIZE - resized.width) // 2, (OUTPUT_SIZE - resized.height) // 2),
                )

                encoded = BytesIO()
                result.save(encoded, format="WEBP", quality=85, method=6)
    except LogoValidationError:
        raise
    except (
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
    ) as error:
        raise LogoValidationError("invalid_image") from error

    canonical = ContentFile(encoded.getvalue(), name="family-logo.webp")
    canonical.content_type = "image/webp"
    return canonical
