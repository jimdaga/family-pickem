"""Streaming guards for the family-admin logo upload route."""

from django.core.files.uploadhandler import FileUploadHandler, StopUpload


MAX_FAMILY_LOGO_UPLOAD_BYTES = 5 * 1024 * 1024


class FamilyLogoUploadSizeLimitHandler(FileUploadHandler):
    """Abort only the logo file once its actual streamed size exceeds 5 MiB.

    This handler deliberately passes normal chunks through to Django's standard
    handlers.  It never creates an UploadedFile itself.
    """

    def new_file(self, field_name, *args, **kwargs):
        super().new_file(field_name, *args, **kwargs)
        self._is_logo = field_name == "logo"
        self._bytes_received = 0

    def receive_data_chunk(self, raw_data, start):
        if self._is_logo:
            self._bytes_received += len(raw_data)
            if self._bytes_received > MAX_FAMILY_LOGO_UPLOAD_BYTES:
                # The view consumes this stable, non-sensitive code after
                # CSRF has parsed the request and renders the normal form.
                self.request._family_logo_upload_error = "file_too_large"
                raise StopUpload()
        return raw_data

    def file_complete(self, file_size):
        return None
