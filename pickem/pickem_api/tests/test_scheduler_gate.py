from django.test import SimpleTestCase

from pickem_api.apps import _should_start_scheduler


class ShouldStartSchedulerTests(SimpleTestCase):
    def test_both_true_starts(self):
        self.assertTrue(
            _should_start_scheduler(
                {"RUN_SCHEDULER": "true", "RUN_WEB_SERVER": "true"}
            )
        )

    def test_scheduler_only_does_not_start(self):
        self.assertFalse(_should_start_scheduler({"RUN_SCHEDULER": "true"}))

    def test_web_only_does_not_start(self):
        self.assertFalse(_should_start_scheduler({"RUN_WEB_SERVER": "true"}))

    def test_neither_does_not_start(self):
        self.assertFalse(_should_start_scheduler({}))

    def test_requires_literal_true(self):
        self.assertFalse(
            _should_start_scheduler(
                {"RUN_SCHEDULER": "1", "RUN_WEB_SERVER": "true"}
            )
        )
