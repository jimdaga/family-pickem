# Family Pickem Multi-Tenancy

## What This Is

Family Pickem is an existing Django NFL pick'em web application evolving from one global shared league into private family/pool tenancy. The product should let different families create, manage, join, and play separate pick'em pools without leaking picks, standings, dashboards, message-board data, settings, or admin controls across families.

## Core Value

Families can run private pick'em pools with strict server-enforced data isolation.

## Requirements

### Validated

- ✓ Google sign-in, NFL scores/week navigation, picks, standings, rules, profiles, and message-board discussion exist — prior product
- ✓ Private families/pools, memberships, roles, invitations, onboarding, and family switching — v1.0 phases 1–5
- ✓ Tenant-scoped gameplay/admin reads and writes with cross-family negative coverage — v1.0 phases 2–5
- ✓ Family owners/admins can manage family settings, members, invites, and commissioner workflows — v1.0 phase 5
- ✓ Authorized family-logo uploads accept only bounded JPEG/PNG/WebP sources and persist a fresh 256×256 WebP asset — v1.1 phase 6
- ✓ Family-logo references are server-owned, private S3-backed objects; legacy arbitrary family-logo URLs are removed without remote fetches — v1.1 phase 6

### Active

- [ ] Deliver S3/ESO configuration without exposing cloud credentials or allowing arbitrary upload content.
- [ ] Make remaining background scoring, production migration, and hardening work separately planned follow-on milestones.

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
| Store family logos as server-processed S3 objects | Avoids external URL UX/security issues and bounds client delivery cost. | Phase 6 foundation complete; delivery/IAM remains in phases 7–8. |

## Current Milestone: v1.1 Family Logo Uploads

**Goal:** Replace family-logo URLs with a secure commissioner-page upload and crop flow backed by S3.

**Target features:**
- A commissioner-page upload, preview, crop/position, save, replace, and remove experience for family logos.
- Strict server-side raster-image validation, sanitization/re-encoding, and fixed-size delivery assets.
- Private S3 storage and Kubernetes credentials/configuration sourced through ESO and AWS Secrets Manager.
- Automated security, authorization, and upload-processing coverage.

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
*Last updated: 2026-07-18 after completing v1.1 Phase 6 Secure Logo Foundation*
