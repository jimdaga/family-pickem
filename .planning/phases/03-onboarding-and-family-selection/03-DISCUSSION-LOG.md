# Phase 3: Onboarding And Family Selection - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-29
**Phase:** 3-Onboarding And Family Selection
**Areas discussed:** post-login routing, create-family flow, join-family flow, invite minimum, family switcher, empty states, URL shape

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| All areas | Cover create-family, join-invite, routing/switcher, and empty states so planning has no gaps. | ✓ |
| Core flow only | Focus on zero/one/multiple-family routing plus create/join decisions; leave polish details to planner discretion. | |
| Switcher focus | Spend most discussion on active family/pool context, URLs, and header switcher behavior. | |

**User's choice:** All areas.
**Notes:** Text-mode fallback was used because the interactive question tool was unavailable.

---

## Post-login Routing

| Option | Description | Selected |
|--------|-------------|----------|
| Route by membership count | 0 families goes to onboarding, 1 family goes straight to that family's default pool dashboard, multiple families goes to a family picker. | ✓ |
| Always show family picker | Every signed-in user sees a selection screen first, even with one family. | |
| Always show onboarding hub | A single hub page handles create, join, and select for everyone. | |

**User's choice:** Route by membership count.
**Notes:** Planner should preserve anonymous public landing behavior while routing signed-in users into the appropriate onboarding/tenant context.

---

## Create-family Flow

| Option | Description | Selected |
|--------|-------------|----------|
| Create family plus one default pool | Ask for family name, create a default current-season NFL pool automatically, and make creator owner. | ✓ |
| Create family only | User creates the family first, then a separate pool setup screen follows. | |
| Configure pool details immediately | Family name plus pool name/season/settings in one setup form. | |

**User's choice:** Create family plus one default pool.
**Notes:** Keep the flow short and use existing default/current-season conventions where possible.

---

## Join-family Flow

| Option | Description | Selected |
|--------|-------------|----------|
| Invite code/link entry | Signed-in user enters an invite code or opens an invite link, then joins as the invite's role/member and lands in that family's default pool. | ✓ |
| Code entry only | No link handling yet; users paste a code into onboarding. | |
| Admin-added members only | Defer self-serve invite acceptance until Phase 5 admin tools. | |

**User's choice:** Invite code/link entry.
**Notes:** Acceptance must be server-validated and should work for both pasted codes and clicked links.

---

## Invite Minimum

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal owner-created invite | Owner can generate one active member invite link/code from onboarding/family home; revoke/regenerate waits for Phase 5. | ✓ |
| Seed-only/manual invite codes | Phase 3 can accept existing invite records, but UI for creating invites waits for Phase 5. | |
| Full invite management now | Create, revoke, regenerate, expiry, max uses, and list invites in Phase 3. | |

**User's choice:** Minimal owner-created invite.
**Notes:** Full invite administration is deferred to Phase 5.

---

## Family Switcher

| Option | Description | Selected |
|--------|-------------|----------|
| Header switcher plus explicit URLs | Show current family in the header, let multi-family users switch there, and use tenant URLs for the new post-login context. | ✓ |
| Family picker page only | Users switch via a dedicated page; header only displays current family. | |
| Session-only active family | URLs stay mostly global for now and active family is stored in session. | |

**User's choice:** Header switcher plus explicit URLs.
**Notes:** Switcher should show active family/pool context and use active memberships only.

---

## Empty States

| Option | Description | Selected |
|--------|-------------|----------|
| Focused onboarding screen | Clear create/join actions, short friendly copy, no global standings/picks content. | ✓ |
| Homepage with onboarding banner | Keep showing the current home page but add a prominent create/join prompt. | |
| Auto-create legacy membership if possible | Try to place users into the legacy family rather than showing onboarding. | |

**User's choice:** Focused onboarding screen.
**Notes:** Signed-in no-family users should not see global league data.

---

## URL Shape

| Option | Description | Selected |
|--------|-------------|----------|
| Readable slugs | `/families/<family_slug>/pools/<pool_slug>/...`; clear and debuggable. | ✓ |
| Short slugs | `/f/<family_slug>/p/<pool_slug>/...`; more compact, less explicit. | |
| Family-only for now | `/families/<family_slug>/...`; default pool is implied until Phase 4. | |

**User's choice:** Readable slugs.
**Notes:** URLs should make current tenant context unambiguous.

---

## Final Readiness

| Option | Description | Selected |
|--------|-------------|----------|
| Ready for context | Write the Phase 3 context and discussion log now. | ✓ |
| Ask about admin boundaries | Clarify what owner/admin/member can do in Phase 3 versus Phase 5. | |
| Ask about visual polish | Clarify copy/layout/mobile expectations for onboarding and switcher. | |

**User's choice:** Ready for context.
**Notes:** Planner may decide exact polish and admin boundary details within the locked constraints.

## the agent's Discretion

- Exact page/template/form/helper names.
- Exact copy and layout, within the focused onboarding and header-switcher decisions.
- Exact implementation mechanism for post-login routing.
- Exact slug-collision handling, provided it is deterministic and tested.

## Deferred Ideas

- Full invite management belongs to Phase 5.
- Full tenant-scoped gameplay page migration belongs to Phase 4.
- Multi-active-pool UI is not required in Phase 3.
