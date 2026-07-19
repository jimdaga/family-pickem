# Phase 8: Private AWS Delivery and Adversarial Verification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-18
**Phase:** 08-private-aws-delivery-and-adversarial-verification
**Areas discussed:** Private delivery, AWS credentials, replacement cleanup, release validation

---

## Private delivery

| Option | Description | Selected |
|--------|-------------|----------|
| Short-lived signed S3 URLs | Direct private-bucket delivery without public access or an app proxy. | ✓ |
| Django proxy | Route every image response through the Django application. | |

**User's choice:** Approved the recommended short-lived signed S3 URLs.
**Notes:** No public bucket/object access.

---

## AWS credentials

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated IAM principal and secret | Prefix-limited logo access delivered through Secrets Manager and ESO. | ✓ |
| Shared application credential | Reuse a broader existing application credential. | |

**User's choice:** Approved the dedicated least-privilege credential and secret.
**Notes:** Retain the existing AWS Secrets Manager → ESO → Helm/Kubernetes flow.

---

## Replacement cleanup

| Option | Description | Selected |
|--------|-------------|----------|
| Immediate cleanup | Delete superseded generated objects after the successful mutation. | ✓ |
| Retention window | Keep obsolete objects temporarily for recovery. | |

**User's choice:** Approved immediate cleanup.
**Notes:** Failure compensation must preserve the current reference.

---

## Release validation

| Option | Description | Selected |
|--------|-------------|----------|
| Staging and production smoke tests | Verify upload, replace, and removal after automated checks. | ✓ |
| Automated checks only | Release without environment smoke tests. | |

**User's choice:** Approved staging and production smoke gates.
**Notes:** Required before release.

## the agent's Discretion

- Choose exact signed-URL lifetime, AWS resource names, and test mechanics consistent with project conventions.

## Deferred Ideas

None.
