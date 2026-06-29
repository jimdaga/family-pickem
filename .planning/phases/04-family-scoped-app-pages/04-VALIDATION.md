# Phase 04 Validation: Family-Scoped App Pages

**Status:** Planned  
**Phase goal:** Move user-facing gameplay pages into explicit tenant context.  
**Nyquist rule:** Every scoped behavior below has an automated verification target in a Phase 04 plan before implementation is considered complete.

## Plan Set

| Plan | Wave | Objective | Key Verification |
|------|------|-----------|------------------|
| `04-01-PLAN.md` | 1 | Tenant dashboard/home and signed-in legacy home redirects | `manage.py test pickem_homepage` |
| `04-02-PLAN.md` | 2 | Tenant picks submit/edit with server-derived fields | `manage.py test pickem_homepage` |
| `04-03-PLAN.md` | 3 | Tenant scores, standings, weekly winners, and display-only rules | `manage.py test pickem_homepage` |
| `04-04-PLAN.md` | 4 | Tenant profiles, players, and family-private message-board AJAX | `manage.py test pickem_homepage` |
| `04-05-PLAN.md` | 5 | Shared navigation plus dashboard/picks/scores tenant link cleanup | `manage.py test pickem_homepage` |
| `04-06-PLAN.md` | 6 | Remaining template link cleanup, final negative coverage, final verification/handoff | `manage.py check`, `makemigrations --check --dry-run`, focused and full Django tests |

## Multi-Source Coverage Audit

### GOAL Coverage

| Source Item | Coverage | Plan(s) |
|-------------|----------|---------|
| Move user-facing gameplay pages into explicit tenant context | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |
| Dashboard/home | COVERED | 04-01 |
| Scores | COVERED | 04-03 |
| Standings | COVERED | 04-03 |
| Picks | COVERED | 04-02 |
| Rules | COVERED | 04-03 |
| Profiles and players | COVERED | 04-04 |
| Message board | COVERED | 04-04 |
| Tenant-aware URLs and links | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |
| Tenant-scoped query filters for picks, standings, stats, and community content | COVERED | 04-01, 04-02, 04-03, 04-04 |
| Legacy route redirects | COVERED | 04-01, 04-02, 04-03, 04-04 |
| Cross-family page/API access is denied | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |
| No global pick/standing/message data appears inside a family context | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |

### REQ Coverage

| Requirement | Coverage | Plan(s) | Verification Target |
|-------------|----------|---------|---------------------|
| AUTHZ-02: Every family/pool write path checks authenticated membership server-side | COVERED | 04-02, 04-04, 04-06 | Tenant pick and message-board write tests |
| AUTHZ-04: Outsiders cannot view or infer private family data | COVERED | 04-01, 04-03, 04-04, 04-06 | Cross-family page and object-ID negative tests |
| AUTHZ-05: Client-provided tenant/user/game fields validated against server context | COVERED | 04-02, 04-06 | Pick POST tampering tests |
| POOL-03: Scores use global NFL facts with pool-scoped overlays | COVERED | 04-03, 04-06 | Scores overlay isolation tests |
| POOL-04: Rules/settings visible in appropriate context | COVERED | 04-03, 04-06 | Tenant rules display tests |
| COMM-02: Family members see profile stats only in allowed family context | COVERED | 04-04, 04-06 | Tenant profile/player negative tests |
| SEC-03: Cross-family isolation has automated negative tests | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 | Final two-family regression suite |
| SEC-04: Cache keys and precomputed data are family/pool scoped | COVERED | 04-01, 04-03, 04-06 | Scoped query and validation checks |

### RESEARCH Coverage

| Research Finding | Coverage | Plan(s) |
|------------------|----------|---------|
| Use existing Django function views and `family_member_required` | COVERED | 04-01, 04-02, 04-03, 04-04 |
| Keep NFL games/weeks/teams global | COVERED | 04-01, 04-02, 04-03 |
| Scope private overlays by `pool` and community rows by `family` | COVERED | 04-01, 04-02, 04-03, 04-04 |
| Redirect signed-in legacy private routes before rendering global data | COVERED | 04-01, 04-02, 04-03, 04-04 |
| Derive pick write fields server-side | COVERED | 04-02 |
| Use scoped object lookup for message-board and profile IDs | COVERED | 04-04 |
| No package installs are needed | COVERED | all plans |
| Keep UI edits focused during Bootstrap-to-Tailwind migration | COVERED | all template plans |

### CONTEXT Decision Coverage

| Decision | Coverage | Plan(s) |
|----------|----------|---------|
| D-01 tenant URLs | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |
| D-02 legacy signed-in redirects | COVERED | 04-01, 04-02, 04-03, 04-04 |
| D-03 no private global signed-in legacy rendering | COVERED | 04-01, 04-02, 04-03, 04-04 |
| D-04 auth and membership required for private surfaces | COVERED | 04-01, 04-02, 04-03, 04-04 |
| D-05 global NFL reference data | COVERED | 04-01, 04-02, 04-03 |
| D-06 pool-scoped pick overlays | COVERED | 04-02, 04-03 |
| D-07 server-derived pick fields | COVERED | 04-02 |
| D-08 scores do not leak other pools | COVERED | 04-03, 04-05, 04-06 |
| D-09 tenant dashboard scoped data | COVERED | 04-01 |
| D-10 remove/rewrite global dashboard widgets | COVERED | 04-01 |
| D-11 standings and weekly winners current-pool scoped | COVERED | 04-03 |
| D-12 scoped cache/precomputed data | COVERED | 04-01, 04-03, 04-05, 04-06 |
| D-13 family-private players/profiles/posts/comments/votes | COVERED | 04-04 |
| D-14 active family membership for profile/player viewing | COVERED | 04-04 |
| D-15 profile/stat views scoped to current family/pool | COVERED | 04-04 |
| D-16 message-board AJAX family/pool scoped | COVERED | 04-04 |
| D-17 cross-family negative tests | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |
| D-18 tenant-aware rules | COVERED | 04-03 |
| D-19 no rules/settings editing | COVERED | 04-01, 04-03 |
| D-20 static fallback rules display allowed | COVERED | 04-03 |
| D-21 tenant-preserving links | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |
| D-22 tenant-local empty states | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |
| D-23 non-leaking denial behavior | COVERED | 04-01, 04-03, 04-04, 04-05, 04-06 |
| D-24 mobile/header context remains visible | COVERED | 04-01, 04-02, 04-03, 04-04, 04-05, 04-06 |

## Out-of-Scope Guardrails

| Item | Status |
|------|--------|
| Family settings/rules editing forms | NOT PLANNED |
| Invite management, revocation/regeneration UI, role/member management | NOT PLANNED |
| Cron/scoring job production hardening | NOT PLANNED |
| Multi-active-pool UI | NOT PLANNED |

## Final Verification Checklist

- [ ] `cd pickem && ../venv/bin/python manage.py check --settings=pickem.test_settings`
- [ ] `cd pickem && ../venv/bin/python manage.py makemigrations --check --dry-run --settings=pickem.test_settings`
- [ ] `cd pickem && ../venv/bin/python manage.py test pickem_homepage pickem_api --settings=pickem.test_settings --verbosity=2`
- [ ] `cd pickem && ../venv/bin/python manage.py test --settings=pickem.test_settings --verbosity=2`
- [ ] `curl -s --max-time 5 http://localhost:8000 | head -40`

## Completion Evidence To Fill During Execution

| Evidence | Status | Reference |
|----------|--------|-----------|
| Dashboard/home summary | PENDING | `04-01-SUMMARY.md` |
| Picks summary | PENDING | `04-02-SUMMARY.md` |
| Scores/standings/rules summary | PENDING | `04-03-SUMMARY.md` |
| Profiles/message-board summary | PENDING | `04-04-SUMMARY.md` |
| Link cleanup summary | PENDING | `04-05-SUMMARY.md` |
| Final verification summary | PENDING | `04-06-SUMMARY.md` |
