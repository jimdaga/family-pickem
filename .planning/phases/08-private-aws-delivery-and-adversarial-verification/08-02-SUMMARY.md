---
phase: 08-private-aws-delivery-and-adversarial-verification
plan: 02
subsystem: infra
tags: [aws, s3, iam, external-secrets, helm, kubernetes]
requires:
  - phase: 06-secure-logo-foundation
    provides: private server-derived family-logo object prefix
  - phase: 08-01
    provides: dedicated family-logo storage configuration contract
provides:
  - Prefix-limited IAM policy and idempotent provision/rotation workflow
  - Dedicated ESO Secret mounted only by web and migration workloads
  - Render assertions and redacted cloud-operations runbook
affects: [phase-08-release-verification, deployment, family-logo-storage]
tech-stack:
  added: [AWS CLI, IAM policy simulation, Helm render assertions]
  patterns: [empty-safe ESO condition, credential rotation with rollback]
key-files:
  created:
    - charts/family-pickem/templates/external-secret-logo-storage.yaml
    - infra/family-logo-storage/iam-policy.json
    - infra/family-logo-storage/provision.sh
    - infra/family-logo-storage/test-helm-render.sh
    - docs/runbooks/family-logo-storage.md
  modified:
    - charts/family-pickem/templates/deployment.yaml
    - charts/family-pickem/values.yaml
    - infra/app/values-dev.yaml
    - infra/app/values-prd.yaml
key-decisions:
  - "Use a separate ESO target guarded by the same condition as its Deployment envFrom references."
  - "Re-use an adopted active key and rotate only when the secret/key metadata does not match."
patterns-established:
  - "Dedicated feature credentials use a separate ExternalSecret rather than the backup-visible envvars Secret."
  - "IAM changes are verified by explicit allowed and denied principal-policy simulations."
requirements-completed: [S3-02, S3-03]
coverage:
  - id: D1
    description: Dedicated logo-secret Helm rendering is absent by default and isolated to web/migration in dev and production.
    requirement: S3-03
    verification:
      - kind: integration
        ref: infra/family-logo-storage/test-helm-render.sh
        status: pass
    human_judgment: false
  - id: D2
    description: IAM policy source and provisioner constrain family-logo object access and describe a redacted ESO rotation procedure.
    requirement: S3-02
    verification:
      - kind: other
        ref: bash -n infra/family-logo-storage/provision.sh; python -m json.tool infra/family-logo-storage/iam-policy.json
        status: pass
    human_judgment: true
    rationale: Live AWS preflight, IAM simulation, ESO synchronization, and rollout evidence require the authenticated staging/production environments.
duration: 24min
completed: 2026-07-19
status: complete
---

# Phase 8 Plan 2: Private AWS delivery and adversarial verification summary

**A separately reconciled, least-privilege family-logo credential reaches only the Django web and migration workloads, with policy simulation and redacted rotation controls ready for authenticated environments.**

## Performance

- **Duration:** 24 min
- **Completed:** 2026-07-19
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Added one empty-safe, owner-managed ExternalSecret for each configured logo-storage remote key and mounted it only in the Deployment's web and migration containers.
- Added dev and production remote secret keys, while default chart output and every CronJob omit the dedicated credentials.
- Added a prefix-only IAM policy, idempotent AWS CLI provisioner with bucket/IAM checks and rollback, plus an operator runbook that never requires exposing secret material.

## Task Commits

1. **Task 1: Render dedicated ESO logo-secret injection** - `a3f815d`, `6560f57`, `d34a0bc` (test/feat/chore)
2. **Task 2: Add idempotent AWS CLI provisioning and cloud verification runbook** - `2a30588` (feat)

## Verification

- `bash infra/family-logo-storage/test-helm-render.sh` — passed
- `helm lint charts/family-pickem -f infra/app/values-dev.yaml` — passed
- `helm lint charts/family-pickem -f infra/app/values-prd.yaml` — passed
- `bash -n infra/family-logo-storage/provision.sh` — passed
- `python -m json.tool infra/family-logo-storage/iam-policy.json` — passed
- Policy deny-pattern scan and `git diff --check` — passed

## Decisions Made

- The ExternalSecret and every logo `envFrom` use the identical enabled-and-nonempty-key condition, preventing a dangling secret reference in any chart output.
- Rotation retains the existing active credential until Secrets Manager, ESO, and the Deployment rollout verify the replacement; failed adoption rolls the replacement back.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved AWS CLI policy ARN command substitution correctness.**
- **Found during:** Task 2
- **Issue:** Provisioner progress output would have been captured with the policy ARN.
- **Fix:** Sent progress output to stderr and retained stdout exclusively for the ARN.
- **Files modified:** `infra/family-logo-storage/provision.sh`
- **Verification:** `bash -n` and source review.

**2. [Rule 2 - Security] Handled the IAM managed-policy five-version limit.**
- **Found during:** Task 2
- **Issue:** Repeated idempotent policy updates could exhaust IAM's managed-policy version quota.
- **Fix:** Delete one non-default version before creating a replacement when at the limit.
- **Files modified:** `infra/family-logo-storage/provision.sh`
- **Verification:** `bash -n` and source review.

**Total deviations:** 2 auto-fixed (1 bug, 1 security/correctness). No scope creep.

## User Setup Required

Run the provisioner against authenticated dev and production AWS/Kubernetes contexts, retain only redacted preflight/simulation/ESO evidence, then complete Phase 8 staging and production smoke tests. See [family-logo-storage.md](../../../docs/runbooks/family-logo-storage.md).

## Next Phase Readiness

Phase 8 Plan 03 can use the render assertion and runbook as release gates. No AWS, Secrets Manager, or Kubernetes resource was created during this repository implementation.

## Self-Check: PASSED

All created artifacts exist and task commits `a3f815d`, `6560f57`, `d34a0bc`, and `2a30588` are present.
