# Family Pickem Style Guide

This guide documents the Tailwind CSS patterns used throughout the application, based on the picks page design. Use these patterns to maintain visual consistency across all pages.

---

## Table of Contents
1. [Color System](#color-system)
2. [Typography](#typography)
3. [Page Structure](#page-structure)
4. [Component Patterns](#component-patterns)
5. [Interactive States](#interactive-states)
6. [Icons & Badges](#icons--badges)
7. [Forms](#forms)
8. [Modals](#modals)
9. [Animations](#animations)
10. [Responsive Design](#responsive-design)

---

## Color System

### Design Tokens (tailwind.config.js)

```javascript
colors: {
  // Dark Mode (Primary)
  'bg-dark': '#0B0E13',        // Page background
  'surface': '#121821',         // Card backgrounds
  'surface-hover': '#1A212C',   // Hover states, secondary surfaces
  'border-subtle': '#1F2937',   // Borders
  'primary': '#FF6B1A',         // Primary orange accent
  'secondary': '#9FE870',       // Success green
  'text-primary': '#FFFFFF',    // Primary text
  'text-secondary': '#A9B4C4',  // Muted text
  'muted': '#6B7280',           // Disabled/subtle text

  // Light Mode
  'bg-light': '#F8FAFC',        // Page background
  'surface-light': '#FFFFFF',   // Card backgrounds
  'border-light': '#E2E8F0',    // Borders
  'secondary-light': '#3CA455', // Success green (light)
  'text-dark': '#0F172A',       // Primary text
  'text-secondary-light': '#475569', // Muted text
}
```

### Usage Patterns

```html
<!-- Text Colors -->
<span class="text-text-dark dark:text-white">Primary text</span>
<span class="text-text-secondary-light dark:text-text-secondary">Secondary text</span>
<span class="text-primary">Accent/link text</span>

<!-- Background Colors -->
<div class="bg-bg-light dark:bg-bg-dark">Page background</div>
<div class="bg-surface-light dark:bg-surface">Card background</div>
<div class="bg-surface-light dark:bg-surface-hover">Secondary surface</div>

<!-- Border Colors -->
<div class="border border-border-light dark:border-border-subtle">Bordered element</div>
```

### Semantic Color Patterns

| Purpose | Light Mode | Dark Mode |
|---------|-----------|-----------|
| Success | `bg-secondary-light/20 text-secondary-light` | `bg-secondary/20 text-secondary` |
| Error/Warning | `bg-red-500/10 text-red-600` | `bg-red-600/20 text-red-400` |
| Info | `bg-blue-500/10 text-blue-600` | `bg-blue-600/20 text-blue-400` |
| Special (Tiebreaker) | `bg-purple-500/10 text-purple-600` | `bg-purple-600/20 text-purple-400` |

---

## Typography

### Font Family
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Urbanist:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
```

### Heading Styles

```html
<!-- Page Title (Hero) -->
<h2 class="text-3xl lg:text-5xl font-black tracking-tight"
    style="font-family: 'Urbanist', sans-serif; text-transform: uppercase; letter-spacing: -0.02em; color: white; -webkit-text-stroke: 3px #FF6B1A; paint-order: stroke fill;">
    Page Title
</h2>

<!-- Section Title -->
<h3 class="section-title">
    <i class="fas fa-icon mr-2"></i>
    <span>Section Name</span>
</h3>
<!-- Note: .section-title = text-2xl font-bold text-text-dark dark:text-gray-100 flex items-center !mb-8 -->

<!-- Card Title -->
<h4 class="text-xl font-semibold text-text-dark dark:text-white">Card Title</h4>

<!-- Small Heading -->
<h6 class="text-lg font-semibold text-text-dark dark:text-white">Small Heading</h6>
```

### Text Sizes

| Size | Class | Usage |
|------|-------|-------|
| XS | `text-xs` | Badges, percentage labels |
| SM | `text-sm` | Secondary info, metadata |
| Base | `text-base` | Body text |
| LG | `text-lg` | Card titles, team names |
| XL | `text-xl` | Section subtitles |
| 2XL | `text-2xl` | Section headers |
| 4XL | `text-4xl` | Stats, large numbers |

---

## Page Structure

### Page Header (Hero Section)

**IMPORTANT:** The `<main>` tag in base.html has `pt-16` (64px) to clear the fixed navbar. Hero sections should use the standard padding below - they will automatically touch the navbar.

```html
<div class="relative text-center mb-6 px-4 py-8 lg:py-12 bg-gradient-to-br from-slate-100 via-blue-100 to-indigo-100 dark:from-blue-600/30 dark:via-purple-600/20 dark:to-red-600/30 border-b-2 border-blue-600 dark:border-blue-500/40 overflow-hidden shadow-xl">
    <!-- Subtle background pattern (optional) -->
    <div class="absolute inset-0 opacity-20 dark:opacity-5 bg-[url('data:image/svg+xml;base64,...')] pointer-events-none"></div>

    <div class="relative z-10">
        <!-- Icon -->
        <div class="flex items-center justify-center mb-3 lg:mb-4">
            <i class="fas fa-icon text-4xl lg:text-6xl text-primary"></i>
        </div>

        <!-- Title -->
        <h2 class="text-3xl lg:text-5xl font-black tracking-tight mb-2 lg:mb-3"
            style="font-family: 'Urbanist', sans-serif; text-transform: uppercase; letter-spacing: -0.02em; color: white; -webkit-text-stroke: 3px #FF6B1A; paint-order: stroke fill;">
            Page Title
        </h2>

        <!-- Subtitle -->
        <p class="text-base lg:text-xl text-gray-700 dark:text-text-secondary font-medium">
            Subtitle or context info
        </p>
    </div>
</div>
```

### Main Content Container

```html
<div class="max-w-7xl mx-auto px-4 py-6">
    <!-- Content sections here -->
</div>
```

### Section Container

```html
<div class="section-container mb-6">
    <!-- .section-container = bg-surface dark:bg-surface rounded-2xl p-6 shadow-xl border border-border-subtle -->

    <h3 class="section-title">
        <i class="fas fa-icon mr-2"></i>
        <span>Section Title</span>
        <!-- Optional badge -->
        <span class="ml-3 px-3 py-1 text-sm font-semibold bg-primary text-white rounded-full">
            Count
        </span>
    </h3>

    <!-- Section content -->
</div>
```

---

## Component Patterns

### Cards

#### Basic Card
```html
<div class="bg-surface-light dark:bg-surface rounded-2xl p-6 border border-border-light dark:border-border-subtle hover:border-primary/30 dark:hover:border-primary/30 transition-all duration-200 space-y-4">
    <!-- Card content -->
</div>
```

#### Game Card (with flex for sticky footer)
```html
<div class="game-card flex flex-col bg-surface-light dark:bg-surface rounded-2xl p-6 border border-border-light dark:border-border-subtle hover:border-primary/30 transition-all duration-200 space-y-4">
    <!-- Card header -->
    <div class="flex items-center justify-between flex-wrap gap-2">
        <!-- Date/time -->
        <div class="flex items-center gap-2 text-sm text-text-secondary-light dark:text-text-secondary">
            <i class="fas fa-calendar"></i>
            <span>Sun, Dec 07</span>
        </div>
        <!-- Status badge -->
        <div class="px-3 py-1 bg-secondary-light/20 dark:bg-secondary/20 text-secondary-light dark:text-secondary rounded-lg text-sm font-semibold flex items-center gap-1">
            <i class="fas fa-check-circle"></i>
            <span>Available</span>
        </div>
    </div>

    <!-- Main content -->
    <!-- ... -->

    <!-- ESPN-style Footer (sticks to bottom) -->
    <div class="mt-auto pt-3 border-t border-border-light dark:border-border-subtle">
        <div class="flex items-center justify-between">
            <div>
                <a href="#" class="inline-flex items-center gap-1.5 text-sm text-primary hover:text-primary/80 transition-colors font-medium">
                    <i class="fas fa-external-link-alt"></i>
                    <span>Preview</span>
                </a>
            </div>
            <div>
                <span class="text-sm font-semibold text-text-secondary-light dark:text-text-secondary">CBS</span>
            </div>
        </div>
    </div>
</div>
```

#### Info Card (for empty states, prep cards)
```html
<div class="bg-surface-light dark:bg-surface-hover rounded-xl p-6 border border-border-light dark:border-border-subtle">
    <i class="fas fa-icon text-4xl text-primary mb-3"></i>
    <h6 class="text-lg font-semibold text-text-dark dark:text-white mb-2">Title</h6>
    <p class="text-sm text-text-secondary-light dark:text-text-secondary">Description text</p>
</div>
```

### Team Selection Cards (ESPN-style)

```html
<div class="team-option relative group rounded-xl border-2 border-transparent hover:border-primary transition-all cursor-pointer overflow-hidden flex flex-col">
    <!-- Top Half - Team Color Background -->
    <div class="relative h-[100px] flex items-center justify-center py-2"
         style="background: linear-gradient(135deg, #ALTCOLOR40 0%, #COLOR 50%, #COLOR 100%);">
        <img src="logo.png" alt="Team logo" class="w-16 h-16 object-contain drop-shadow-lg relative z-10">

        <!-- Selection Indicator (appears on hover/select) -->
        <div class="team-selection-indicator absolute top-2 right-2 w-8 h-8 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center text-white opacity-0 group-hover:opacity-100 transition-opacity">
            <i class="fas fa-check"></i>
        </div>
    </div>

    <!-- Bottom Half - Text Content -->
    <div class="flex-1 flex flex-col items-center justify-center p-3 text-center bg-surface-light dark:bg-surface-hover">
        <div class="font-bold text-lg text-text-dark dark:text-white mb-1">Team Name</div>
        <div class="text-sm text-text-secondary-light dark:text-text-secondary space-y-1">
            <div>(8-4)</div>
            <div class="flex items-center justify-center gap-1 text-xs">
                <i class="fas fa-percentage"></i>
                <span>55% chance</span>
            </div>
        </div>
    </div>
</div>
```

### Buttons

#### Primary Button
```html
<button class="px-6 py-3 bg-primary hover:bg-primary/80 text-white rounded-xl font-semibold transition-all flex items-center gap-2">
    <i class="fas fa-icon"></i>
    <span>Button Text</span>
</button>
```

#### Secondary/Outline Button
```html
<button class="px-6 py-3 border-2 border-primary text-primary rounded-xl font-semibold hover:bg-primary hover:text-white transition-all flex items-center gap-2">
    <i class="fas fa-icon"></i>
    <span>Button Text</span>
</button>
```

#### Action Button (Edit, Save)
```html
<button class="w-full px-4 py-2 bg-blue-600/10 dark:bg-blue-600/20 text-blue-600 dark:text-blue-400 rounded-xl font-semibold hover:bg-blue-600/20 dark:hover:bg-blue-600/30 transition-all flex items-center justify-center gap-2">
    <i class="fas fa-edit"></i>
    <span>Edit Pick</span>
</button>
```

#### Cancel/Neutral Button
```html
<button class="w-full px-4 py-3 bg-gray-500/10 dark:bg-gray-600/20 text-gray-600 dark:text-gray-400 rounded-xl font-semibold hover:bg-gray-500/20 dark:hover:bg-gray-600/30 transition-all flex items-center justify-center gap-2">
    <i class="fas fa-times"></i>
    <span>Cancel</span>
</button>
```

### Progress Bar

```html
<div class="space-y-2">
    <div class="w-full bg-surface-light dark:bg-surface-hover rounded-full h-4 overflow-hidden border border-border-light dark:border-border-subtle">
        <div class="h-full bg-gradient-to-r from-primary to-orange-600 rounded-full transition-all duration-500 flex items-center justify-end pr-2"
             style="width: 71%">
            <span class="text-xs font-semibold text-white">71%</span>
        </div>
    </div>
    <div class="text-center text-sm font-semibold text-text-secondary-light dark:text-text-secondary">
        71% Complete - 4 remaining
    </div>
</div>
```

### Stats Display

```html
<div class="flex items-center justify-center gap-2 text-center">
    <div class="flex-1">
        <div class="text-4xl font-bold text-primary">10</div>
        <div class="text-sm text-text-secondary-light dark:text-text-secondary uppercase tracking-wide mt-1">Picks Submitted</div>
    </div>
    <div class="text-3xl text-text-secondary-light dark:text-text-secondary font-light">/</div>
    <div class="flex-1">
        <div class="text-4xl font-bold text-text-dark dark:text-white">14</div>
        <div class="text-sm text-text-secondary-light dark:text-text-secondary uppercase tracking-wide mt-1">Total Games</div>
    </div>
</div>
```

### Info Row (Spread, Weather, etc.)

```html
<div class="flex flex-wrap items-center gap-3 text-sm text-text-secondary-light dark:text-text-secondary">
    <!-- Spread -->
    <div class="flex items-center gap-1.5">
        <i class="fas fa-chart-line"></i>
        <span class="font-medium">Spread:</span>
        <span class="flex items-center gap-1 font-semibold text-text-dark dark:text-white">
            <img src="team-logo.png" class="w-4 h-4">
            -7.5
        </span>
    </div>

    <!-- Over/Under -->
    <div class="flex items-center gap-1.5">
        <i class="fas fa-calculator"></i>
        <span class="font-medium">O/U:</span>
        <span class="font-semibold text-text-dark dark:text-white">44.5</span>
    </div>

    <!-- Weather -->
    <div class="flex items-center gap-1.5">
        <i class="fas fa-sun text-yellow-500"></i>
        <span>72°F, Clear</span>
    </div>

    <!-- Indoor -->
    <div class="flex items-center gap-1.5">
        <i class="fas fa-home"></i>
        <span>Indoor</span>
    </div>
</div>
```

---

## Interactive States

### Selection State (Team Cards)

```css
/* In input.css */
.team-option.selected,
.team-option-edit.selected {
    @apply border-primary bg-primary/10 dark:bg-primary/20;
}

.team-option.selected .team-selection-indicator,
.team-option-edit.selected .selection-indicator {
    @apply opacity-100;
}
```

### Hover States

```html
<!-- Card hover -->
<div class="hover:border-primary/30 dark:hover:border-primary/30 transition-all duration-200">

<!-- Button hover -->
<button class="hover:bg-primary/80 transition-all">

<!-- Link hover -->
<a class="hover:text-primary/80 transition-colors">
```

### Disabled/Locked State

```html
<div class="opacity-50 pointer-events-none">
    <!-- Locked content -->
</div>
```

### Opacity for Non-Selected

```html
<!-- Show non-selected team at 40% opacity -->
<div class="{% if not selected %}opacity-40{% endif %}">
```

---

## Icons & Badges

### Status Badges

```html
<!-- Success/Available -->
<div class="px-3 py-1 bg-secondary-light/20 dark:bg-secondary/20 text-secondary-light dark:text-secondary rounded-lg text-sm font-semibold flex items-center gap-1">
    <i class="fas fa-check-circle"></i>
    <span>Available</span>
</div>

<!-- Locked/Error -->
<div class="px-3 py-1 bg-red-500/20 text-red-600 dark:text-red-400 rounded-lg text-sm font-semibold flex items-center gap-1">
    <i class="fas fa-lock"></i>
    <span>Locked</span>
</div>

<!-- Count Badge -->
<span class="ml-3 px-3 py-1 text-sm font-semibold bg-primary text-white rounded-full">
    4 remaining
</span>
```

### Weather Icons (Contextual)

```html
{% if 'Sun' in condition or 'Clear' in condition %}
    <i class="fas fa-sun text-yellow-500"></i>
{% elif 'Cloud' in condition %}
    <i class="fas fa-cloud"></i>
{% elif 'Rain' in condition %}
    <i class="fas fa-cloud-rain text-blue-500"></i>
{% elif 'Snow' in condition %}
    <i class="fas fa-snowflake text-blue-300"></i>
{% elif 'Storm' in condition %}
    <i class="fas fa-bolt text-purple-500"></i>
{% endif %}
```

### Alert/Message Boxes

```html
<!-- Info -->
<div class="flex items-center gap-2 px-4 py-3 bg-blue-500/10 dark:bg-blue-600/20 text-blue-600 dark:text-blue-400 rounded-xl border border-blue-500/30 dark:border-blue-500/40">
    <i class="fas fa-info-circle"></i>
    <span>Information message</span>
</div>

<!-- Success -->
<div class="flex items-center gap-2 px-4 py-3 bg-secondary-light/20 dark:bg-secondary/20 text-secondary-light dark:text-secondary rounded-xl border border-secondary-light/30 dark:border-secondary/40">
    <i class="fas fa-check-circle"></i>
    <span>Success message</span>
</div>

<!-- Error/Warning -->
<div class="flex items-center gap-2 px-4 py-3 bg-red-500/10 dark:bg-red-600/20 text-red-600 dark:text-red-400 rounded-xl border border-red-500/30 dark:border-red-500/40">
    <i class="fas fa-exclamation-triangle"></i>
    <span>Error or warning message</span>
</div>

<!-- Special (Purple - Tiebreaker) -->
<div class="bg-purple-500/10 dark:bg-purple-600/20 rounded-xl p-4 border border-purple-500/30 dark:border-purple-500/40">
    <div class="flex items-center gap-2 text-purple-600 dark:text-purple-400 font-semibold mb-3">
        <i class="fas fa-balance-scale"></i>
        <span>Tiebreakers Required</span>
    </div>
</div>
```

---

## Forms

### Text Input

```html
<div class="space-y-1">
    <label class="block text-sm font-medium text-text-dark dark:text-white">
        Field Label
    </label>
    <input type="text"
           placeholder="Placeholder text"
           class="w-full px-3 py-2 bg-bg-light dark:bg-surface border border-border-light dark:border-border-subtle rounded-lg text-text-dark dark:text-white placeholder-text-secondary-light dark:placeholder-text-secondary focus:border-primary dark:focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all">
</div>
```

### Number Input (Tiebreaker style)

```html
<input type="number"
       placeholder="e.g. 45"
       min="0"
       max="200"
       class="w-full px-3 py-2 bg-bg-light dark:bg-surface border border-border-light dark:border-border-subtle rounded-lg text-text-dark dark:text-white placeholder-text-secondary-light dark:placeholder-text-secondary focus:border-purple-500 dark:focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-500/20 transition-all">
```

### Form Grid

```html
<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    <!-- Form fields -->
</div>
```

---

## Modals

### Modal Structure

```html
<div id="modal" class="hidden fixed inset-0 z-50 overflow-y-auto" role="dialog" aria-modal="true">
    <!-- Backdrop -->
    <div class="fixed inset-0 bg-black bg-opacity-50 transition-opacity"></div>

    <!-- Modal Container -->
    <div class="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:p-0">
        <!-- Modal Content -->
        <div class="relative inline-block align-bottom bg-bg-light dark:bg-bg-dark rounded-2xl border-2 border-border-light dark:border-border-subtle shadow-2xl text-left overflow-hidden transform transition-all sm:my-8 sm:align-middle sm:max-w-2xl sm:w-full">

            <!-- Header -->
            <div class="border-b border-border-light dark:border-border-subtle p-6">
                <div class="flex items-center justify-between">
                    <h5 class="text-xl font-bold text-text-dark dark:text-white flex items-center gap-2">
                        <i class="fas fa-icon text-primary"></i>
                        <span>Modal Title</span>
                    </h5>
                    <button class="p-2 rounded-lg hover:bg-surface-hover transition-colors">
                        <i class="fas fa-times text-text-secondary-light dark:text-text-secondary"></i>
                    </button>
                </div>
            </div>

            <!-- Body -->
            <div class="py-6 px-6">
                <!-- Modal content -->
            </div>

            <!-- Footer (ESPN-style, optional) -->
            <div class="border-t border-border-light dark:border-border-subtle px-6 py-3">
                <div class="flex items-center justify-between">
                    <a href="#" class="inline-flex items-center gap-1.5 text-sm text-primary hover:text-primary/80 transition-colors font-medium">
                        <i class="fas fa-external-link-alt"></i>
                        <span>Preview</span>
                    </a>
                    <span class="text-sm font-semibold text-text-secondary-light dark:text-text-secondary">CBS</span>
                </div>
            </div>

            <!-- Action Buttons -->
            <div class="border-t border-border-light dark:border-border-subtle p-6 flex flex-col gap-3">
                <button class="w-full px-4 py-3 bg-blue-600/10 dark:bg-blue-600/20 text-blue-600 dark:text-blue-400 rounded-xl font-semibold hover:bg-blue-600/20 dark:hover:bg-blue-600/30 transition-all flex items-center justify-center gap-2">
                    <i class="fas fa-save"></i>
                    <span>SAVE CHANGES</span>
                </button>
                <button class="w-full px-4 py-3 bg-gray-500/10 dark:bg-gray-600/20 text-gray-600 dark:text-gray-400 rounded-xl font-semibold hover:bg-gray-500/20 dark:hover:bg-gray-600/30 transition-all flex items-center justify-center gap-2">
                    <i class="fas fa-times"></i>
                    <span>CANCEL</span>
                </button>
            </div>
        </div>
    </div>
</div>
```

### Modal JavaScript

```javascript
function openModal() {
    const modal = document.getElementById('modal');
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    const modal = document.getElementById('modal');
    modal.classList.add('hidden');
    document.body.style.overflow = '';
}

// Close on backdrop click
document.getElementById('modal')?.addEventListener('click', function(e) {
    if (e.target === this || e.target.classList.contains('bg-opacity-50')) {
        closeModal();
    }
});

// Close on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeModal();
    }
});
```

---

## Animations

### CSS Animations (in input.css)

```css
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}

@keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

.animate-fade-in-up {
    animation: fadeInUp 0.6s ease-out backwards;
}

.shimmer {
    background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.1) 50%, transparent 100%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
}
```

### Transition Classes

```html
<!-- Standard transition -->
<div class="transition-all duration-200">

<!-- Color transition -->
<a class="transition-colors">

<!-- Opacity transition -->
<div class="transition-opacity">
```

---

## Responsive Design

### Breakpoint Reference

| Breakpoint | Min Width | Usage |
|------------|-----------|-------|
| `sm:` | 640px | Small tablets |
| `md:` | 768px | Tablets |
| `lg:` | 1024px | Desktop |
| `xl:` | 1280px | Large desktop |

### Common Responsive Patterns

```html
<!-- Text sizing -->
<h2 class="text-3xl lg:text-5xl">Responsive heading</h2>
<p class="text-base lg:text-xl">Responsive text</p>

<!-- Padding -->
<div class="px-4 py-8 lg:py-12">Responsive padding</div>

<!-- Grid columns -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

<!-- Hide/show -->
<div class="hidden md:block">Desktop only</div>
<div class="md:hidden">Mobile only</div>
```

### Card Grid Pattern

```html
<!-- 1 column mobile, 2 columns tablet+ -->
<div class="grid grid-cols-1 md:grid-cols-2 gap-4">

<!-- 1 column mobile, 2 columns desktop -->
<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

<!-- 1 column mobile, 3 columns desktop -->
<div class="grid grid-cols-1 md:grid-cols-3 gap-6">
```

---

## Empty States

```html
<div class="col-span-full flex flex-col items-center justify-center py-12 text-center">
    <i class="fas fa-info-circle text-6xl text-text-secondary-light dark:text-text-secondary mb-4"></i>
    <h4 class="text-xl font-semibold text-text-dark dark:text-white mb-2">No Data Available</h4>
    <p class="text-text-secondary-light dark:text-text-secondary mb-6">
        Helpful message explaining what to do.
    </p>
    <a href="#" class="inline-flex items-center gap-2 px-6 py-3 bg-primary hover:bg-primary/80 text-white rounded-xl font-semibold transition-all">
        <i class="fas fa-arrow-right"></i>
        <span>Take Action</span>
    </a>
</div>
```

---

## CSS Custom Classes (input.css)

These pre-built classes are available for common patterns:

```css
.section-container    /* Card wrapper with shadow and border */
.section-title        /* Section heading with icon support */
.game-card           /* Game card base styles */
.team-option.selected /* Selected team state */
.btn-primary         /* Primary button */
.btn-secondary       /* Secondary/outline button */
.btn-gradient        /* Gradient CTA button */
.input-base          /* Form input styling */
.gradient-text       /* Orange gradient text effect */
.hover-glow          /* Hover glow effect */
```

---

## Quick Reference Checklist

When building a new page:

- [ ] Use `section-container` for main content sections
- [ ] Use `section-title` with icon for section headers
- [ ] Apply dark mode variants to all colors (`dark:`)
- [ ] Use consistent border-radius (`rounded-xl` or `rounded-2xl`)
- [ ] Add `transition-all duration-200` to interactive elements
- [ ] Include proper spacing with `space-y-4` or `gap-*` classes
- [ ] Use Font Awesome icons consistently
- [ ] Test both light and dark modes
- [ ] Ensure mobile responsiveness with `lg:` breakpoints

---

## Footer

The footer appears on all pages at the bottom and includes branding, quick links, season info, and a theme toggle.

```html
<footer class="bg-surface-light dark:bg-surface border-t border-border-light dark:border-border-subtle mt-12">
    <div class="max-w-7xl mx-auto px-6 py-8">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mb-6">
            <!-- Brand Section -->
            <div>
                <div class="flex items-center gap-2 mb-3">
                    <img src="{% static 'images/logo.png' %}" alt="Logo" class="h-8 w-auto">
                    <span class="text-lg font-bold text-text-dark dark:text-white">Family Pick'em</span>
                </div>
                <p class="text-sm text-text-secondary-light dark:text-text-secondary">
                    Your ultimate NFL pick 'em league experience.
                </p>
            </div>

            <!-- Quick Links -->
            <div>
                <h3 class="text-sm font-semibold text-text-dark dark:text-white uppercase tracking-wide mb-3">Quick Links</h3>
                <ul class="space-y-2">
                    <li><a href="/" class="text-sm text-text-secondary-light dark:text-text-secondary hover:text-primary transition-colors">Home</a></li>
                    <!-- Additional links -->
                </ul>
            </div>

            <!-- Season Info -->
            <div>
                <h3 class="text-sm font-semibold text-text-dark dark:text-white uppercase tracking-wide mb-3">Current Season</h3>
                <ul class="space-y-2 text-sm text-text-secondary-light dark:text-text-secondary">
                    <li class="flex items-center gap-2">
                        <i class="fas fa-calendar-alt text-primary"></i>
                        <span>Season info</span>
                    </li>
                </ul>
            </div>
        </div>

        <!-- Bottom Bar -->
        <div class="pt-6 border-t border-border-light dark:border-border-subtle">
            <div class="flex flex-col sm:flex-row items-center justify-between gap-4">
                <p class="text-sm text-text-secondary-light dark:text-text-secondary">
                    &copy; {% now "Y" %} Family Pick'em. All rights reserved.
                </p>
                <div class="flex items-center gap-4">
                    <button id="theme-toggle-footer" class="text-text-secondary-light dark:text-text-secondary hover:text-primary transition-colors">
                        <i class="fas fa-moon dark:hidden"></i>
                        <i class="fas fa-sun hidden dark:inline"></i>
                    </button>
                </div>
            </div>
        </div>
    </div>
</footer>
```

**Notes:**
- Footer is universal - shows on all pages for all users
- Responsive 3-column layout collapses to single column on mobile
- Theme toggle button syncs with navbar toggle
- Season info shows current user rank for authenticated users

### Fixed Bottom Status Bar

A thin status bar fixed at the bottom of the viewport for authenticated users, showing quick stats and action button:

```html
{% if user.is_authenticated %}
<div class="fixed bottom-0 left-0 right-0 bg-surface/95 dark:bg-surface/95 backdrop-blur-sm border-t border-border-light dark:border-border-subtle z-40 shadow-lg">
    <div class="max-w-7xl mx-auto px-4 py-2.5 flex items-center justify-between text-sm">
        <!-- Week Info -->
        <div class="flex items-center gap-4">
            <span class="text-text-dark dark:text-white font-semibold">
                <i class="fas fa-calendar-week mr-1.5 text-primary"></i>
                Week {{ current_week|default:"--" }}
            </span>
            {% if user_current_rank %}
            <span class="text-text-dark dark:text-white font-semibold">
                <i class="fas fa-trophy mr-1.5 text-yellow-500"></i>
                Rank #{{ user_current_rank }}
            </span>
            {% endif %}
        </div>

        <!-- Submit Picks Button -->
        <a href="/picks/" class="px-4 py-1.5 bg-primary hover:bg-primary/80 text-white rounded-lg font-semibold transition-colors flex items-center gap-2">
            <i class="fas fa-check-circle"></i>
            <span>Submit Picks</span>
        </a>
    </div>
</div>
{% endif %}
```

**Notes:**
- Only visible for authenticated users
- Fixed at bottom of viewport with `z-40` to stay above content
- Semi-transparent background with backdrop blur for visual depth
- Main footer needs `pb-16` padding when user is authenticated to prevent overlap
