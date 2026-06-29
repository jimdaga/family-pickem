---
phase: 02
slug: authorization-foundation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-28
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for authorization-foundation execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Django `TestCase` via `manage.py test` |
| **Config file** | `pickem/pickem/test_settings.py` |
| **Quick run command** | `cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings` |
| **Full suite command** | `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings` |
| **Estimated runtime** | ~10-30 seconds |

## Sampling Rate

- **After every task commit:** Run the relevant app test command for touched code.
- **After every plan wave:** Run `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings`.
- **Before `$gsd-verify-work`:** Full suite and Django check must be green.
- **Max feedback latency:** one implementation task.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | Central authz helpers | IDOR/BOLA | non-member and inactive member denied | unit | `cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings` | Yes | pending |
| 02-01-02 | 01 | 1 | Role hierarchy | least privilege | member cannot perform admin/owner checks | unit | `cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings` | Yes | pending |
| 02-01-03 | 01 | 1 | No global bypass | privilege escalation | superuser/commissioner without membership denied | unit | `cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings` | Yes | pending |
| 02-02-01 | 02 | 2 | Browser guard | auth boundary | anonymous redirects; non-member 404; wrong role 403 | integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings` | Yes | pending |
| 02-02-02 | 02 | 2 | API guard | auth boundary | API returns 401/403/404 without leaking tenants | integration | `cd pickem && ../venv/bin/python manage.py test pickem_api --settings=pickem.test_settings` | Yes | pending |
| 02-03-01 | 03 | 3 | Regression | route safety | existing global behavior not accidentally broken | regression | `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings` | Yes | pending |

## Wave 0 Requirements

Existing test infrastructure covers all Phase 2 requirements. No framework installation is needed.

## Manual-Only Verifications

All Phase 2 behaviors have automated verification. Manual QA may optionally hit the proof endpoint/page locally after execution.

## Validation Sign-Off

- [x] All tasks have automated verification.
- [x] Sampling continuity: no 3 consecutive tasks without automated verification.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency target is under one implementation task.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** planned 2026-06-28
