from django.test import TestCase

from pickem_superadmin.models import SuperAdminLogEntry


class LogEntryModelTests(TestCase):
    def test_can_store_a_log_row(self):
        entry = SuperAdminLogEntry.objects.create(
            level='INFO', level_no=20, logger_name='pickem_api.x', message='hi',
        )
        self.assertEqual(SuperAdminLogEntry.objects.get().message, 'hi')
        self.assertIsNotNone(entry.timestamp)
