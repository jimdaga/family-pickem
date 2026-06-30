# Family Pickem Modern Frontend Redesign

## Summary

Family Pickem will move from a gradient-heavy, oversized-card interface to a compact sports dashboard inspired by ESPN's information hierarchy without copying its brand. The approved direction is **Modern ESPN Hybrid** with a **Broadcast Blue** accent and coordinated light and dark themes.

The homepage will be the reference implementation. Its shared shell, semantic tokens, modules, tables, status labels, and responsive behavior will then be applied across picks, scores, standings, profiles, rules, settings, and commissioner screens.

## Goals

- Make the interface feel clean, modern, deliberate, and recognizably sports-oriented.
- Remove visual patterns commonly associated with generic AI-generated interfaces.
- Improve information density and scan speed without making the app feel cramped.
- Give light and dark themes the same hierarchy and product identity.
- Reduce template duplication and page-specific visual overrides.
- Preserve existing application behavior and user workflows.

## Non-Goals

- Rebrand the league or replace the existing logo during this project.
- Copy ESPN's exact colors, typography, components, or layout.
- Change scoring rules, authentication, data sources, or league behavior.
- Introduce a JavaScript framework or a new frontend build system.
- Perform unrelated backend or dependency upgrades.

## Current-State Findings

The frontend currently spreads more than 7,000 lines across ten page templates. Several large templates also contain substantial inline JavaScript and inline style overrides.

The strongest sources of the current "AI-made" appearance are:

- Large blue-purple-red gradient hero banners on most screens.
- Outlined, all-caps display headings with heavy text stroke.
- Rounded cards nested inside other rounded cards.
- Gradients, glows, shadows, glass effects, and hover scaling used simultaneously.
- Decorative Font Awesome icons on nearly every heading and action.
- Low information density despite large page sections.
- Inconsistent visual rules implemented independently by each template.
- Page-level scripts and inline styles that override the shared Tailwind layer.

## Approved Visual Direction

### Product Character

The interface should feel like a private NFL league dashboard built by people who follow games closely. It should be practical on normal weekdays and especially useful during game windows.

The visual reference is a modern broadcast-sports product:

- Compact navigation and score information.
- Clear week, game, and standings hierarchy.
- Dense white or graphite data modules.
- Thin rules and borders instead of floating cards.
- One restrained accent color.
- Strong typography without decorative display treatments.

### Color System

The approved accent is **Broadcast Blue**, a medium athletic blue used sparingly.

Initial semantic palette targets:

| Token | Light | Dark | Purpose |
| --- | --- | --- | --- |
| `canvas` | `#EDF0F3` | `#171B20` | Page background |
| `surface` | `#FFFFFF` | `#252B32` | Primary modules |
| `surface-subtle` | `#F6F7F8` | `#20262C` | Secondary rows and controls |
| `nav` | `#141920` | `#0E1115` | Utility navigation |
| `text` | `#1B2028` | `#EDF1F5` | Primary text |
| `text-muted` | `#6D747D` | `#969FA9` | Secondary text |
| `border` | `#D7DCE1` | `#39414A` | Rules and module boundaries |
| `accent` | `#2563A6` | `#4F91D9` | Primary actions and active states |
| `accent-hover` | `#1F548D` | `#6FA9E8` | Hover and link emphasis |
| `positive` | `#2E7D57` | `#56B887` | Correct, live, and success states |
| `negative` | `#B84242` | `#E07171` | Incorrect and error states |
| `warning` | `#9B6B13` | `#D1A94D` | Deadlines and pending states |

Exact values may be adjusted during implementation to meet WCAG 2.2 contrast requirements. Color must never be the only signal for game, pick, validation, or selection state.

### Typography

- Use Inter as the single interface font, with system sans-serif fallback.
- Remove Urbanist and all text-stroke treatments.
- Use normal casing for names and navigation.
- Reserve uppercase for short metadata labels such as `FINAL`, `LIVE`, `WEEK`, and table headings.
- Use a compact type scale with clear weight differences instead of dramatic size changes.
- Use tabular numerals for scores, points, ranks, and records where supported.

### Shape and Depth

- Page modules use `0-6px` corner radii.
- Buttons and form controls use `2-4px` radii.
- Avatars and status dots may remain circular.
- Thin borders and background contrast define hierarchy.
- Shadows are limited to open menus, sticky overlays, and rare elevated states.
- Remove decorative gradients, glass effects, glows, blurred blobs, and routine hover translation or scaling.

### Icons and Motion

- Use icons only when they improve recognition or communicate state.
- Navigation may combine concise labels with selected icons where space requires it.
- Section headings generally use text alone.
- Motion is limited to menu transitions, loading feedback, disclosure, and live-state indicators.
- Respect `prefers-reduced-motion`.

## Shared Architecture

### Template Composition

`base.html` remains the application shell, but repeated visual structures move into Django includes under:

```text
pickem/pickem_homepage/templates/pickem/components/
```

Expected shared components:

- `primary_nav.html`
- `mobile_nav.html`
- `site_banner.html`
- `page_heading.html`
- `module.html`
- `module_header.html`
- `status_label.html`
- `score_row.html`
- `standings_table.html`
- `empty_state.html`
- `form_field.html`
- `button.html`

Includes should receive explicit context with `only` when practical. Page-specific business logic stays in views and template tags rather than moving into presentation components.

### CSS Structure

`tailwind.config.js` will define semantic colors, radius, spacing, and typography tokens. `static/css/input.css` will contain a small shared component layer for patterns that would otherwise repeat long utility strings.

The generated `tailwind.css` remains a build artifact and must be regenerated through `npm run build:prod`; it is not edited manually.

Existing classes such as `card-base`, `section-container`, `btn-gradient`, and glow-oriented status components will be replaced or retired as pages migrate.

### JavaScript Structure

Shared navigation, theme, banner, dropdown, and disclosure behavior should move out of inline template scripts into focused static JavaScript modules. Page-specific scripts remain separate by page.

The redesign must preserve:

- Pick selection, editing, locking, progress, and tiebreaker behavior.
- Live score refreshing and pick-result display.
- Message board posting, comments, voting, and deletion.
- Profile and commissioner form behavior.
- Theme persistence and authenticated theme synchronization.

## Homepage Reference Design

The homepage answers four questions in this order:

1. What week is it, and when do picks close?
2. Do I need to finish my picks?
3. What is happening in the NFL this week?
4. How am I doing in the league?

### Desktop Hierarchy

1. Compact utility and primary navigation.
2. Week heading with season context and pick deadline.
3. Full-width pick progress action for authenticated users.
4. Two-column dashboard:
   - Main: current and upcoming games.
   - Side: personal season summary and league activity.
5. Compact league standings table.
6. Secondary league content, including message-board activity and historical summaries.

### Mobile Hierarchy

The two-column dashboard becomes one ordered feed:

1. Week and deadline.
2. Pick progress action.
3. Current games.
4. Personal season summary.
5. League standings.
6. League activity and discussion.

The main action remains visible without a permanent bottom bar covering page content. A sticky action may be used only where it materially improves pick completion and has safe-area padding.

### Homepage States

- **Anonymous:** replace personal pick progress with a compact sign-in prompt; retain scores and public standings.
- **No games:** show a concise empty state without a large illustration or icon.
- **No picks submitted:** show `0 of N complete` and a direct start action.
- **All picks submitted:** use a positive status label and offer review/edit when allowed.
- **Offseason or missing week data:** explain the state plainly and prioritize standings/history.
- **Live games:** display a text status and restrained live dot; no pulsing card or gradient.

## Page Rollout

### Shared Shell

- Replace icon-only desktop navigation with clear labels.
- Keep the current route set and permission-aware commissioner link.
- Simplify score-week selection and account menus.
- Replace the fixed bottom status bar with contextual page actions.
- Convert banners to compact semantic alerts integrated below navigation.

### Picks

- Present each game as a matchup sheet with one header and two selectable team rows.
- Use team colors as a narrow identifier, not a large gradient background.
- Make selected, locked, unavailable, and completed states explicit with text and icons.
- Keep progress and submission actions prominent.
- Maintain keyboard-accessible selection and form validation.

### Scores

- Use dense scoreboard modules with game status, teams, score, records, and optional detail rows.
- Hide secondary weather, betting, probability, and player-pick detail behind clear disclosure when space is constrained.
- Remove glow borders, repeated avatar scaling, gradient status bars, and page-level dark-mode DOM overrides.
- Preserve automatic refresh and game-detail behavior.

### Standings

- Lead with a responsive standings table rather than repeated player cards.
- Columns prioritize rank, player, weekly points, total points, and movement when available.
- Use gold, silver, and bronze as small rank markers only.
- Weekly winners become a compact list or table grouped by week.
- Preserve season selection and profile links.

### User Profiles

- Replace the gradient profile hero with a compact identity header.
- Group current-season and lifetime statistics into summary modules and tables.
- Keep charts as supporting analysis below primary statistics.
- Remove glass panels, multicolor achievement tiles, outlined headings, and decorative gradients.

### Rules

- Treat rules as a readable document with anchored sections.
- Use simple callouts for scoring exceptions and deadlines.
- Remove icon tiles and hover animation.

### Settings

- Use grouped form sections with consistent labels, help text, validation, and actions.
- Keep theme preference and profile controls easy to scan.
- Remove decorative metrics and presentation-only effects.

### Commissioner

- Use an admin-oriented layout with compact controls, tables, filters, and confirmation states.
- Prioritize clarity and destructive-action safety over visual decoration.
- Retain all permission checks and existing operations.

## Responsive Behavior

- Primary breakpoints follow the existing Tailwind configuration unless a component needs a documented exception.
- Tables retain column headers on desktop and become labeled rows or horizontally scrollable tables on narrow screens.
- Modules must not depend on hover for essential information.
- Touch targets should be at least 44 by 44 CSS pixels where practical.
- Content must reflow at 320 CSS pixels without horizontal page scrolling.
- Navigation, dropdowns, and disclosures must be keyboard operable.

## Accessibility

- Meet WCAG 2.2 AA contrast for text and meaningful UI boundaries.
- Maintain visible focus states in both themes.
- Use semantic headings, tables, buttons, links, form labels, and status text.
- Provide accessible names for icon-only controls.
- Do not use color alone for live/final, correct/incorrect, selected/unselected, or error/success states.
- Preserve logical DOM order when desktop columns collapse on mobile.
- Use `aria-live="polite"` for form validation summaries and user-triggered pick updates. Do not announce routine automatic score refreshes unless the visible game status changes.

## Data and Backend Boundaries

Existing models and public view behavior remain unchanged. Backend edits are allowed when they reduce template computation or provide a clearer presentation model.

Homepage context should expose explicit, template-ready structures for:

- Pick progress and action state.
- Current/upcoming game summaries.
- Personal rank and points.
- Compact standings rows.
- League activity.

Avoid adding repeated database queries inside template filters or nested loops. Query changes should be covered by view tests and query-count checks where regression risk is meaningful.

The uncommitted homepage and view changes present before this redesign must be reviewed and incorporated rather than overwritten.

## Testing and Validation

### Automated

- Django view tests for authenticated, anonymous, empty, offseason, live, and completed states.
- Template rendering tests for required headings, actions, table semantics, and theme hooks.
- Existing behavior tests for picks, scores, profiles, message board, and commissioner workflows.
- `python manage.py test` for the complete Django suite.
- `npm run build:prod` to verify Tailwind compilation.
- Static checks for unintended Bootstrap dependencies, inline visual styles, and obsolete component classes as each page migrates.

### Browser Validation

Use the running app at `http://localhost:8000` and validate:

- Light and dark themes.
- Mobile, tablet, and desktop widths.
- Anonymous and authenticated layouts.
- Keyboard navigation and visible focus.
- Empty and populated data states.
- Menu, disclosure, theme, message-board, and pick interactions.
- Console errors and failed network requests.

The browser-rendered result is the source of truth for visual acceptance because JavaScript modifies parts of the DOM.

## Acceptance Criteria

- The homepage matches the approved Modern ESPN Hybrid hierarchy in both themes.
- No primary page uses a gradient hero, outlined display heading, glass panel, glow, or decorative blurred background.
- Shared modules use semantic tokens and consistent borders, spacing, type, and radius.
- Broadcast Blue is the only primary brand accent; status colors remain semantic.
- Usernames and ordinary headings use normal casing.
- Core information appears above secondary community and historical content.
- Existing user workflows and URLs continue to function.
- Mobile layouts reflow without covered content or page-level horizontal scrolling.
- Both themes meet agreed accessibility checks.
- Page-specific inline visual overrides and duplicated shared scripts are substantially reduced.

## Delivery Strategy

Implementation proceeds in reviewable slices:

1. Foundation tokens, shell, shared components, and theme behavior.
2. Homepage reference implementation.
3. Picks.
4. Scores.
5. Standings.
6. Profiles and settings.
7. Rules and commissioner screens.
8. Legacy cleanup and full regression validation.

Each slice should leave the migrated pages working in both themes and should avoid partially restyling a page with conflicting old and new systems.
