"""A logging.Handler that writes records into SuperAdminLogEntry so the console
can show application logs without shell/kubectl access.

Two failure modes are designed around:

1. Recursion — writing a log row runs DB queries, which the DB layer logs. If we
   captured those, a single DB error while logging would generate more log rows
   and loop. So records from the DB loggers (and this module) are dropped.
2. Bootstrap — before migrations create the table, create() raises. emit() routes
   every failure to handleError() (stderr), never back into logging, so a missing
   table simply drops the record instead of crashing the request.
"""
import logging

MAX_MESSAGE_LEN = 10000
MAX_TB_LEN = 20000

# Records from these logger prefixes are never captured (see recursion note).
EXCLUDED_LOGGER_PREFIXES = ('django.db', 'pickem_superadmin.logging')


class DatabaseLogHandler(logging.Handler):
    def emit(self, record):
        if record.name.startswith(EXCLUDED_LOGGER_PREFIXES):
            return
        try:
            from pickem_superadmin.models import SuperAdminLogEntry

            message = self.format(record)[:MAX_MESSAGE_LEN]
            traceback_text = None
            if record.exc_info:
                traceback_text = logging.Formatter().formatException(
                    record.exc_info
                )[:MAX_TB_LEN]

            SuperAdminLogEntry.objects.create(
                level=record.levelname,
                level_no=record.levelno,
                logger_name=record.name,
                message=message,
                traceback=traceback_text,
                pathname=(record.pathname or '')[:255] or None,
                lineno=record.lineno,
            )
        except Exception:
            # Never raise out of logging, and never log this failure back into
            # the DB. handleError() writes to stderr only.
            self.handleError(record)
