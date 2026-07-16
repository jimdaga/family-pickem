import logging

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from pickem_superadmin.models import SuperAdminLogEntry


class LogEntryModelTests(TestCase):
    def test_can_store_a_log_row(self):
        entry = SuperAdminLogEntry.objects.create(
            level='INFO', level_no=20, logger_name='pickem_api.x', message='hi',
        )
        self.assertEqual(SuperAdminLogEntry.objects.get().message, 'hi')
        self.assertIsNotNone(entry.timestamp)


class DatabaseLogHandlerTests(TestCase):
    def _handler(self):
        from pickem_superadmin.logging import DatabaseLogHandler

        return DatabaseLogHandler()

    def _record(self, name='pickem_api.test', level=logging.INFO, msg='hello', exc_info=None):
        return logging.LogRecord(
            name=name, level=level, pathname='/app/x.py', lineno=42,
            msg=msg, args=(), exc_info=exc_info,
        )

    def test_emit_writes_a_row(self):
        self._handler().emit(self._record(msg='captured'))
        row = SuperAdminLogEntry.objects.get()
        self.assertEqual(row.message, 'captured')
        self.assertEqual(row.level, 'INFO')
        self.assertEqual(row.level_no, logging.INFO)
        self.assertEqual(row.logger_name, 'pickem_api.test')

    def test_db_logger_records_are_dropped(self):
        # A record from the DB layer must never be written back into the DB,
        # or a DB error while logging would loop.
        self._handler().emit(self._record(name='django.db.backends'))
        self.assertEqual(SuperAdminLogEntry.objects.count(), 0)

    def test_long_message_is_truncated(self):
        from pickem_superadmin.logging import MAX_MESSAGE_LEN

        self._handler().emit(self._record(msg='x' * (MAX_MESSAGE_LEN + 500)))
        self.assertEqual(len(SuperAdminLogEntry.objects.get().message), MAX_MESSAGE_LEN)

    def test_exception_records_capture_a_traceback(self):
        try:
            raise ValueError('boom')
        except ValueError:
            import sys
            rec = self._record(level=logging.ERROR, msg='failed', exc_info=sys.exc_info())
        self._handler().emit(rec)
        row = SuperAdminLogEntry.objects.get()
        self.assertIn('ValueError: boom', row.traceback)


class LoggingWiringTests(TestCase):
    def test_app_logger_info_is_captured(self):
        logging.getLogger('pickem_api').info('WIRING-APP-INFO-marker')
        self.assertTrue(
            SuperAdminLogEntry.objects.filter(message__contains='WIRING-APP-INFO-marker').exists()
        )

    def test_unrelated_info_is_not_captured(self):
        logging.getLogger('some.random.thirdparty').info('WIRING-ROOT-INFO-marker')
        self.assertFalse(
            SuperAdminLogEntry.objects.filter(message__contains='WIRING-ROOT-INFO-marker').exists()
        )

    def test_unrelated_warning_is_captured(self):
        logging.getLogger('some.random.thirdparty').warning('WIRING-ROOT-WARN-marker')
        self.assertTrue(
            SuperAdminLogEntry.objects.filter(message__contains='WIRING-ROOT-WARN-marker').exists()
        )


class LogsViewTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser(
            username='root', email='root@example.com', password='pw',
        )
        self.client.force_login(self.root)
        SuperAdminLogEntry.objects.create(level='INFO', level_no=logging.INFO,
                                          logger_name='pickem_api.a', message='info-row')
        SuperAdminLogEntry.objects.create(level='ERROR', level_no=logging.ERROR,
                                          logger_name='pickem_api.b', message='error-row')

    def test_page_renders(self):
        response = self.client.get(reverse('superadmin:logs'))
        self.assertEqual(response.status_code, 200)

    def test_level_filter_limits_rows(self):
        response = self.client.get(reverse('superadmin:logs'), {'level': str(logging.ERROR)})
        messages = [e.message for e in response.context['page_obj']]
        self.assertIn('error-row', messages)
        self.assertNotIn('info-row', messages)

    def test_text_search_filters_message(self):
        response = self.client.get(reverse('superadmin:logs'), {'q': 'error-row'})
        messages = [e.message for e in response.context['page_obj']]
        self.assertEqual(messages, ['error-row'])

    def test_logger_filter(self):
        response = self.client.get(reverse('superadmin:logs'), {'logger': 'pickem_api.b'})
        messages = [e.message for e in response.context['page_obj']]
        self.assertEqual(messages, ['error-row'])
