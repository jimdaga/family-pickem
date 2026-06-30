# Family Pickem Multi-Tenancy

## What This Is

Family Pickem is an existing Django NFL pick'em web application evolving from one global shared league into private family/pool tenancy. The product should let different families create, manage, join, and play separate pick'em pools without leaking picks, standings, dashboards, message-board data, settings, or admin controls across families.

## Core Value

Families can run private pick'em pools with strict server-enforced data isolation.

## Requirements

### Validated

- ✓ Google sign-in exists — existing
- ✓ Users can view NFL scores and week navigation — existing
- ✓ Users can submit and edit weekly picks — existing
- ✓ Users can view standings, rules, player profiles, and message-board discussion — existing
- ✓ Commissioners can access global admin workflows — existing
- ✓ Background jobs update games, picks, standings, and records — existing

### Active

- [ ] Add first-class `Family` and `Pool` domain boundaries.
- [ ] Add memberships, roles, invitations, settings, and audit logging for sensitive admin actions.
- [ ] Migrate existing global data into a default legacy family/pool.
- [ ] Enforce server-side family/pool authorization on every read and write path.
- [ ] Add onboarding for create-family and join-family flows.
- [ ] Add a visible family/pool switcher and tenant-aware URLs.
- [ ] Scope picks, standings, stats, message board, profile context, and admin controls by tenant.
- [ ] Add automated negative tests proving cross-family isolation.

### Out of Scope

- Native mobile apps — web-first scope.
- Custom per-family NFL schedules — keep NFL games/weeks/teams global reference data for v1.
- Multiple simultaneous pools UI — schema should support it, but v1 UI can create one default pool per family.
- Payment/subscription features — not part of this migration.

## Context

The existing codebase is a Django 4.0.2 monolith with `pickem_api` for models/API/cron scripts and `pickem_homepage` for template views/forms/UI. Current league data is global and mostly scoped only by season/week/user identifiers. The app is also mid-migration from Bootstrap to Tailwind.

Critical current risks:

- No family/pool/membership tenant boundary exists.
- Several API reads are public or read-open.
- `UserProfile.is_commissioner` is a global privilege.
- Picks and standings are global by season/week/user fields.
- Message board and site banners are global.
- Some JSON endpoints are CSRF-exempt.
- Pick creation currently accepts client-controlled fields that should be server-derived.

## Constraints

- **Security**: Tenant isolation is non-negotiable; every family-scoped table and route needs a clear server-enforced boundary.
- **Migration**: Existing production data must be preserved and mapped into a default legacy family/pool.
- **Delivery**: Use small, independently reviewable milestones rather than one large refactor.
- **Compatibility**: Existing global routes should be redirected or bridged during migration rather than broken abruptly.
- **Reference data**: NFL games, weeks, and teams should remain global unless future requirements require custom schedules.
- **Testing**: Each tenant-scoped feature needs positive and negative authorization tests.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Separate `Family` from `Pool` | Family is the social/admin container; Pool is the competition/scoring container. This avoids a future schema break when one family wants multiple pools or archived seasons. | — Pending |
| Keep NFL games/weeks/teams global | These are reference data shared by all pools and do not need tenant duplication for v1. | — Pending |
| Use explicit family/pool URLs | Tenant context must be visible and not only session-derived. | — Pending |
| Add schema foundation before route migration | Existing data needs a tenant key before views and APIs can be safely scoped. | — Pending |
| Use default legacy family/pool migration | Preserves production data and gives existing users a safe continuity path. | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition**:
1. Requirements invalidated? Move to Out of Scope with reason.
2. Requirements validated? Move to Validated with phase reference.
3. New requirements emerged? Add to Active.
4. Decisions to log? Add to Key Decisions.
5. "What This Is" still accurate? Update if drifted.

**After each milestone**:
1. Full review of all sections.
2. Core Value check: still the right priority?
3. Audit Out of Scope: reasons still valid?
4. Update Context with current state.

---
*Last updated: 2026-06-28 after discovery approval*
