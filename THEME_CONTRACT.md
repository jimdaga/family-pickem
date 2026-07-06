# Family Pick'em — Theme Contract

## What Must Survive (Non-Negotiable Identity)

### Brand & Color
- **Primary accent color**: Dual-mode via CSS custom property.
  - Light mode: `#0B3D91` (NFL navy)
  - Dark mode: `#3B82F6` (bright blue — legible against the near-black dark backgrounds)
  - Implemented as `rgb(var(--color-primary) / <alpha-value>)` in Tailwind config so opacity variants (`bg-primary/20`, `hover:bg-primary/80`) work automatically in both modes.
  - Replaces the previous orange `#FF6B1A` everywhere — buttons, active nav states, pick selection highlights, progress bars, rank indicators.
  - Hardcoded `#FF6B1A` and `orange-600` references in `input.css` component classes (`btn-gradient`, `rule-icon-container`) and inline template styles (hero text-stroke) are replaced in Tasks 1 and 3.
- **Logo**: The `logo.png` wordmark appears in the nav. Its presentation may be adjusted (size, position) but it must remain the primary nav identifier.
- **Dark mode**: The dark theme (`bg-dark: #0B0E13`, `surface: #121821`) is a first-class experience, not an afterthought. All changes must look correct in both modes.
- **Green for correct picks**: `#3CA455` / `secondary-light` is used exclusively for correct-pick states and must not change or be repurposed.
- **Yellow/gold for rankings**: `text-yellow-500` for #1 rank and trophy icons. This semantic color coding (gold=1st, silver=2nd, bronze=3rd) must be preserved across the leaderboard and bottom bar.

### Typography
- **Inter** is the body font. It stays.
- **Urbanist** is the display font — currently used for page hero titles. Its usage will shrink but it must remain available.
- **Uppercase + tracking** on small metadata labels (rank, "pts", "Active Players", etc.) is intentional information density. Keep it for data labels; remove it from navigation and section titles.

### Functional Layout
- **Fixed top nav** (h-16) with logo left, center nav icons, right user/family context — this three-column layout must be preserved.
- **Fixed bottom status bar** (authenticated users only): shows user avatar, week number, rank, and Submit Picks CTA. This is a signature UX element. Keep it; only restyle it.
- **Bottom bar padding** (`pb-24` on `<main>`) must remain so content is not hidden behind the bottom bar.
- **Family context switcher** in the nav — required. Shows current family + pool name, allows switching.
- **Dropdown menus** for Scores (week selector), User profile, and Family switcher — must remain functional and accessible.
- **Mobile hamburger menu** with full mobile navigation — required.
- **AJAX message board** — posts, comments, votes all loaded/submitted via fetch. No page behavior changes, only visual.
- **Dark mode toggle** via `ThemeManager` JS — must not be broken.
- **Deploy marker** (`data-deploy-marker` attribute) — keep the attribute, hide it visually if needed.

### Page Structure
- Each content page has its own hero/header section that identifies the current page with an icon and title. This functional wayfinding must be preserved, even if the visual treatment changes.
- `section-container` as the primary card wrapper used across all pages.
- The home page section order (today's games → week points → week status → quick actions → leaderboard + league stats → message board → season champion) must not change.

---

## What We Are Adopting (Facebook-Modern UX Polish)

### Density & Clarity
- **Card hierarchy**: Cards should feel clean and airy, not crowded. Reduce internal padding inconsistencies. Standardize `p-4` or `p-5` (not mixing `p-3`, `p-5`, `p-6` arbitrarily).
- **Shadow discipline**: Only two shadow levels — `shadow-sm` (resting) and `shadow-md` (hover). Remove `shadow-xl` from cards (currently overused).
- **Border radius**: Standardize to `rounded-xl` (12px) for cards, `rounded-lg` (8px) for inputs and small elements. Remove `rounded-2xl` (24px) — too bubbly for a utility app.
- **Spacing consistency**: Section containers currently mix `p-2 sm:p-4 lg:p-6`. Standardize to `p-4 sm:p-5` as baseline.

### Nav Treatment
- **Light mode nav**: Move from `bg-slate-800` to white (`bg-white`). In light mode, a dark nav feels like a broadcast TV bar, not a focused utility platform. This is the single biggest visual shift.
- All nav text and icon colors must update to work against white in light mode.
- Dark mode nav stays dark (`dark:bg-surface/95`) — no change there.

### Page Headers
- Replace the heavy blue gradient hero banners (used on home, scores, standings, rules, picks, commissioners pages) with a compact, white-background page header: icon in a tinted square + title + subtitle. This removes visual noise and makes pages load feeling faster.
- The home page gets a personalized compact header (user avatar + welcome + week info) in place of the marketing-style gradient banner.

### Interaction States
- **Quick action cards** on the home page: remove per-card colored hover borders (currently red/blue/yellow/purple). Use a single `hover:border-primary` across all — consistent, calmer.
- **Hover animations**: Keep `hover:-translate-y-0.5` on leaderboard cards. Remove `hover:-translate-y-1` on quick action cards (too much lift for navigation elements).
- **Button styles**: `btn-gradient` (currently orange-to-orange-600 gradient) → flat `bg-primary` with `hover:bg-primary/90`. Gradients on buttons are a 2019 pattern.

### Bottom Status Bar
- Light mode: change from `bg-slate-800` to `bg-white` with a top border. All text updates from `text-white` to `text-text-dark dark:text-white`.
- Dark mode: stays as-is.

---

## What We Are NOT Doing

- No layout restructuring (no sidebar, no feed-only view, no column rebalancing)
- No font changes (Inter and Urbanist stay)
- No layout-driven recoloring beyond the navy/blue primary migration described above (the orange `#FF6B1A` → navy/blue accent swap is intentional and in-scope)
- No dark mode style changes beyond what's required to match light mode changes
- No functional changes to JS (message board, dropdowns, theme toggle, picks)
- No new pages, no new routes, no new components beyond what's needed
- No removing features (message board, stats, week picker, family switcher all stay)
- No changes to Django views or models
- No Bootstrap re-introduction

---

## Atomic Task List

| # | Task | Files | Risk |
|---|------|-------|------|
| 1 | **CSS foundations** — Standardize shadow levels, border radii, and spacing in `input.css`. Update `section-container`, `card-base`, `leaderboard-card`, `game-card`, `btn-gradient`, `page-header-clean`. No color or nav changes yet. | `input.css` | Low |
| 2 | **Nav → light mode** — Change nav and bottom bar from `bg-slate-800` to `bg-white`. Update all inline text colors from `text-white` to proper light/dark pairs. Update `nav-link-base` in `input.css`. Rebuild CSS. | `base.html`, `input.css` | Medium (many small edits) |
| 3 | **Page heroes** — Replace the blue gradient hero banner on all 6 pages (home, scores, standings, rules, picks, commissioners) with a compact white page header. Home gets the personalized variant; commissioners keeps the badge image. | 6 template files | Medium |
| 4 | **Quick actions cleanup** — On `home.html`, unify the per-card colored hover borders to `hover:border-primary`. Remove `hover:-translate-y-1`. Make interactions consistent. | `home.html` | Low |
| 5 | **Tailwind config + rebuild** — If Task 2 introduces any color gaps (e.g., new light-mode-specific hover states that need config tokens), add them here. Then do a full production CSS rebuild and verify all pages load correctly. | `tailwind.config.js`, CSS build | Low |
| 6 | **Cross-page audit** — Take screenshots of home, scores, standings, picks, rules. Verify dark mode still works. Check mobile menu. Verify bottom bar in both modes. | Browser inspection | Low |

---

## Validation Checklist (per task)

After each task, verify:
- [ ] Light mode looks correct on the changed element
- [ ] Dark mode is not broken on the changed element
- [ ] The orange primary color is still the dominant action/brand color
- [ ] No Bootstrap classes were re-introduced
- [ ] The bottom bar still shows avatar, week, rank, submit button
- [ ] Mobile menu still opens and closes
- [ ] No `text-white` on a white background (the most common light-mode bug)
