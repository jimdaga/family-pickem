# 🏈 Family Pickem — Modern Redesign Specification (Sporty + Dark Mode)

**Clean & Sporty • Tailwind-friendly • Dark-Mode-First**

## Overview

This is a ready-to-implement Tailwind redesign spec for Family Pickem that includes:

- Overall design direction
- Color system
- Typography
- Layout rules
- Component specifications
- Tailwind-ready structure
- References to the mockup you already have

No extra images, just practical implementation specs.

---

## 1. Product Tone & Visual Goals

**Target aesthetic:** Bold, clean, NFL-adjacent but non-infringing, high-contrast UI with modern spacing and typography.

**Key attributes:**
- Dark mode primary (light mode optional)
- Sporty, energetic accent colors
- Heavy emphasis on clarity and readability
- Card-based layout
- Good hierarchy, strong spacing
- Tailwind-friendly, clean utility classes

The companion mockup visually represents these foundations.

---

## 2. 🎨 Color System

### Dark Mode (Primary Experience)

| Element | Color | Description |
|---------|-------|-------------|
| Background | `#0B0E13` | Deep navy-charcoal |
| Surface | `#121821` | Dark elevated surface |
| Surface Hover | `#1A212C` | Hover state |
| Border/Subtle | `#1F2937` | Slate |
| Primary Accent | `#FF6B1A` | Electric orange |
| Secondary | `#9FE870` | Sporty lime green |
| Text Primary | `#FFFFFF` | White |
| Text Secondary | `#A9B4C4` | Light gray |
| Muted | `#6B7280` | Muted gray |
| Card Shadow | `rgba(0, 0, 0, 0.45)` | Shadow |

### Light Mode

| Element | Color | Description |
|---------|-------|-------------|
| Background | `#F8FAFC` | Light gray |
| Surface | `#FFFFFF` | White |
| Border/Subtle | `#E2E8F0` | Light border |
| Primary Accent | `#FF6B1A` | Electric orange |
| Secondary | `#3CA455` | Green |
| Text Primary | `#0F172A` | Dark slate |
| Text Secondary | `#475569` | Gray |

---

## 3. 🔤 Typography System

Use **Inter** or **Urbanist** (Google Fonts), both extremely modern and sports-friendly.

### Headings
- **Weight:** 700–900
- Tight leading
- Use uppercase for section labels

### Body
- **Weight:** 400–500
- Increased line-height (`leading-relaxed`)

### Monospace / Stats
- Use for small stat pills or abbreviated team initials
- Use `font-mono` Tailwind class

---

## 4. 🌐 Layout & Structure

### Global Layout

- **Max width:** `max-w-7xl mx-auto`

### Grid

- Page sections use `grid grid-cols-1 lg:grid-cols-12 gap-8`
- Dashboard uses `lg:col-span-8`, sidebar `lg:col-span-4`

### Cards

- Use: `rounded-2xl p-6 bg-surface shadow-xl border border-surface-subtle`
- Spacing heavy: `space-y-4` inside cards

### Transitions

- `transition-all duration-200 ease-out`
- Hover glow for accents: `hover:shadow-[0_0_20px_rgba(255,107,26,0.4)]`

---

## 5. 🧭 Navigation Bar Specification

### Dark Mode Navbar

```html
<div class="w-full bg-[#0B0E13]/80 backdrop-blur-lg border-b border-surface-subtle">
  <!-- Navbar content -->
</div>
```

### Structure

- **Left:** Logo + Title
- **Center:** Navigation
- **Right:** User menu / CTA

### Navigation Items

```css
px-4 py-2 rounded-xl text-secondary hover:text-white hover:bg-surface-hover
```

### Primary CTA

```css
px-4 py-2 bg-primary text-white rounded-xl font-semibold hover:bg-primary/80
```

---

## 6. 🏟 Homepage Hero Section

### Layout

**2-column layout:**
- **Left:** Big headline text
- **Right:** Feature card or weekly match preview

### Hero Example

```html
<h1 class="text-4xl lg:text-6xl font-extrabold text-white">
  Pick. Compete. Win.
</h1>

<p class="text-xl text-text-secondary max-w-xl mt-4">
  The cleanest way to run a family or friends NFL pick'em league — no accounts to manage,
  no spam, just weekly fun.
</p>

<button class="mt-8 px-6 py-3 bg-primary rounded-xl font-semibold">
  Join Your League
</button>
```

### Background

- Use an abstract, geometric football shape, not NFL-branded
- Low opacity lines, gradients, or blurred stripes

---

## 7. 🏈 Weekly Match Picks — Component Specification

### Match Card

```html
<div class="bg-surface rounded-2xl p-5 border border-surface-subtle shadow-lg hover:bg-surface-hover transition-all space-y-4">
  <!-- Match card content -->
</div>
```

### Team Row

```html
<div class="flex items-center justify-between">
  <div class="flex items-center gap-3">
    <div class="w-10 h-10 rounded-xl bg-surface-hover flex items-center justify-center font-bold">
      BUF
    </div>
    <span class="text-white font-semibold text-lg">Buffalo</span>
  </div>

  <button class="px-4 py-2 bg-primary rounded-lg text-white font-semibold">
    Pick
  </button>
</div>
```

### Kickoff

```html
<p class="text-muted text-sm mt-2">Sunday • 4:25 PM</p>
```

---

## 8. 🏆 Leaderboard Component Specification

### Leaderboard Card

```html
<div class="bg-surface rounded-2xl p-6 border border-surface-subtle space-y-4">
  <!-- Leaderboard content -->
</div>
```

### Row Style

```html
<div class="flex items-center justify-between">
  <div class="flex items-center gap-3">
    <div class="w-10 h-10 rounded-full bg-surface-hover"></div>
    <span class="text-white font-medium">Player Name</span>
  </div>

  <div class="flex items-center gap-2">
    <span class="text-secondary font-semibold">82%</span>
    <div class="w-24 h-2 bg-surface-hover rounded-full">
      <div class="h-full bg-primary rounded-full" style="width: 82%"></div>
    </div>
  </div>
</div>
```

---

## 9. 👤 User Dashboard Card

### User Summary

```html
<div class="flex items-center gap-4">
  <div class="w-14 h-14 rounded-full bg-surface-hover"></div>
  <div>
    <p class="text-white font-semibold text-lg">Hi, Jim!</p>
    <p class="text-text-secondary text-sm">Current record: 9–4</p>
  </div>
</div>
```

### Accuracy Chart

Recommend using a small lightweight chart:

- **ApexCharts** or **Chart.js**
- Tailwind-compatible
- Rounded stroke caps
- Glow highlight on hover

---

## 10. 💬 Message Board / Threaded Comments

### Comment Box

```html
<div class="bg-surface rounded-2xl p-4 border border-surface-subtle">
  <p class="text-white font-medium">Username</p>
  <p class="text-text-secondary mt-2">Comment content...</p>
</div>
```

### Thread Line

Use left-side vertical line:

```css
border-l-2 border-surface-hover pl-4
```

### Optional

- Reactions row using icons
- Highlight new comments with subtle glow: `animate-pulse bg-primary/10`

---

## 11. 📱 Mobile Layout Rules

- Collapse navbar into hamburger menu
- Cards become full-width with `space-y-4`
- Match pick cards stack teams vertically
- Leaderboard truncates bars and uses badges instead
- User dashboard collapses into stat blocks
- Use `sticky bottom-0` for weekly pick submission button

---

## 12. 🧩 Implementation Recommendations (Django + Tailwind)

Use **django-tailwind** or **DaisyUI** for theming.

### DaisyUI recommended for:

- Dark/light theming
- Buttons
- Cards
- Component shortcuts

### File Structure

```
templates/
  base.html
  home.html
  league/
    weekly.html
    leaderboard.html
  user/
    dashboard.html
static/
  css/
    tailwind.css
```

### Tailwind Config

- Enable `darkMode: 'class'`
- Add custom colors (primary, surface, etc.)
- Add `fontFamily: { sans: ['Inter', ...] }`

### Dark Mode Toggle

Use simple JS toggle:

```javascript
document.documentElement.classList.toggle('dark')
```

---

## 13. 📌 Prioritized Implementation Roadmap

This is the fastest path to a modern look:

### Week 1 – Core Modernization

- Add Tailwind
- Convert navbar
- Update color tokens
- Apply new spacing + typography globally
- Redesign card components

### Week 2 – Feature Screens

- Redesign Weekly Picks
- Redesign Leaderboard
- Redesign Dashboard

### Week 3 – Polish

- Mobile-first improvements
- Light mode
- Animations + microinteractions