# Phase 5: Family Admin Experience - Context

**Gathered:** 2026-07-01T02:24:03Z
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 5 replaces legacy global commissioner behavior with tenant-scoped family owner/admin management. It delivers a family admin hub under explicit family/pool context for family settings, pool/rules settings, member and role management, invite management around the current invite model, audit log visibility, and tenant-scoped manual pick/week-winner actions. It must not claim production migration hardening, cron/scoring job hardening, non-null tenant constraints, or the later email-based invite redesign.

</domain>

<decisions>
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning and phase scope

- `.planning/PROJECT.md` — Multi-tenancy project goal and security-first framing.
- `.planning/REQUIREMENTS.md` — Phase 5 requirements: `AUTHZ-03`, `AUTHZ-05`, `INV-02`, `POOL-04`, `COMM-03`, and `SEC-01` traceability.
- `.planning/ROADMAP.md` — Phase 5 scope and definition of done.
- `.planning/STATE.md` — Locked decisions and completion summaries from Phases 1-4.

### Prior phase decisions

- `.planning/phases/01-domain-schema-foundation/01-CONTEXT.md` — Family/pool/membership/invitation/audit domain model decisions.
- `.planning/phases/02-authorization-foundation/02-CONTEXT.md` — 404/403/login behavior, role hierarchy, and no superuser/commissioner tenant bypass decisions.
- `.planning/phases/03-onboarding-and-family-selection/03-CONTEXT.md` — Invite minimum, tenant URL shape, and switcher/current-context decisions.
- `.planning/phases/04-family-scoped-app-pages/04-CONTEXT.md` — Tenant URL, page scoping, private data, and settings-editing handoff decisions.
- `.planning/phases/04-family-scoped-app-pages/04-VALIDATION.md` — Confirms Phase 4 did not claim family admin editing, invite/role management UI, or production hardening.

### Existing implementation and patterns

- `.planning/codebase/STACK.md` — Django/Tailwind/test/deployment stack summary.
- `.planning/codebase/ARCHITECTURE.md` — Existing homepage, API, commissioner, forms, context processor, and cron architecture.
- `.planning/codebase/CONVENTIONS.md` — Django naming/style/testing conventions and large-view cautions.
- `.planning/codebase/CONCERNS.md` — Known security and fragility concerns around commissioner workflows, CSRF, dynamic week fields, and frontend refactor risk.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `pickem_api.models.Family`, `Pool`, `FamilyMembership`, `PoolSettings`, `FamilyInvitation`, and `FamilyAuditLog` provide the core data model for Phase 5.
- `pickem_homepage.authz.family_member_required` and `pickem_api.authz` tenant helpers provide the required membership/role guard pattern.
- Existing invite helpers in `pickem_homepage.views` include `normalize_invite_code`, `hash_invite_code`, `generate_invite_code`, and minimal owner-created invite creation.
- Existing commissioner views in `pickem_homepage.views` contain manual pick, user-pick retrieval, and week-winner logic to migrate rather than expand globally.
- Existing templates include `commissioners.html` and tenant gameplay templates that show current family/pool context; admin hub templates should align with the current Tailwind refactor.

### Established Patterns

- Browser routes live in `pickem_homepage.urls` and render Django templates from `pickem_homepage/templates/pickem/`.
- Tenant routes use `/families/<family_slug>/pools/<pool_slug>/...` and derive current context server-side.
- New tenant reads/writes should start from `request.tenant_context`, not client-supplied family/pool IDs.
- Sensitive actions should create `FamilyAuditLog` rows and should not expose raw invite codes or secrets in logs.
- Tests live in `pickem_homepage/tests.py` and should include negative cross-family and wrong-role coverage.

### Integration Points

- Add family admin routes under the explicit tenant URL tree in `pickem/pickem_homepage/urls.py`.
- Implement admin views/forms in or near `pickem/pickem_homepage/views.py` and `forms.py`, keeping changes focused despite the large existing view module.
- Update tenant navigation/templates to expose admin entry points only as a UX affordance for authorized roles, while preserving server-side authorization.
- Disable or deny legacy commissioner URLs/actions in `pickem_homepage.urls`/`views.py` after tenant-scoped replacements exist.
- Extend `FamilyAuditLog.Action` only if existing action choices cannot represent Phase 5 events safely.

</code_context>

<specifics>
## Specific Ideas

- The admin surface should be a dedicated family admin hub, not a marketing landing page and not scattered full controls across existing gameplay pages.
- The UI should be polished enough to match the nearly complete frontend refactor and current Tailwind/theme direction.
- Invite email delivery and a redesigned email-first invitation model are desired later, but they are not part of Phase 5.
- Keep current invite-code behavior simple and safe until the later email-invite refactor.

</specifics>

<deferred>
## Deferred Ideas

- Email-based invitation flow and invite model redesign. This should be a later phase because it changes product behavior, data model/API expectations, and likely email delivery infrastructure.
- Production cron/scoring hardening and pool-aware background scoring jobs remain Phase 6.
- Non-null tenant constraints, strict production migration rollback plans, and broader settings/security hardening remain Phase 6.
- Advanced multi-pool admin UX beyond the current/default pool remains later scope unless needed by current Phase 5 routes.

</deferred>

---

*Phase: 5-Family Admin Experience*
*Context gathered: 2026-07-01T02:24:03Z*
