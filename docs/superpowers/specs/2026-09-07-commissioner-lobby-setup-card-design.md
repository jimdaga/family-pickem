# Commissioner getting-started card on the lobby

**Date:** 2026-09-07

## Problem

People sign up for a pool and their commissioner cannot find the form to invite
anyone else. The lobby does have a "Manage Invites" button, but it sits at the
very bottom of a long page (`family_pool_home.html:481`, in the OWNER ACTIONS
row) — below the games grid, standings, message board and ESPN news. In
practice it is not found.

## Goal

A commissioner-only card near the top of the lobby that points at the handful of
things needed to get a pool going, shown only while the season has not started.

## Visibility

Both conditions required:

1. **Commissioner:** `membership.role in ('owner', 'admin')` — the same gate the
   existing "Manage Invites" button uses. No new permission concept. This also
   covers the superuser god-mode path, which enters with a synthetic owner
   membership.
2. **Before the season's first kickoff:** `now < season_kickoff`, where
   `season_kickoff` is the earliest `GamesAndScores.startTimestamp` for the
   pool's season and competition.

Deliberately **not** the existing `season_has_started` flag in the same view:
that means "a game has been scored", which flips hours after kickoff. First
kickoff is the requested boundary.

When the season has no games loaded at all, `season_kickoff` is `None` and the
card **shows** — that is the deep pre-season, exactly when a commissioner is
setting up.

The view exposes one boolean, `show_commissioner_setup`, so the template holds
no logic beyond a single `{% if %}`.

## Placement

Directly below the four action tiles (`lobby-action-grid`) and above the
publications loop — `family_pool_home.html:154`, between the closing `</div>` of
the action grid and `{% if publications %}`.

## Look

Reuses the existing `.commissioner-message-card` / `.commissioner-message-card__inner`
styles: the same construction as the AI recap card (animated conic-gradient
border, soft inner gradient, subtle texture overlay) but in the site's navy →
sky → teal rather than the recap's purple/magenta. Those styles already carry
light and dark variants and a `prefers-reduced-motion` opt-out, so no new CSS is
needed for the frame.

Distinguished from an actual commissioner note by its header: a flag icon in
place of the author avatar, a "Getting started" badge (reusing
`.commissioner-message-badge`), and a subtitle stating that the card disappears
once the season kicks off, so nobody wonders where it went.

Carries `data-testid="commissioner-setup"` for tests, and `lobby-section` so it
joins the existing GSAP scroll-reveal treatment.

## Content

A one-line lead, then three links as tappable rows:

| Label | Route | Why it is here |
| --- | --- | --- |
| Invite other players | `family_pool_admin_invites` | The reported problem |
| Pool settings | `family_pool_admin_settings` | Scoring, pick lock mode, missed-pick policy — set before week 1 |
| Post a lobby note | `family_pool_admin_publications` | The welcome message every member sees on their lobby |

## Tests

In `pickem_homepage/tests.py`, alongside the existing lobby tests:

- An owner before kickoff sees the card.
- A regular member before kickoff does not.
- An owner after the first kickoff does not.
- An owner sees it when the season has no games at all.
- The card links to all three admin routes.

## Build note

`static/css/input.css` is the source and `static/css/tailwind.css` is committed
and served. If the markup introduces a utility class not already compiled, run
`npm run build:prod` and commit the rebuilt `tailwind.css`. Never append a
`?v=...` cache-buster to a `{% static %}` URL.
