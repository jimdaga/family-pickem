---
phase: 08
slug: private-aws-delivery-and-adversarial-verification
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-18
---

# Phase 8 — Validation Strategy

## Test Infrastructure

| Property | Value |
|---|---|
| Framework | Django `TestCase` / test client, Helm, AWS CLI policy simulation |
| Config file | `pickem/pickem/test_settings.py` |
| Quick run command | `cd pickem && ../venv/bin/python manage.py test pickem_api.tests.test_family_logo_storage pickem_homepage.tests.FamilyLogoUploadFoundationTests --settings=pickem.test_settings --verbosity=2` |
| Full suite command | `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=1` |

## Sampling Rate

- After every task commit: run the focused Django tests or the affected Helm/shell/JSON command.
- After each wave: run Django checks, focused suites, and default/dev/prd Helm renders.
- Before `$gsd-verify-work`: full Django suite, AWS bucket/IAM/ESO evidence, then staging and production smoke evidence must be green.
- Max feedback latency: 60 seconds for focused checks; the full suite may run longer as the phase gate.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---|---|---|---|---|---|---|---|---|---|
| 08-01-01 | 01 | 1 | S3-02 | T-08-01/T-08-04 | Logo storage uses only dedicated settings; local fallback and five-minute signed URLs work | Django unit | focused storage test + `manage.py check` | Yes | pending |
| 08-01-02 | 01 | 1 | SAFE-02, SAFE-03 | T-08-02/T-08-03 | Hostile requests have no side effects; cleanup follows commit | Django request/transaction | `FamilyLogoUploadFoundationTests` + app suites | Yes | pending |
| 08-02-01 | 02 | 1 | S3-03 | T-08-06/T-08-08 | ESO secret reaches web/migrate only, never backup | Helm render | default/dev/prd `helm template` and `rg` checks | Yes | pending |
| 08-02-02 | 02 | 1 | S3-02, S3-03 | T-08-05/T-08-07 | IAM prefix is exact and provisioning fails closed | shell/JSON/AWS CLI | `bash -n`, JSON parse, IAM simulation, bucket readback | Yes | pending |
| 08-03-01 | 03 | 2 | S3-02, S3-03, SAFE-02, SAFE-03 | T-08-09 | Automated app/chart/cloud gates recorded before smoke | release gate | full Django suite, checks, migrations, Helm, shell/JSON | Yes | pending |
| 08-03-02 | 03 | 2 | S3-02, S3-03, SAFE-02, SAFE-03 | T-08-10/T-08-11/T-08-12 | Staging then production prove signed delivery, audit, cleanup, fallback | manual deployed smoke | artifact-presence check plus runbook steps | Yes | pending |

## Wave 0 Requirements

None — existing Django test infrastructure and existing chart rendering tools cover every planned test; Phase 8 extends focused test classes in Plan 01.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| Staging and production upload, replace, remove | S3-02, S3-03, SAFE-02, SAFE-03 | Requires the deployed AWS/ESO identity and signed URL observation | Follow Plan 03 Task 2 and record redacted evidence in the runbook. |

## Validation Sign-Off

- [x] All tasks have an automated verify command or a preceding Wave 0 dependency.
- [x] Sampling continuity is maintained across both waves.
- [x] No watch-mode commands are planned.
- [ ] Automated gates passed during execution.
- [ ] Staging smoke recorded.
- [ ] Production smoke recorded.

**Approval:** planned — release remains blocked until the final two smoke records are complete.
