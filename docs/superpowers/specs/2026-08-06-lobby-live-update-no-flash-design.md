# Lobby Live-Update: Stop the Flash — Design

**Date:** 2026-08-06
**Status:** Approved (brainstorming) — implement directly (small single-file JS change)
**Feature:** #159 live-update lobby (`family_pool_home.html`), not the simulation harness.
**Found by:** the live-weekend simulation harness demo (watching real SSE updates).

## Problem

On the lobby, the **Week Points** panel updates live via SSE. On every standings
event (debounced 1.5s) the handler does a **full `innerHTML` replace of the whole
tile grid**:

```js
current.innerHTML = fresh.innerHTML;   // family_pool_home.html ~line 702
```

This tears down and recreates **every** tile's DOM node, even tiles whose data
did not change — the browser repaints the entire panel, which reads as a flash.
During scoring this fires constantly. User feedback: "the other cards updating
almost gave me a seizure." (The row *reorder* itself is fine to animate subtly;
it's the wholesale redraw of unchanged tiles that's the problem.)

A secondary path: the pager's `render()` calls a global `ScrollTrigger.refresh()`
(~line 802) which, in pools large enough to paginate (>12 members), can re-fire
the GSAP `from()` reveal on other lobby sections. In small pools the pager's
one-page early-return means `refresh()` isn't called, so the primary cause there
is purely the `innerHTML` teardown.

## Fix

Two parts, both in `family_pool_home.html` (client-side JS only):

### 1. In-place keyed reconcile (removes the flash)

Replace the wholesale `innerHTML` swap with a reconcile that **reuses existing
tile nodes**, keyed by `data-user-id`:

- Still fetch the server-rendered rows as the source of truth (correct order,
  ranks, new/removed members).
- For an existing member: patch the node's content **only if** its rendered HTML
  actually changed (`node.innerHTML !== fresh.innerHTML`); update its
  `data-week-points-value`. Unchanged tiles are never touched → no repaint.
- Reorder by **moving** existing nodes into server order (`appendChild` moves,
  it doesn't recreate) — so a rank change relocates a tile without a teardown.
- Add only genuinely new member nodes; remove only departed ones. These count as
  a **structural** change.
- Animate moved tiles with a subtle **FLIP** slide (~220ms): record positions
  before the moves, then transition each moved node from its old offset to 0.
  Respect `prefers-reduced-motion` (snap instantly). Skip nodes that are hidden
  (0-width) so paginated-away rows don't animate.

### 2. Gate the pager's `ScrollTrigger.refresh()` (defensive, for >12-member pools)

Thread a `skipScrollRefresh` flag through the pager's `refresh()`/`render()`.
The live-update path calls the pager with `skipScrollRefresh = !structural`: a
pure value/reorder update leaves the visible-row count (and thus page height)
unchanged, so no `ScrollTrigger.refresh()` fires and the other lobby sections
stay perfectly still. A structural change (member added/removed, which can shift
height) still refreshes. **Manual page-nav (prev/next) keeps its refresh**, since
that genuinely changes which/how-many rows show.

## Non-goals

- No change to the SSE transport, the server-rendered row template, or the
  server publish path.
- Keep the existing instant value-patch (`applyStandingsEvent`) — it gives
  immediate feedback before the debounced reconcile; the reconcile then just
  confirms order against server truth without flashing.
- The initial page-load reveal animation is unchanged (it should still run once).

## Verification

There is **no JS test runner** in this repo, so:

1. The existing Django "live-update DOM contract" test (`pickem_homepage`
   tests) must stay green — it asserts the `data-week-points-row` /
   `data-user-id` / `data-week-points-value` / `data-user-week-points`
   attributes the reconcile depends on still render.
2. **Live verification on the running `:8055` demo**: run a weekend simulation
   and confirm (a) unchanged tiles no longer flash, (b) a rank change slides
   its tile subtly, (c) the other lobby cards do not animate on updates.

## Branch

Own branch off the lobby base (`5e73c24`, tip of
`fix/lobby-scrolltrigger-pagination-refresh`) — kept separate from the
`feature/live-weekend-simulation` harness branch.
