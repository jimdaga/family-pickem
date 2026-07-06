# Phase 5: Family Admin Experience - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-01T02:24:03Z
**Phase:** 5-Family Admin Experience
**Areas discussed:** Admin surface, member management, owner protections, invite management, settings, manual scoring tools, audit log visibility, UI style, legacy commissioner routes, authorization behavior

---

## Admin Surface And Navigation

| Option | Description | Selected |
|--------|-------------|----------|
| Tenant admin hub | Add a clear owner/admin area under `/families/<family_slug>/pools/<pool_slug>/admin/`; keeps controls tenant-scoped and discoverable. | ✓ |
| Inline controls | Put controls on existing pages like rules, members, dashboard, and standings; faster access but more clutter. | |
| Hybrid | Admin hub plus contextual links/buttons from relevant pages. | |

**User's choice:** Tenant admin hub.
**Notes:** Admin controls should live under explicit tenant context.

---

## Member Management

| Option | Description | Selected |
|--------|-------------|----------|
| Manage roles and deactivate members | View members, promote/demote eligible roles, and deactivate/reactivate members. | ✓ |
| Roles only | Allow role changes, but no deactivate/reactivate yet. | |
| View-only members | Show members and roles, but defer changes. | |

**User's choice:** Manage roles and deactivate members.
**Notes:** This is part of the family admin baseline.

---

## Owner-Sensitive Role Rules

| Option | Description | Selected |
|--------|-------------|----------|
| Strong owner protections | Only owners can promote admins, demote admins, transfer ownership, or deactivate members; prevent removing/demoting the last owner. | ✓ |
| Admins can manage members | Admins can promote/demote members but cannot affect owners or the last owner. | |
| Owner-only role management | Only owners can change any role/status; admins manage invites/settings only. | |

**User's choice:** Strong owner protections.
**Notes:** Least privilege and last-owner safety are required.

---

## Invite Management

| Option | Description | Selected |
|--------|-------------|----------|
| Full invite lifecycle | List/create/revoke/regenerate/set expiry/max uses/role and see use counts. | |
| Simple revoke/regenerate | List current invites and revoke/regenerate member invites only; keep defaults. | |
| Create + revoke only | Minimal UI around the existing invite model. | ✓ |

**User's choice:** Keep it simple around the current invite model.
**Notes:** User clarified that invites will later be refactored away from visible code generation toward an email model, so Phase 5 should avoid a major invite redesign. Email invite refactor is deferred.

---

## Family And Pool Settings

| Option | Description | Selected |
|--------|-------------|----------|
| Basic family + pool settings | Edit family name, pool display name, and rules/settings values already represented by `PoolSettings`. | ✓ |
| Rules/settings only | Keep family/pool identity fixed; edit rules/settings only. | |
| Display/admin labels only | Minimal rename/edit surface, no gameplay-affecting settings. | |

**User's choice:** Basic family + pool settings.
**Notes:** Settings should be tenant-scoped and safe.

---

## Manual Pick And Week-Winner Admin Actions

| Option | Description | Selected |
|--------|-------------|----------|
| Tenant-scoped parity for existing commissioner tools | Move manual pick submission, user-pick retrieval, and week-winner/bonus selection into family admin hub with pool-scoped checks and audit logs. | ✓ |
| Week-winner only | Migrate winner/bonus selection now; defer manual picks. | |
| Defer scoring tools | Do settings/member/invites/audit only; leave commissioner scoring tools for later. | |

**User's choice:** Tenant-scoped parity for existing commissioner tools.
**Notes:** Existing global commissioner scoring tools should be migrated into tenant admin context.

---

## Audit Log Visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Admin-visible recent activity | Show recent family admin actions such as invite created/revoked, membership changes, settings updates, manual picks, and winner overrides. | ✓ |
| Owner-only audit log | Same audit trail, but visible only to owners. | |
| Write logs only | Record audit events, but do not build an audit log page yet. | |

**User's choice:** Admin-visible recent activity.
**Notes:** Members cannot view audit logs.

---

## Admin UI Style

| Option | Description | Selected |
|--------|-------------|----------|
| Functional admin UI, minimal styling | Clean usable forms/tables but avoid major visual redesign. | |
| Match current refactor direction | Use the new Tailwind/theme direction and polish the admin hub as part of the phase. | ✓ |
| Barebones backend-first | Prioritize routes/actions/tests with very plain templates. | |

**User's choice:** Match current refactor direction.
**Notes:** User said the frontend refactor is almost done, so it is safe to improve the admin UI.

---

## Legacy Commissioner Routes

| Option | Description | Selected |
|--------|-------------|----------|
| Redirect tenant-resolvable users to family admin | Keep legacy routes as compatibility bridges but do not render global tools. | |
| Disable legacy commissioner routes | Return 404/403 for legacy commissioner pages/actions once tenant admin exists. | ✓ |
| Leave legacy routes for now | Build new tools but keep old commissioner tools unchanged until later. | |

**User's choice:** Disable legacy commissioner routes.
**Notes:** Legacy global commissioner tools should not remain available.

---

## Authorization Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Same 404/403 split | Non-members get 404, members without admin role get 403, anonymous users redirect/login or auth-error for JSON. | ✓ |
| Always 404 for admin routes | Hide existence even from family members without admin rights. | |
| Friendly 403 for all authenticated denials | Easier UX, slightly more revealing. | |

**User's choice:** Same Phase 2 404/403 split.
**Notes:** Preserve established tenant authorization behavior.

---

## the agent's Discretion

- Exact route names, template names, form names, and page/tab grouping.
- Exact audit-log metadata shape, provided it is useful and safe.
- Whether invite regeneration appears as a dedicated action or as revoke-and-create if it remains simple.

## Deferred Ideas

- Email-based invite workflow and invite model redesign.
- Production cron/scoring hardening and pool-aware background jobs.
- Non-null tenant constraints and production migration rollback hardening.
