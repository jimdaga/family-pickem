# Requirements: Family Pickem Multi-Tenancy

**Defined:** 2026-06-28  
**Core Value:** Families can run private pick'em pools with strict server-enforced data isolation.

## v1 Requirements

### Tenant Domain

- [x] **TEN-01**: A signed-in user can create a family.
- [x] **TEN-02**: A family has at least one pool for a season/competition.
- [x] **TEN-03**: A signed-in user can belong to one or more families.
- [x] **TEN-04**: A family membership has a role of owner, admin, or member.
- [x] **TEN-05**: Existing global production data is assigned to a default legacy family and pool.

### Authorization

- [x] **AUTHZ-01**: Every family/pool read path checks authenticated membership server-side.
- [x] **AUTHZ-02**: Every family/pool write path checks authenticated membership server-side.
- [x] **AUTHZ-03**: Owner/admin actions require least-privilege role checks.
- [x] **AUTHZ-04**: Users outside a family cannot view or infer private family picks, standings, members, invitations, settings, dashboards, profiles, or message-board data.
- [x] **AUTHZ-05**: Client-provided family, pool, user, season, week, and game identifiers are validated against server-resolved membership and allowed objects.

### Invitations And Onboarding

- [x] **INV-01**: Owners/admins can create invite links or codes.
- [x] **INV-02**: Invite codes can expire, be revoked, and be regenerated.
- [x] **INV-03**: A signed-in user with no family sees onboarding to create or join a family.
- [x] **INV-04**: A signed-in user with multiple families can switch active family/pool context.

### Pool Gameplay

- [x] **POOL-01**: Picks are scoped to a pool.
- [x] **POOL-02**: Standings and weekly winners are scoped to a pool.
- [x] **POOL-03**: Scores can use global NFL game data while showing only pool-scoped pick overlays.
- [x] **POOL-04**: Rules/settings are visible and editable in the appropriate family/pool context.
- [ ] **POOL-05**: Background scoring jobs update only the intended pool data.

### Community And Profiles

- [x] **COMM-01**: Message-board posts, comments, and votes are scoped to a family or pool.
- [x] **COMM-02**: Family members can see member/profile stats only within allowed family context.
- [x] **COMM-03**: Site/family banners do not leak across families.

### Audit And Hardening

- [x] **SEC-01**: Security-sensitive admin actions are audit logged.
- [ ] **SEC-02**: Session-authenticated JSON mutations use CSRF protection or a documented secure alternative.
- [x] **SEC-03**: Cross-family isolation has automated negative tests.
- [x] **SEC-04**: Cache keys and precomputed data are family/pool scoped.
- [ ] **SEC-05**: Production migration has backup, rollback, and verification steps.

## v2 Requirements

### Advanced Pools

- **ADV-01**: One family can run multiple active pools at the same time.
- **ADV-02**: Pools can have custom scoring rules beyond current settings.
- **ADV-03**: Families can archive old pools and browse historical pool dashboards.

### Visibility

- **VIS-01**: Families can optionally publish a read-only public leaderboard.
- **VIS-02**: Family owners can configure whether member profiles are visible outside the family.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Native mobile apps | Web migration is the current scope |
| Payments/subscriptions | Not required for private family tenancy |
| Custom NFL schedules | Global NFL reference data is sufficient for v1 |
| Full standings normalization | Useful later, but tenant boundaries can be added before replacing denormalized weekly columns |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TEN-01 | Phase 3 | Complete |
| TEN-02 | Phase 1 | Complete |
| TEN-03 | Phase 1 | Complete |
| TEN-04 | Phase 1 | Complete |
| TEN-05 | Phase 1 | Complete |
| AUTHZ-01 | Phase 2, Phase 4 | Complete |
| AUTHZ-02 | Phase 2, Phase 4 | Complete |
| AUTHZ-03 | Phase 2, Phase 5 | Complete |
| AUTHZ-04 | Phase 2, Phase 4 | Complete |
| AUTHZ-05 | Phase 2, Phase 4, Phase 5 | Complete |
| INV-01 | Phase 3, Phase 5 | Complete |
| INV-02 | Phase 3, Phase 5 | Complete |
| INV-03 | Phase 3 | Complete |
| INV-04 | Phase 3 | Complete |
| POOL-01 | Phase 1, Phase 4 | Complete |
| POOL-02 | Phase 1, Phase 4, Phase 6 | Complete |
| POOL-03 | Phase 4 | Complete |
| POOL-04 | Phase 4, Phase 5 | Complete |
| POOL-05 | Phase 6 | Pending |
| COMM-01 | Phase 1, Phase 4 | Complete |
| COMM-02 | Phase 4 | Complete |
| COMM-03 | Phase 1, Phase 5 | Complete |
| SEC-01 | Phase 1, Phase 5 | Complete |
| SEC-02 | Phase 6 | Pending |
| SEC-03 | Phase 2, Phase 4, Phase 7 | Complete |
| SEC-04 | Phase 4, Phase 6 | Complete |
| SEC-05 | Phase 6 | Pending |

**Coverage:**

- v1 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0

---
*Requirements defined: 2026-06-28*
*Last updated: 2026-06-28 after Phase 1 Plan 03 execution*
