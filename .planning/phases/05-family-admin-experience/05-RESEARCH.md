# Phase 05: Family Admin Experience - Research

**Researched:** 2026-07-01  
**Domain:** Django tenant administration, role management, invite management, audit logging, and legacy commissioner migration  
**Confidence:** HIGH for codebase facts, MEDIUM for Django docs, LOW for OWASP web-search findings

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
## Implementation Decisions

### Admin surface and navigation

- **D-01:** Family admin tools should be reached from a dedicated tenant admin hub under an explicit tenant URL such as `/families/<family_slug>/pools/<pool_slug>/admin/`.
- **D-02:** The admin hub should be discoverable for authorized owners/admins from the tenant navigation/header or relevant tenant pages, but members must not see or use admin controls as authorization.
- **D-03:** The admin hub is the primary admin surface; avoid scattering full admin workflows inline across user-facing gameplay pages.

### Member and role management

- **D-04:** Phase 5 should include member management that lets authorized family admins view members, change eligible roles, and deactivate/reactivate memberships.
- **D-05:** Strong owner protections are required: only owners may promote admins, demote admins, transfer ownership, deactivate members, or perform ownership-sensitive actions.
- **D-06:** The app must prevent removing, demoting, deactivating, or otherwise losing the last active owner of a family.
- **D-07:** Role/status changes must be server-side checked against active membership, current family, and least-privilege role rules. Hidden buttons or missing UI controls are not authorization.

### Invite management

- **D-08:** Keep Phase 5 invite management simple and based on the existing `FamilyInvitation` model. Do not redesign invitations around email delivery in this phase.
- **D-09:** Owners/admins should be able to create member invites, list active/recent invites, revoke invites, and see basic invite metadata such as role, expiry, max uses, use count, creator, and revoked state where already represented.
- **D-10:** Raw invite codes/links should be shown only immediately after creation and should not be stored or exposed later. Persisted invite display should use safe metadata, not raw codes.
- **D-11:** Regeneration should be treated as revoking an existing invite and creating a replacement only if the planner finds this fits cleanly without expanding into the later email-invite redesign.

### Family, pool, and rules settings

- **D-12:** Phase 5 should let owners/admins edit basic family and pool settings, including family display name, pool display name, and rules/settings values already represented by `PoolSettings`.
- **D-13:** Settings writes must be tenant-scoped and audit logged. Client-provided family/pool identifiers must be validated against the server-resolved tenant context.
- **D-14:** Avoid broad scoring-rule model redesign in this phase. If a setting is not already represented or safely additive, defer it.

### Manual pick and week-winner admin actions

- **D-15:** Phase 5 should migrate existing commissioner manual pick submission, user-pick retrieval, and week-winner/bonus selection into the tenant admin hub.
- **D-16:** Manual pick and winner actions must be pool-scoped, validate week/user/game IDs against the current pool/family, and avoid modifying another family's picks, standings, or bonuses.
- **D-17:** Existing dynamic week-winner field behavior is fragile; Phase 5 should validate week numbers in the supported range before constructing dynamic fields and should test invalid week behavior.
- **D-18:** These admin actions are security-sensitive and must create `FamilyAuditLog` entries with enough metadata to identify actor, target, action type, and relevant before/after or request context.

### Audit log visibility

- **D-19:** The family admin UI should show recent family admin activity to owners/admins, including invite created/revoked, membership role/status changes, settings updates, manual picks, and week-winner overrides where those actions exist.
- **D-20:** Members cannot view the audit log. Audit log queries must be scoped to the current family and avoid leaking other-family events.

### UI polish and frontend refactor alignment

- **D-21:** Phase 5 admin UI should match the active frontend refactor direction and may use the new Tailwind/theme patterns. It is safe to improve polish rather than keeping admin pages barebones.
- **D-22:** Admin pages should still be practical operational screens: clear tables/forms, good empty states, mobile-friendly layout, visible current family/pool context, and no marketing-style landing page.
- **D-23:** The planner/executor must preserve unrelated local frontend refactor work and avoid broad visual churn outside the Phase 5 admin surfaces.

### Legacy commissioner routes

- **D-24:** Legacy global commissioner routes should be disabled in Phase 5 once tenant admin replacements exist. They should not continue rendering or mutating global commissioner tools.
- **D-25:** Disabling legacy commissioner surfaces may use 404/403/generic JSON denial depending on route type, but must not leave a private global admin path available.

### Authorization and denial behavior

- **D-26:** Reuse the Phase 2 denial split for family admin routes: anonymous browser users redirect to login; authenticated non-members get 404; active members without sufficient role get 403; anonymous/API JSON requests return auth errors rather than redirects where applicable.
- **D-27:** Owner/admin actions require least-privilege checks server-side. Admins may handle non-owner-sensitive actions such as invite and settings management, but owner-sensitive role/status actions require owner.
- **D-28:** Negative tests must prove members, outsiders, inactive memberships, forged URLs, forged request bodies, and cross-family object IDs cannot access or mutate another family's admin data.

### the agent's Discretion
- Exact admin hub route names, template filenames, form class names, and view helper names, provided routes remain explicit tenant URLs and use existing tenant authorization helpers.
- Exact grouping of admin hub subpages or tabs, provided the final UI is clear and not a dead-end.
- Exact audit-log metadata shape, provided it remains safe, useful, and avoids secrets/raw invite codes.
- Whether to implement invite regeneration as a distinct button or as documented revoke-and-create flow, provided no raw code is stored or exposed after creation.

### Deferred Ideas (OUT OF SCOPE)
## Deferred Ideas

- Email-based invitation flow and invite model redesign. This should be a later phase because it changes product behavior, data model/API expectations, and likely email delivery infrastructure.
- Production cron/scoring hardening and pool-aware background scoring jobs remain Phase 6.
- Non-null tenant constraints, strict production migration rollback plans, and broader settings/security hardening remain Phase 6.
- Advanced multi-pool admin UX beyond the current/default pool remains later scope unless needed by current Phase 5 routes.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTHZ-03 | Owner/admin actions require least-privilege role checks. | Use `family_member_required(minimum_role=...)` for route-level checks and action-specific owner checks for role/status mutations. [VERIFIED: codebase grep] |
| AUTHZ-05 | Client-provided family, pool, user, season, week, and game identifiers are validated against server-resolved membership and allowed objects. | Resolve family/pool from `request.tenant_context`; resolve target users through active same-family memberships; resolve games by server-side game/week/season validation. [VERIFIED: codebase grep] |
| INV-02 | Invite codes can expire, be revoked, and be regenerated. | Existing `FamilyInvitation` already has `expires_at`, `is_revoked`, `max_uses`, and `use_count`; implement revoke and optional revoke-and-create regeneration without raw-code storage. [VERIFIED: codebase grep] |
| POOL-04 | Rules/settings are visible and editable in the appropriate family/pool context. | `PoolSettings` currently supports `picks_lock_at_kickoff` and `allow_tiebreaker`; Phase 4 rendered rules display-only and handed editing to Phase 5. [VERIFIED: codebase grep] |
| COMM-03 | Site/family banners do not leak across families. | `SiteBanner.family` exists and Phase 4 context processors choose current-family banners before site-wide fallback; Phase 5 should preserve/test isolation but not add banner editing UI. [VERIFIED: codebase grep] |
| SEC-01 | Security-sensitive admin actions are audit logged. | `FamilyAuditLog` has actions for invitation, membership, pool settings, manual picks, and week winners. [VERIFIED: codebase grep] |
</phase_requirements>

## Summary

Phase 5 should implement a tenant admin hub under explicit family/pool URLs and migrate the remaining useful global commissioner behavior into tenant-scoped owner/admin workflows. [VERIFIED: `.planning/phases/05-family-admin-experience/05-CONTEXT.md`] The critical implementation path is to reuse `pickem_homepage.authz.family_member_required` and `pickem_api.authz.require_tenant_context`, then add command-style forms/views that derive `family`, `pool`, `actor`, and most target fields server-side. [VERIFIED: codebase grep]

The legacy commissioner surface is still global: `is_commissioner()` grants access via `UserProfile.is_commissioner` or `is_superuser`, `/commissioners/` queries all active users and global `userSeasonPoints`, and `set_week_winner()` plus `submit_manual_pick()` are CSRF-exempt JSON mutations. [VERIFIED: codebase grep] Those endpoints should not be extended; build tenant replacements first, then deny the legacy routes. [VERIFIED: `.planning/phases/05-family-admin-experience/05-CONTEXT.md`]

**Primary recommendation:** Add a focused family admin hub with tenant routes, small admin command forms, transaction-wrapped mutations, `FamilyAuditLog` writes, cross-family negative tests, and explicit legacy commissioner denials. [VERIFIED: codebase grep]

## Project Constraints (from AGENTS.md)

- The local webserver is assumed to already run at `http://localhost:8000`; do not start it unnecessarily. [VERIFIED: `AGENTS.md`]
- Validate rendered changes with `curl http://localhost:8000` and parse HTML where frontend output matters. [VERIFIED: `AGENTS.md`]
- CSS changes must account for JavaScript DOM interactions. [VERIFIED: `AGENTS.md`]
- Use Django ORM rather than raw SQL for application queries. [VERIFIED: `AGENTS.md`]
- Run Django commands from `pickem/` with the repo virtualenv, e.g. `../venv/bin/python manage.py test --settings=pickem.test_settings`. [VERIFIED: `AGENTS.md`]
- Tailwind source/output are under `pickem/pickem_homepage/static/css/input.css` and `tailwind.css`; the project is mid Bootstrap-to-Tailwind migration. [VERIFIED: `AGENTS.md`]
- Current season must come from `get_season()` or the current-season model/API, not hardcoded values. [VERIFIED: `AGENTS.md`]
- Preserve the user dirty worktree outside `.planning`, including current frontend/logo/schema/admin/migration/screenshot refactor files. [VERIFIED: `git status --short`]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Admin hub routing and authorization | Frontend Server / Django Views | API / Authz Helpers | Browser routes are Django template views; authorization policy lives in reusable helper functions. [VERIFIED: codebase grep] |
| Family/pool settings edits | API / Backend | Database / Storage | Writes mutate `Family`, `Pool`, and `PoolSettings` rows and must be transaction/audit controlled. [VERIFIED: codebase grep] |
| Member and role management | API / Backend | Database / Storage | Role/status writes are business rules over `FamilyMembership`, not browser-only UI state. [VERIFIED: codebase grep] |
| Invite management | API / Backend | Frontend Server / Templates | Raw code generation/hash/revocation is server-owned; templates only display safe metadata or one-time raw codes. [VERIFIED: codebase grep] |
| Audit log display | Frontend Server / Django Views | Database / Storage | Views query `FamilyAuditLog` scoped by current family and render recent events. [VERIFIED: codebase grep] |
| Manual pick/week-winner admin actions | API / Backend | Database / Storage | These mutate pool-scoped picks/standings and must validate dynamic week fields before persistence. [VERIFIED: codebase grep] |
| Admin navigation affordance | Browser / Client | Frontend Server / Templates | Template links can hide/show admin entry points, but server-side guards remain authoritative. [VERIFIED: Django docs; VERIFIED: codebase grep] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 4.0.2 | Function-based views, ORM, templates, CSRF, transactions, forms, tests. | Existing project framework; official docs describe auth decorators, request users, CSRF headers, and view method decorators. [CITED: https://docs.djangoproject.com/en/4.0/topics/auth/default/] [CITED: https://docs.djangoproject.com/en/4.0/ref/csrf/] |
| Django test runner | 4.0.2 | Unit/integration tests for views, forms, authz, and model mutations. | Existing suite uses `manage.py test` and Phase 4 reached 157 tests. [VERIFIED: `.planning/phases/04-family-scoped-app-pages/04-VALIDATION.md`] |
| Tailwind CSS | 3.4.18 | Admin hub template styling in the active frontend direction. | Existing CSS stack and dirty refactor use Tailwind/theme patterns. [VERIFIED: `.planning/codebase/STACK.md`] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Django REST Framework | 3.13.1 | Existing `/api/` surface. | Avoid for Phase 5 browser admin unless a migrated JSON route needs API-style denial mapping. [VERIFIED: `.planning/codebase/STACK.md`] |
| django-allauth | 0.51.0 | Google OAuth/session auth. | Existing login state feeds `request.user`; Phase 5 should not alter auth provider behavior. [VERIFIED: `.planning/codebase/STACK.md`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Django function views and forms | New DRF viewsets | Adds API surface and permission classes without need; existing admin UI is template-driven. [VERIFIED: `.planning/codebase/ARCHITECTURE.md`] |
| Existing tenant auth helpers | New global commissioner decorator | Would contradict Phase 2 decision that superuser/commissioner are not tenant bypasses. [VERIFIED: `.planning/STATE.md`] |
| Existing `FamilyInvitation` | Email-invite redesign | Explicitly deferred from Phase 5. [VERIFIED: `.planning/phases/05-family-admin-experience/05-CONTEXT.md`] |

**Installation:** No package installs are needed. [VERIFIED: codebase grep]

## Package Legitimacy Audit

No external packages should be installed for Phase 5. [VERIFIED: codebase grep]

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| None | - | - | - | - | - | No install planned |

**Packages removed due to [SLOP] verdict:** none  
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```text
Owner/Admin browser request
  -> /families/<family_slug>/pools/<pool_slug>/admin/... URL
  -> family_member_required(minimum_role=admin or owner)
  -> request.tenant_context {family, pool, membership}
  -> command form validates untrusted POST/JSON fields
  -> action-specific policy check:
       settings/invites: admin+
       role/status/owner-sensitive: owner only
       last-active-owner protection: required before mutation
  -> transaction.atomic()
       -> scoped ORM lookup/update
       -> FamilyAuditLog row with safe metadata
  -> template/JSON response without raw secrets except one-time invite code
```

### Recommended Project Structure

```text
pickem/pickem_homepage/
|-- urls.py                 # Add tenant admin routes under existing family/pool tree
|-- views.py                # Add focused tenant admin views/helpers near commissioner section or tenant helpers
|-- forms.py                # Add command forms for settings, invites, membership, manual picks, week winners
|-- templates/pickem/
|   `-- family_admin.html   # Practical Tailwind admin hub/tabs/sections
`-- tests.py                # Add FamilyAdminExperienceTests and focused negative tests
```

### Pattern 1: Tenant Admin Guard

**What:** Use `@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)` for admin+ pages and `OWNER` for owner-only routes. [VERIFIED: codebase grep]  
**When to use:** Every Phase 5 admin route under `/families/<family_slug>/pools/<pool_slug>/admin/...`. [VERIFIED: `.planning/phases/05-family-admin-experience/05-CONTEXT.md`]  
**Example:**

```python
# Source: pickem/pickem_homepage/authz.py and pickem_api/authz.py
@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)
def family_admin(request, family_slug, pool_slug):
    tenant_context = request.tenant_context
    ...
```

### Pattern 2: Command Form + Server-Derived Tenant

**What:** Validate only action inputs in Django forms, then assign `family`, `pool`, `actor`, role/status targets, game metadata, and audit metadata in server code. [CITED: https://docs.djangoproject.com/en/4.0/topics/forms/modelforms/]  
**When to use:** Settings, invite creation/revocation, member role/status changes, manual picks, and week winners. [VERIFIED: codebase grep]  
**Example:**

```python
# Source: Django ModelForm/Form docs + existing PickSubmissionForm pattern
form = AdminManualPickForm(request.POST or json_payload)
if form.is_valid():
    game = GamesAndScores.objects.get(
        id=form.cleaned_data["game_id"],
        gameseason=tenant_context.pool.season,
        competition=tenant_context.pool.competition,
    )
    target_membership = FamilyMembership.objects.get(
        family=tenant_context.family,
        user_id=form.cleaned_data["user_id"],
        status=FamilyMembership.Status.ACTIVE,
    )
```

### Pattern 3: Audit in Same Transaction

**What:** Wrap sensitive writes in `transaction.atomic()` and create `FamilyAuditLog` in the same block. [VERIFIED: codebase grep]  
**When to use:** Any action in `FamilyAuditLog.Action` plus membership and settings changes. [VERIFIED: codebase grep]  
**Example:**

```python
# Source: existing create_family/create_family_invite implementation
with transaction.atomic():
    membership.save(update_fields=["role", "status", "updated_at"])
    FamilyAuditLog.objects.create(
        family=tenant_context.family,
        pool=tenant_context.pool,
        actor=request.user,
        action=FamilyAuditLog.Action.MEMBERSHIP_UPDATED,
        target_type="FamilyMembership",
        target_id=str(membership.id),
        metadata={"previous_role": previous_role, "role": membership.role},
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
```

### Anti-Patterns to Avoid

- **Extending `/commissioners/`:** It is global and currently authorized by `UserProfile.is_commissioner`/`is_superuser`, not tenant membership. [VERIFIED: codebase grep]
- **Trusting hidden inputs/buttons:** UI affordances are not authorization; server checks must enforce role, family, pool, object membership, and last-owner rules. [VERIFIED: `.planning/phases/05-family-admin-experience/05-CONTEXT.md`]
- **Logging raw invite codes:** Existing tests assert raw codes are not stored in `FamilyInvitation` or audit metadata. [VERIFIED: codebase grep]
- **Constructing week fields before validation:** Legacy `set_week_winner()` builds `week_{week_number}_winner` directly from JSON. [VERIFIED: codebase grep]
- **Deactivating all banners globally:** Legacy `manage_banner()` deactivates all active banners before saving, which conflicts with family-scoped banners. [VERIFIED: codebase grep]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tenant route authorization | New ad hoc role decorators | `family_member_required` and `require_tenant_context` | Existing helpers already implement Phase 2 302/404/403 behavior. [VERIFIED: codebase grep] |
| CSRF for admin JSON | Custom token scheme or `csrf_exempt` | Django CSRF middleware with `X-CSRFToken` for fetch | Official Django docs support the header pattern for AJAX POST. [CITED: https://docs.djangoproject.com/en/4.0/ref/csrf/] |
| Invite code storage | Raw-code persistence | `generate_invite_code()` + `hash_invite_code()` and one-time display | Existing model stores `code_hash` only and tests assert no raw code fields. [VERIFIED: codebase grep] |
| Role hierarchy | String comparisons scattered in views | `FamilyMembership.Role` plus `role_allows()` | Existing authz helper has role ordering for member/admin/owner. [VERIFIED: codebase grep] |
| Week-winner fields | Dynamic field names from unvalidated request values | Validate integer week `1..18` before using `week_{n}_...` | Legacy dynamic field path is documented fragile. [VERIFIED: `.planning/codebase/CONCERNS.md`] |

**Key insight:** Phase 5 is not a new admin framework; it is a tenantization of existing admin commands behind the already-built tenant authorization boundary. [VERIFIED: `.planning/STATE.md`]

## Common Pitfalls

### Pitfall 1: Global Commissioner Bypass

**What goes wrong:** A legacy commissioner or superuser can mutate tenant data without active family membership. [VERIFIED: codebase grep]  
**Why it happens:** `is_commissioner()` checks `UserProfile.is_commissioner` and `is_superuser`; Phase 2 explicitly rejected these as tenant bypasses. [VERIFIED: `.planning/STATE.md`]  
**How to avoid:** Use active `FamilyMembership` checks for every tenant admin action. [VERIFIED: codebase grep]  
**Warning signs:** New Phase 5 routes import or use `commissioner_required`. [VERIFIED: codebase grep]

### Pitfall 2: Cross-Family Target User Mutation

**What goes wrong:** Admin endpoints accept `user_id` and mutate an outsider or another family member. [VERIFIED: codebase grep]  
**Why it happens:** Legacy manual picks query `User.objects.get(id=user_id)` and all active users globally. [VERIFIED: codebase grep]  
**How to avoid:** Resolve target users through active `FamilyMembership.objects.filter(family=request.tenant_context.family, status='active')`. [VERIFIED: codebase grep]  
**Warning signs:** Admin dropdowns or JSON handlers use `User.objects.filter(is_active=True)` without family membership filtering. [VERIFIED: codebase grep]

### Pitfall 3: Last Owner Lost

**What goes wrong:** The last active owner is demoted/deactivated, leaving no one able to manage the family. [VERIFIED: `.planning/phases/05-family-admin-experience/05-CONTEXT.md`]  
**Why it happens:** The database has no constraint enforcing at least one active owner. [VERIFIED: codebase grep]  
**How to avoid:** Check active owner count inside the same transaction before owner demotion/deactivation/transfer. [ASSUMED]  
**Warning signs:** Membership updates call `.save()` without `select_for_update()` or active-owner count checks. [ASSUMED]

### Pitfall 4: CSRF-Exempt Admin JSON

**What goes wrong:** Session-authenticated admin JSON mutations skip CSRF checks. [VERIFIED: codebase grep]  
**Why it happens:** Legacy `set_week_winner()` and `submit_manual_pick()` are decorated with `@csrf_exempt`. [VERIFIED: codebase grep]  
**How to avoid:** Do not copy `@csrf_exempt`; use Django CSRF token headers for fetch POSTs. [CITED: https://docs.djangoproject.com/en/4.0/ref/csrf/]  
**Warning signs:** New Phase 5 admin POST/JSON routes appear in `rg csrf_exempt pickem/pickem_homepage/views.py`. [VERIFIED: codebase grep]

### Pitfall 5: Dirty Frontend Refactor Churn

**What goes wrong:** Phase 5 executor accidentally overwrites ongoing logo/theme/template/model work. [VERIFIED: `git status --short`]  
**Why it happens:** Many non-planning files are already modified or untracked before Phase 5. [VERIFIED: `git status --short`]  
**How to avoid:** Planner should scope edits to admin routes/views/forms/templates/tests and inspect any touched dirty file before patching. [VERIFIED: `git status --short`]  
**Warning signs:** Plan tasks include broad base/nav/theme rewrites or staging non-planning files. [VERIFIED: `git status --short`]

## Code Examples

### Scoped Invite Revoke

```python
# Source: existing FamilyInvitation fields and FamilyAuditLog pattern
@require_http_methods(["POST"])
@family_member_required(minimum_role=FamilyMembership.Role.ADMIN)
def revoke_family_invite(request, family_slug, pool_slug, invitation_id):
    tenant_context = request.tenant_context
    with transaction.atomic():
        invitation = FamilyInvitation.objects.select_for_update().get(
            id=invitation_id,
            family=tenant_context.family,
        )
        invitation.is_revoked = True
        invitation.save(update_fields=["is_revoked", "updated_at"])
        FamilyAuditLog.objects.create(
            family=tenant_context.family,
            pool=tenant_context.pool,
            actor=request.user,
            action=FamilyAuditLog.Action.INVITATION_REVOKED,
            target_type="FamilyInvitation",
            target_id=str(invitation.id),
            metadata={"role": invitation.role},
        )
```

### Validate Dynamic Week Field

```python
# Source: legacy week winner fields on userSeasonPoints
week_number = form.cleaned_data["week_number"]
if week_number not in range(1, 19):
    return JsonResponse({"success": False, "error": "Invalid week."}, status=400)
winner_field = f"week_{week_number}_winner"
bonus_field = f"week_{week_number}_bonus"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Global `UserProfile.is_commissioner` controls admin pages | Active `FamilyMembership` role controls tenant admin | Phase 2 established policy; Phase 5 completes UI migration | No implicit superuser/commissioner tenant bypass. [VERIFIED: `.planning/STATE.md`] |
| Global commissioner routes mutate all users/picks/standings | Tenant admin routes mutate current family/pool only | Phase 5 | Cross-family admin IDOR coverage becomes mandatory. [VERIFIED: `.planning/phases/05-family-admin-experience/05-CONTEXT.md`] |
| Minimal owner-only invite create on pool home | Admin hub lists/revokes/regenerates simple hash-only invites | Phase 5 | Raw invite codes remain one-time only; email redesign stays deferred. [VERIFIED: `.planning/phases/05-family-admin-experience/05-CONTEXT.md`] |
| Rules display-only | Owner/admin settings edit for represented fields | Phase 5 | Edit `PoolSettings` only; do not redesign scoring settings. [VERIFIED: `.planning/phases/04-family-scoped-app-pages/04-VALIDATION.md`] |

**Deprecated/outdated:**
- `commissioner_required` for tenant admin actions: replace with tenant membership role checks. [VERIFIED: codebase grep]
- `/commissioners/submit-manual-pick/` pick IDs of `user-game`: tenant picks now use pool/user/game identity in Phase 4. [VERIFIED: `.planning/STATE.md`]
- CSRF-exempt admin JSON: do not carry forward. [VERIFIED: codebase grep]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Last-owner protection should use transaction plus row locking/counting because the database has no direct constraint for this business invariant. | Common Pitfalls | Race condition if two owner changes happen concurrently. |
| A2 | `select_for_update()` is sufficient for Phase 5 membership/invite mutation consistency in the deployed database. | Common Pitfalls | SQLite tests may not reveal PostgreSQL lock behavior; planner should keep tests deterministic and code transaction-safe. |

## Open Questions (RESOLVED)

1. **Should Phase 5 include family-scoped banner editing or only preserve current banner isolation?**
   - What we know: `SiteBanner.family` exists and `SiteBannerForm` does not currently expose `family`. [VERIFIED: codebase grep]
   - What's unclear: CONTEXT emphasizes family settings and COMM-03 traceability, but not a full banner-management UI. [VERIFIED: `.planning/phases/05-family-admin-experience/05-CONTEXT.md`]
   - Resolution: Phase 5 should not add a new family-banner editing UI. Preserve and test current-family banner isolation only, and disable legacy global commissioner banner management with the rest of the global commissioner surface. [RESOLVED: plan-checker feedback + D-23 scope control]

2. **Should admins create invites or owners only?**
   - What we know: Phase 3 invite creation is owner-only; Phase 5 says owners/admins should manage simple invites. [VERIFIED: codebase grep] [VERIFIED: `.planning/phases/05-family-admin-experience/05-CONTEXT.md`]
   - What's unclear: Whether admins can create admin-role invites. [VERIFIED: `.planning/phases/05-family-admin-experience/05-CONTEXT.md`]
   - Resolution: Admins may create member-role invites only. Owners may create member or admin invites if the form explicitly allowlists those roles. Do not introduce email invite delivery or raw-code redisplay. [RESOLVED: D-08 through D-11 and D-27]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python virtualenv | Django commands/tests | yes | Python 3.10.6 | Use `python3` only for non-Django tooling. [VERIFIED: shell] |
| Django | App/test runtime | yes | 4.0.2 | None. [VERIFIED: shell] |
| Node.js | Tailwind build if templates/classes change | yes | v25.2.1 | Avoid CSS build only if no CSS/template class changes. [VERIFIED: shell] |
| npm | Tailwind build | yes | 11.6.2 | None for CSS build. [VERIFIED: shell] |
| Local dev server | Curl validation | Assumed running per AGENTS | `http://localhost:8000` | Use Django tests if server unavailable. [VERIFIED: `AGENTS.md`] |

**Missing dependencies with no fallback:** none found. [VERIFIED: shell]  
**Missing dependencies with fallback:** local dev server was not probed during research to avoid changing runtime state; AGENTS says assume it is already running. [VERIFIED: `AGENTS.md`]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Django test runner 4.0.2 [VERIFIED: shell] |
| Config file | `pickem/pickem/test_settings.py` [VERIFIED: codebase grep] |
| Quick run command | `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.FamilyAdminExperienceTests --settings=pickem.test_settings --verbosity=2` [VERIFIED: shell] |
| Full suite command | `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=2` [VERIFIED: `.planning/phases/04-family-scoped-app-pages/04-VALIDATION.md`] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTHZ-03 | Member/outsider/inactive cannot access admin hub or POST actions; admin vs owner split enforced. | integration | `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.FamilyAdminExperienceTests --settings=pickem.test_settings --verbosity=2` | Missing - Wave 0 |
| AUTHZ-05 | Forged family/pool/user/game/week IDs cannot cross tenant boundaries. | integration | same focused command | Missing - Wave 0 |
| INV-02 | Invite list/revoke/regenerate respects expiry/revocation/max-use metadata and no raw code redisplay. | integration | same focused command | Missing - Wave 0 |
| POOL-04 | Family/pool/settings edits are current-tenant only and audit logged. | integration | same focused command | Missing - Wave 0 |
| COMM-03 | Family admin does not leak another family's banner metadata or globally mutate banner rows. | integration | same focused command | Missing - Wave 0 |
| SEC-01 | Every sensitive mutation creates scoped `FamilyAuditLog` metadata without secrets/raw invite codes. | unit/integration | same focused command | Missing - Wave 0 |

### Sampling Rate

- **Per task commit:** focused `FamilyAdminExperienceTests` command plus `manage.py check`. [VERIFIED: shell]
- **Per wave merge:** `cd pickem && ../venv/bin/python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings --verbosity=2`. [VERIFIED: `.planning/phases/04-family-scoped-app-pages/04-VALIDATION.md`]
- **Phase gate:** full suite plus migration dry-run before `$gsd-verify-work`. [VERIFIED: `.planning/phases/04-family-scoped-app-pages/04-VALIDATION.md`]

### Wave 0 Gaps

- [ ] `pickem_homepage.tests.FamilyAdminExperienceTests` - admin hub access, role split, invite/member/settings/audit/manual pick/week-winner coverage. [VERIFIED: codebase grep]
- [ ] Form tests for new admin command forms - invalid week, invalid role/status transition, outsider target user, unsafe invite role. [ASSUMED]
- [ ] CSRF tests with `Client(enforce_csrf_checks=True)` for every Phase 5 POST/JSON mutation. [VERIFIED: existing tests pattern]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | Existing Django/allauth session auth; no auth provider changes in Phase 5. [VERIFIED: `.planning/codebase/STACK.md`] |
| V3 Session Management | yes | Django session auth and CSRF-protected POSTs; do not put invite codes/session IDs in URLs beyond one-time invite acceptance flow. [CITED: https://docs.djangoproject.com/en/4.0/ref/csrf/] |
| V4 Access Control | yes | `family_member_required`, server-side role/action checks, deny-by-default for non-members. [VERIFIED: codebase grep] [CITED: https://owasp.org/Top10/2021/A01_2021-Broken_Access_Control/] |
| V5 Input Validation | yes | Django forms plus explicit ID/week/role allowlists before ORM mutation. [CITED: https://docs.djangoproject.com/en/4.0/topics/forms/modelforms/] |
| V6 Cryptography | yes | Do not hand-roll new crypto; keep invite hashes via existing SHA-256 helper and do not store raw codes. [VERIFIED: codebase grep] |
| V7 Error Handling and Logging | yes | `FamilyAuditLog` for sensitive mutations; avoid `str(e)` leakage in JSON responses. [VERIFIED: codebase grep] [CITED: https://devguide.owasp.org/en/04-design/02-web-app-checklist/09-logging-monitoring/] |

### Known Threat Patterns for Django Tenant Admin

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR via forged family/pool slug or object ID | Elevation of Privilege / Information Disclosure | Resolve `request.tenant_context`; scope every object lookup to `tenant_context.family` or `tenant_context.pool`. [VERIFIED: codebase grep] |
| CSRF against admin JSON mutation | Tampering | Remove `csrf_exempt`; require CSRF token header for fetch POST. [CITED: https://docs.djangoproject.com/en/4.0/ref/csrf/] |
| Privilege escalation by admin/member role edit | Elevation of Privilege | Owner-only role/status routes plus last-owner protection. [VERIFIED: `.planning/phases/05-family-admin-experience/05-CONTEXT.md`] |
| Audit log secret leakage | Information Disclosure | Log IDs/metadata only; never raw invite codes or CSRF/session data. [VERIFIED: existing tests] |
| Dynamic field injection/invalid field errors | Tampering / DoS | Validate week integer `1..18` before constructing weekly field names. [VERIFIED: `.planning/codebase/CONCERNS.md`] |

## Scope Boundaries

- Do not plan Phase 6 cron/scoring hardening, pool-aware background jobs, non-null tenant constraints, production backup/rollback, CSRF hardening outside touched Phase 5 routes, or broad settings/security hardening. [VERIFIED: `.planning/phases/05-family-admin-experience/05-CONTEXT.md`]
- Do not redesign invites around email delivery or new delivery infrastructure. [VERIFIED: `.planning/phases/05-family-admin-experience/05-CONTEXT.md`]
- Do not broaden into advanced multi-pool admin UX. [VERIFIED: `.planning/phases/05-family-admin-experience/05-CONTEXT.md`]
- Do not modify or stage non-planning dirty files unless a later executor phase explicitly needs a Phase 5 code change there and first reads the current user edits. [VERIFIED: `git status --short`]

## Sources

### Primary (HIGH confidence)

- `AGENTS.md` - project constraints and validation commands. [VERIFIED: file read]
- `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md` - project scope, requirements, locked decisions, phase status. [VERIFIED: file read]
- `.planning/phases/05-family-admin-experience/05-CONTEXT.md` - Phase 5 locked decisions and deferred scope. [VERIFIED: file read]
- `.planning/phases/04-family-scoped-app-pages/04-VALIDATION.md` - Phase 4 handoff and explicit non-claims. [VERIFIED: file read]
- `pickem/pickem_api/authz.py`, `pickem/pickem_homepage/authz.py`, `pickem/pickem_homepage/views.py`, `pickem/pickem_homepage/urls.py`, `pickem/pickem_api/models.py`, `pickem/pickem_homepage/forms.py`, `pickem/pickem/context_processors.py`, `pickem/pickem_homepage/tests.py` - implementation facts. [VERIFIED: codebase grep]

### Secondary (MEDIUM confidence)

- Django 4.0 authentication docs - `login_required`, `permission_required`, `request.user`, permissions. [CITED: https://docs.djangoproject.com/en/4.0/topics/auth/default/]
- Django 4.0 CSRF docs - `X-CSRFToken` AJAX guidance and `csrf_protect`. [CITED: https://docs.djangoproject.com/en/4.0/ref/csrf/]
- Django 4.0 view decorator docs - `require_http_methods`, `require_POST`, `never_cache`. [CITED: https://docs.djangoproject.com/en/4.0/topics/http/decorators/]
- Django 4.0 ModelForm docs - validation/save patterns. [CITED: https://docs.djangoproject.com/en/4.0/topics/forms/modelforms/]

### Tertiary (LOW confidence)

- OWASP ASVS project overview and OWASP Developer Guide ASVS category summaries. [CITED: https://owasp.org/www-project-application-security-verification-standard/] [CITED: https://devguide.owasp.org/en/11-security-gap-analysis/01-guides/02-asvs/]
- OWASP Top 10 Broken Access Control prevention guidance. [CITED: https://owasp.org/Top10/2021/A01_2021-Broken_Access_Control/]
- OWASP logging/monitoring checklist. [CITED: https://devguide.owasp.org/en/04-design/02-web-app-checklist/09-logging-monitoring/]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - current project files and shell probes confirm versions; no new packages. [VERIFIED: shell]
- Architecture: HIGH - current code paths and prior phase summaries identify tenant auth, models, routes, and legacy commissioner behavior. [VERIFIED: codebase grep]
- Pitfalls: HIGH for codebase-specific risks, MEDIUM for Django CSRF/auth guidance, LOW for OWASP category framing. [VERIFIED: codebase grep]

**Research date:** 2026-07-01  
**Valid until:** 2026-07-31 for codebase-local findings; revisit sooner if dirty frontend/schema refactor is merged before planning. [ASSUMED]

## RESEARCH COMPLETE
