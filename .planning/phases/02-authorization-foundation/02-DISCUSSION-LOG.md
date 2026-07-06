# Phase 2: Authorization Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-28
**Phase:** 02-authorization-foundation
**Areas discussed:** Guard Behavior, Current Family/Pool Resolution, Role Boundaries, Scope Of Route Changes In Phase 2

---

## Guard Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| 404 for non-members, 403 for wrong role | Non-members get not found to reduce family/pool existence leakage. Active family members who lack admin/owner permission get forbidden. | ✓ |
| 403 for all authenticated denials | Simpler to reason about and test, but confirms family/pool existence to outsiders. | |
| Redirect for page denials, JSON errors for APIs | More user-friendly on pages, but easier to hide authorization bugs behind redirects. | |

**User's choice:** 404 for non-members, 403 for wrong role.
**Notes:** Anonymous browser/page requests should redirect to login. Anonymous API/helper denials should return an authentication error.

---

## Current Family/Pool Resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit first, legacy fallback only where needed | Helpers accept explicit family/pool context. Existing global routes may use a documented legacy fallback temporarily, but new tenant-aware code must pass explicit context. | ✓ |
| Session-selected family/pool first | Easier for old routes and future switcher UX, but risks hidden tenant context and harder-to-review authorization. | |
| Always legacy default until route migration | Lowest disruption, but proves less about real multi-family isolation. | |

**User's choice:** Explicit first, legacy fallback only where needed.
**Notes:** When both family and pool are supplied, helpers must require the pool to belong to the family and the user to be an active member of that family.

---

## Role Boundaries

| Option | Description | Selected |
|--------|-------------|----------|
| Superuser can bypass; commissioner maps only through membership | Superuser remains emergency/global admin; `is_commissioner` does not grant tenant admin by itself. | |
| Superuser and commissioner both bypass all family checks | Easier transition, but preserves the global privilege problem. | |
| No global bypass at all | Strong tenant purity; even superusers need explicit memberships for tenant helpers. | ✓ |

**User's choice:** No global bypass at all.
**Notes:** Django admin can retain separate global staff/superuser behavior. Tenant-scoped helpers must require explicit active membership. Role ladder is member read/play, admin non-destructive management, owner destructive/ownership actions.

---

## Scope Of Route Changes In Phase 2

| Option | Description | Selected |
|--------|-------------|----------|
| Helpers plus focused proof endpoints/tests only | Build reusable resolver/guard/query helpers and tests; broad page/API migration stays later. | ✓ |
| Start applying helpers to major pages now | Faster visible progress, but risks turning Phase 2 into Phase 4. | |
| Helpers/tests only, no runtime wiring at all | Cleanest foundation, but may miss integration problems until later. | |

**User's choice:** Helpers plus focused proof endpoints/tests only.
**Notes:** For proof wiring, default to helper-level tests only unless research/planning finds a tiny safe endpoint. Avoid broad wrapping of high-risk picks/message-board/commissioner flows in Phase 2.

---

## the agent's Discretion

- Exact helper module placement.
- Exact exception/decorator/permission class names.
- Whether a tiny proof route is worth including.
- Exact test organization.

## Deferred Ideas

- Broad tenant URL migration.
- Onboarding and family switching.
- Family admin UI/actions.
- Cron/scoring hardening.
- Pool-specific memberships.
