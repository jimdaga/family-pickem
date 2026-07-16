"""Capture management-command output into the logging framework.

The update pipeline (update_all and its steps) reports progress with
``self.stdout.write(...)`` — the same chatty per-item output the old cron
scripts produced. That goes to process stdout, not through ``logging``, so the
superadmin logs console (which is fed by a logging handler) never saw it.

``call_command_logged`` runs a command with its stdout/stderr redirected into
the ``pickem_api.pipeline`` logger, so every line the command prints becomes a
log record and shows up in the console — restoring the old cron verbosity.
"""
import logging
import re

from django.core.management import call_command

# One logger for all captured pipeline output, so the logs page can filter to it.
pipeline_logger = logging.getLogger("pickem_api.pipeline")

# Django styles command output with ANSI colour codes when the *process* stdout
# is a tty (e.g. running the scheduler from a local terminal). Strip them so the
# stored log lines are clean regardless of where the pipeline runs.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class LoggerWriter:
    """A minimal file-like object that turns ``.write()`` calls into log records,
    one per complete line. Partial writes are buffered until their newline."""

    def __init__(self, logger, level):
        self._logger = logger
        self._level = level
        self._buffer = ""

    def write(self, text):
        if not text:
            return
        self._buffer += _ANSI_RE.sub("", text)
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.rstrip()
            if line:
                self._logger.log(self._level, line)

    def flush(self):
        line = self._buffer.strip()
        if line:
            self._logger.log(self._level, line)
        self._buffer = ""

    def isatty(self):
        # Report non-tty so Django doesn't try to colour output for this stream.
        return False


def call_command_logged(command, **kwargs):
    """Run a management command, capturing its stdout (as INFO) and stderr (as
    ERROR) into the pipeline logger — and thus into the superadmin logs console.

    Used by the scheduler and the manual job-queue path. Commands that fan out
    to sub-commands (update_all) forward this same stdout/stderr down, so the
    whole pipeline's output is captured.
    """
    out = LoggerWriter(pipeline_logger, logging.INFO)
    err = LoggerWriter(pipeline_logger, logging.ERROR)
    try:
        call_command(command, stdout=out, stderr=err, **kwargs)
    finally:
        out.flush()
        err.flush()
