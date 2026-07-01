# Phase 05 Deferred Items

## 05-06 Out-of-Scope Broad Test Failures

- `cd pickem && ../venv/bin/python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings --verbosity=2` failed 8 tests after Plan 05-06 implementation.
- The failures are in pre-existing dirty frontend refactor templates outside the Plan 05-06 commit set:
  - `pickem/pickem_homepage/templates/pickem/home.html`
  - `pickem/pickem_homepage/templates/pickem/family_pool_home.html`
  - `pickem/pickem_homepage/templates/pickem/rules.html`
  - related dirty shared template context in `pickem/pickem_homepage/templates/pickem/base.html`
- Failed assertions expect older public homepage text, dashboard empty-state link/text, message-board AJAX URL markup, and rules text (`Game locking: Off`) that the dirty refactor no longer renders.
- Plan 05-06 did not modify those files; focused winner/legacy tests pass.
