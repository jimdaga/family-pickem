# Phase 05 Validation: Family Admin Experience

**Status:** Planned
**Phase goal:** Replace global commissioner behavior with family owner/admin management.
**Nyquist result:** Planned coverage maps each Phase 05 requirement and locked decision to an executable plan and automated verification target.

## Plan Set

| Plan | Wave | Objective | Key Verification |
|------|------|-----------|------------------|
| `05-01-PLAN.md` | 1 | Tenant admin hub, scoped audit display, and admin navigation | `FamilyAdminExperienceTests`; hub auth split |
| `05-02-PLAN.md` | 2 | Family/pool/settings and family-banner editing | `FamilyAdminExperienceTests`; migration dry-run |
| `05-03-PLAN.md` | 3 | Member role/status management with owner protections | `FamilyAdminExperienceTests`; last-owner negative tests |
| `05-04-PLAN.md` | 4 | Simple current-model invite management | `FamilyAdminExperienceTests`; raw-code non-disclosure tests |
| `05-05-PLAN.md` | 5 | Tenant-scoped manual pick submission and user-pick retrieval | `FamilyAdminExperienceTests`; forged user/game/body tests |
| `05-06-PLAN.md` | 6 | Tenant-scoped week-winner tools and legacy commissioner denial | `FamilyAdminExperienceTests`; app-level tests |
| `05-07-PLAN.md` | 7 | Final cross-feature validation and handoff | focused tests, app tests, full suite, migration dry-run, curl |

## Multi-Source Coverage Audit

### GOAL Coverage

| Source Item | Coverage | Plan(s) |
|-------------|----------|---------|
| Replace global commissioner behavior with family owner/admin management | COVERED | 05-01, 05-03, 05-05, 05-06, 05-07 |
| Family settings | COVERED | 05-02 |
| Member management | COVERED | 05-03 |
| Invite management | COVERED | 05-04 |
| Role management | COVERED | 05-03 |
| Audit log display | COVERED | 05-01, 05-07 |
| Tenant-scoped manual pick admin actions | COVERED | 05-05 |
| Tenant-scoped week-winner admin actions | COVERED | 05-06 |
| Owners/admins can manage safely | COVERED | 05-01 through 05-07 |
| Members cannot access admin actions by direct URL/API call | COVERED | 05-01 through 05-07 |

### REQ Coverage

| Requirement | Coverage | Plan(s) | Verification Target |
|-------------|----------|---------|---------------------|
| AUTHZ-03: Owner/admin actions require least-privilege role checks | COVERED | 05-01, 05-03, 05-04, 05-05, 05-06, 05-07 | `FamilyAdminExperienceTests` owner/admin/member/outsider/inactive matrix |
| AUTHZ-05: Client-provided IDs validated against server-resolved membership and allowed objects | COVERED | 05-02, 05-03, 05-04, 05-05, 05-06, 05-07 | forged slug/body/user/game/week/invite/membership/banner tests |
| INV-02: Invite codes can expire, be revoked, and be regenerated | COVERED | 05-04, 05-07 | invite list/revoke/revoke-and-create tests |
| POOL-04: Rules/settings visible and editable in appropriate context | COVERED | 05-02, 05-07 | tenant settings edit tests |
| COMM-03: Site/family banners do not leak across families | COVERED | 05-02, 05-07 | family banner edit/list isolation tests |
| SEC-01: Security-sensitive admin actions are audit logged | COVERED | 05-01 through 05-07 | audit metadata tests for settings, membership, invites, picks, winners |

### RESEARCH Coverage

| Research Finding | Coverage | Plan(s) |
|------------------|----------|---------|
| Use existing Django function views and `family_member_required` | COVERED | 05-01 through 05-06 |
| Keep Phase 5 browser admin template-driven rather than new DRF viewsets | COVERED | 05-01 through 05-06 |
| Derive family/pool from `request.tenant_context` | COVERED | 05-01 through 05-06 |
| Use command forms and server-side object resolution | COVERED | 05-02 through 05-06 |
| Audit sensitive writes in the same transaction | COVERED | 05-02 through 05-06 |
| Do not store or redisplay raw invite codes | COVERED | 05-04, 05-07 |
| Validate week numbers before dynamic fields | COVERED | 05-06, 05-07 |
| Disable legacy global commissioner routes after tenant replacements | COVERED | 05-06, 05-07 |
| Preserve dirty frontend/schema work | COVERED | all plans |
| No package installs are needed | COVERED | all plans |

### CONTEXT Decision Coverage

| Decision | Coverage | Plan(s) |
|----------|----------|---------|
| D-01 dedicated tenant admin hub | COVERED | 05-01 |
| D-02 admin hub discoverable only as owner/admin affordance | COVERED | 05-01, 05-06 |
| D-03 admin hub is primary admin surface | COVERED | 05-01, 05-04 |
| D-04 member management | COVERED | 05-03 |
| D-05 strong owner protections | COVERED | 05-03 |
| D-06 last active owner safety | COVERED | 05-03 |
| D-07 server-side role/status checks | COVERED | 05-03 |
| D-08 existing invitation model, no email redesign | COVERED | 05-04 |
| D-09 invite create/list/revoke/metadata | COVERED | 05-04 |
| D-10 one-time raw invite code display | COVERED | 05-04 |
| D-11 revoke-and-create regeneration | COVERED | 05-04 |
| D-12 family/pool/settings editing | COVERED | 05-02 |
| D-13 tenant-scoped settings writes and audit | COVERED | 05-02 |
| D-14 no scoring-rule model redesign | COVERED | 05-02 |
| D-15 manual pick/user-pick/week-winner tenant migration | COVERED | 05-05, 05-06 |
| D-16 pool-scoped admin action validation | COVERED | 05-05, 05-06 |
| D-17 validate week numbers before dynamic fields | COVERED | 05-06 |
| D-18 audit manual pick and winner actions | COVERED | 05-05, 05-06 |
| D-19 recent audit activity visible to admins | COVERED | 05-01 |
| D-20 members cannot view audit log | COVERED | 05-01 |
| D-21 polished UI aligned with frontend refactor | COVERED | 05-01 through 05-06 |
| D-22 practical operational screens | COVERED | 05-01 through 05-06 |
| D-23 preserve unrelated frontend refactor work | COVERED | all plans |
| D-24 disable legacy global commissioner routes | COVERED | 05-06 |
| D-25 no private global admin path remains | COVERED | 05-06, 05-07 |
| D-26 Phase 2 auth/403/404 split | COVERED | 05-01 through 05-07 |
| D-27 least-privilege owner/admin action split | COVERED | 05-03, 05-04, 05-05, 05-06 |
| D-28 negative tests for member/outsider/inactive/forged IDs | COVERED | 05-01 through 05-07 |

## Planned Final Negative Test Evidence

| Surface | Tampering Covered | Planned Evidence |
|---------|-------------------|------------------|
| Admin hub/audit | slug tampering, member/outsider/inactive denial, other-family audit rows | `FamilyAdminExperienceTests` |
| Settings and banner | forged family/pool/banner IDs, cross-family banner leakage | `FamilyAdminExperienceTests` |
| Members | forged membership/user IDs, owner/admin/member split, last-owner loss | `FamilyAdminExperienceTests` |
| Invites | forged invite IDs, unsafe role requests, raw-code redisplay | `FamilyAdminExperienceTests` |
| Manual picks | forged user/game/pool/season/week/correctness fields | `FamilyAdminExperienceTests` |
| Week winners | invalid weeks, forged winner user, cross-pool rows | `FamilyAdminExperienceTests` |
| Legacy commissioner | old page/JSON URLs no longer render or mutate global admin tools | `FamilyAdminExperienceTests` |

## Out-of-Phase Guardrails

| Item | Status |
|------|--------|
| Email-based invitation flow and invite model redesign | NOT CLAIMED |
| Production cron/scoring job pool hardening | NOT CLAIMED |
| Non-null tenant constraints and production migration backup/rollback hardening | NOT CLAIMED |
| Broad settings/security hardening outside Phase 5 touched routes | NOT CLAIMED |
| Advanced multi-active-pool admin UX | NOT CLAIMED |

## Dirty Worktree Guardrail

Executors must treat the current non-planning frontend/logo/schema/admin/migration/screenshot work as user-owned. Before editing dirty files such as `base.html`, `family_pool_home.html`, `rules.html`, `commissioners.html`, `pickem_api/models.py`, `pickem_api/admin.py`, CSS, logo assets, or Tailwind config, they must inspect current content and stage only Phase 5 plan-relevant hunks.

## Final Verification Checklist

- [ ] `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings`
- [ ] `cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings`
- [ ] `cd pickem && ../venv/bin/python manage.py test pickem_homepage.tests.FamilyAdminExperienceTests --settings=pickem.test_settings --verbosity=2`
- [ ] `cd pickem && ../venv/bin/python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings --verbosity=2`
- [ ] `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=2`
- [ ] `curl -s --max-time 5 http://localhost:8000 | head -40`

## Completion Evidence

| Evidence | Status | Reference |
|----------|--------|-----------|
| Admin hub summary | PLANNED | `05-01-SUMMARY.md` |
| Settings summary | PLANNED | `05-02-SUMMARY.md` |
| Members summary | PLANNED | `05-03-SUMMARY.md` |
| Invites summary | PLANNED | `05-04-SUMMARY.md` |
| Manual picks summary | PLANNED | `05-05-SUMMARY.md` |
| Winners/legacy denial summary | PLANNED | `05-06-SUMMARY.md` |
| Final validation summary | PLANNED | `05-07-SUMMARY.md` |

## Phase 05 Handoff

Phase 05 plans are complete when owners/admins can manage tenant admin workflows safely, members cannot access admin actions by direct request, and legacy global commissioner routes no longer expose private global admin behavior. Phase 06 remains responsible for cron/scoring pool hardening and production migration hardening.
