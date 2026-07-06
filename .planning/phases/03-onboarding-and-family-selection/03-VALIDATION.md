---
phase: 03
slug: onboarding-and-family-selection
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-29
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for onboarding and family selection execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Django `TestCase` via `manage.py test` |
| **Config file** | `pickem/pickem/test_settings.py` |
| **Quick run command** | `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings` |
| **Full suite command** | `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings` |
| **Estimated runtime** | ~10-30 seconds |

## Sampling Rate

- **After every task commit:** Run focused app tests for touched code.
- **After every plan wave:** Run `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings`.
- **Before `$gsd-verify-work`:** Full suite and Django check must be green.
- **Max feedback latency:** one implementation task.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | INV-03/INV-04 | global data exposure | signed-in users route by active membership count before seeing global private data | integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings` | Yes | passed; see `03-01-SUMMARY.md` and final 03-05 run |
| 03-01-02 | 01 | 1 | INV-03 | no-family leakage | no-family onboarding does not render global standings/picks/message-board content | template/integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings` | Yes | passed; see `03-01-SUMMARY.md` and final 03-05 run |
| 03-02-01 | 02 | 2 | TEN-01/TEN-02 | tenant creation integrity | create-family creates family, default pool, settings, owner membership, audit | integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings` | Yes | passed; see `03-02-SUMMARY.md` and final 03-05 run |
| 03-02-02 | 02 | 2 | AUTHZ-05 | identifier trust | slug collisions are handled server-side | unit/integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings` | Yes | passed; see `03-02-SUMMARY.md` and final 03-05 run |
| 03-03-01 | 03 | 3 | INV-01/INV-02 | invite brute force/leakage | raw invite code is transient; only `code_hash` persists | unit/integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings` | Yes | passed; see `03-03-SUMMARY.md` and final 03-05 run |
| 03-03-02 | 03 | 3 | INV-03/AUTHZ-05 | invalid invite access | revoked, expired, exhausted, bad-code, inactive family/pool fail closed | integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings` | Yes | passed; see `03-03-SUMMARY.md` and final 03-05 run |
| 03-03-03 | 03 | 3 | SEC-02 | CSRF | invite/create/join mutations reject missing CSRF tokens | security integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings` | Yes | passed; see `03-03-SUMMARY.md` and final 03-05 run |
| 03-04-01 | 04 | 4 | INV-04 | cross-family leakage | switcher lists active memberships only and links to default active pools | template/integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage --settings=pickem.test_settings` | Yes | passed; see `03-04-SUMMARY.md` and final 03-05 run |
| 03-05-01 | 05 | 5 | regression | route safety | existing public pages/tests still pass | regression | `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings` | Yes | passed; see `03-05-SUMMARY.md` |

## Final Verification Evidence

Executed for Plan 03-05 on 2026-06-29:

- `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings` passed with 13 existing `pickem_api.userStats` `IntegerField(max_length=...)` warnings.
- `cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings` passed with `No changes detected` and the same existing warnings.
- `cd pickem && ../venv/bin/python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings --verbosity=2` passed with 116 tests.
- `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=2` passed with 116 tests.
- `curl -s --max-time 5 http://localhost:8000 | head -40` returned public homepage HTML including `<title>Family Pick'em</title>`.

## Phase 4 Handoff Risks

- Full dashboard/home, picks, scores, standings, rules, profile, and message-board page data remain partially or wholly global compatibility routes until Phase 4 migrates them into explicit `/families/<family_slug>/pools/<pool_slug>/...` context.
- Phase 4 must add tenant-scoped query filters and negative tests for picks, standings, stats, message-board content, profile context, and any pick overlays on global NFL score data.
- Phase 4 should preserve the Phase 3 route-entry guarantees: no-family users stay on onboarding, active members enter explicit tenant URLs, and switcher choices remain active-membership-only.
- Phase 5 still owns full invite management, role management, family settings, and audit-log UI; Phase 3 only delivered minimal owner-created member invites.

## Wave 0 Requirements

Existing test infrastructure covers all Phase 3 requirements. No test framework installation is needed.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Header/mobile switcher visual fit | INV-04 | Existing suite has no browser visual automation | Using the already-running server at `http://localhost:8000`, sign in with one-family and multi-family test users, and verify header and mobile nav text does not overlap. |

## Validation Sign-Off

- [x] All tasks have automated verification or documented manual check.
- [x] Sampling continuity: no 3 consecutive tasks without automated verification.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency target is under one implementation task.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** planned 2026-06-29
