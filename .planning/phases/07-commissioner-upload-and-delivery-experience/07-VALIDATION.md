---
phase: 07
slug: commissioner-upload-and-delivery-experience
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-18
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Django `manage.py test` / unittest |
| **Config file** | `pickem/pickem/test_settings.py` |
| **Quick run command** | `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests --settings=pickem.test_settings --verbosity=1` |
| **Full suite command** | `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=1` |
| **Estimated runtime** | ~10 seconds |

## Sampling Rate

- **After every task commit:** Run the focused homepage suite.
- **After every plan wave:** Run the full Django suite, `manage.py check`, and `makemigrations --check --dry-run`.
- **Before `$gsd-verify-work`:** Full suite must be green; exercise the authorized settings page in a browser on desktop and mobile widths.
- **Max feedback latency:** 30 seconds.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | LOGO-01, LOGO-02 | T-07-01 | Strict all-or-none integer crop coordinates reach the existing processor; malformed/mixed crop state does not mutate the old logo. | integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests --settings=pickem.test_settings --verbosity=1` | ✅ | ⬜ pending |
| 07-01-02 | 01 | 1 | LOGO-01, LOGO-02 | T-07-02 | Cropper UI previews with an object URL only, supports drag/zoom/reset, clears/revokes preview state, and submits no canvas bytes. | DOM/browser + integration | focused homepage suite plus browser UAT | ✅ | ⬜ pending |
| 07-02-01 | 02 | 2 | LOGO-03, S3-04 | T-07-03 | Replacement and staged removal are tenant/CSRF-protected, audit logged, server-persisted only on Save settings, and render only canonical/default sources. | integration | focused homepage/API logo suites | ✅ | ⬜ pending |
| 07-02-02 | 02 | 2 | LOGO-04 | T-07-04 | Settings, picker, and home render compact rounded-square canonical/default marks with decorative alt text next to visible family names. | template/integration | focused homepage suite | ✅ | ⬜ pending |

## Wave 0 Requirements

Existing Django test infrastructure and local FileSystemStorage test seams cover this phase; no new test framework or package installation is required.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Desktop and mobile crop interaction | LOGO-02 | Drag/zoom behavior and visual framing require a real browser. | Sign in as a family admin; select transparent and opaque images; verify rounded-square preview, slider, drag, Reset, Clear selection, staged removal wording, and Save settings flow at desktop/mobile widths. |
| Browser error/reselection experience | LOGO-03 | Browser file inputs intentionally cannot be repopulated after a server error. | Submit an invalid file; verify other edits remain, old logo remains, chooser shows the error, and the file must be selected again. |

## Validation Sign-Off

- [x] All planned work has focused automated Django coverage or an explicit browser UAT backstop.
- [x] Sampling continuity: every planned task has a focused automated verification command.
- [x] Wave 0 uses existing infrastructure.
- [x] No watch-mode flags.
- [x] Feedback latency is below 30 seconds for focused tests.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** pending planner task alignment
