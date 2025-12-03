# Tailwind CSS Migration Plan for Family Pickem

## Executive Summary

This document outlines a comprehensive, phased approach to migrate the Family Pickem Django application from Bootstrap 5 to Tailwind CSS, implementing a modern dark-mode-first design system.

**Production Site Reference:** https://family-pickem.com/
Use this as the source of truth for visual design and functionality during migration.

---

## Current State Analysis

### Technology Stack
- **Framework:** Django 4.0.2
- **Current CSS:** Bootstrap 5.0.0 (CDN)
- **Custom CSS:** `style.css` (~1400+ lines), `dark-mode.css`
- **Font:** Heebo (Google Fonts)
- **Icons:** Font Awesome 6.0.0
- **JS Dependencies:** Bootstrap JS, Popper.js

### Key Templates Identified
1. **base.html** - Main layout with navbar, footer
2. **home.html** - Hero section, status cards, leaderboard preview, message board
3. **picks.html** - Weekly pick submission interface
4. **standings.html** - Leaderboard and week winners
5. **scores.html** - Live game scores
6. **stats.html** - Player statistics
7. **user_profile.html** - User profiles
8. **rules.html** - League rules

### Bootstrap Dependencies
- **Navbar:** `navbar-expand-lg`, dropdowns, collapse
- **Grid:** Container, rows, cols
- **Cards:** Used extensively
- **Buttons:** `btn-primary`, `btn-outline-*`
- **Utilities:** Spacing (mb-4, me-2, etc.), text utilities, display utilities
- **Components:** Dropdowns, modals(?), progress bars

### Custom Components Requiring Migration
- Modern gradient buttons (`.btn-gradient-primary`)
- Game cards with team selection
- Leaderboard cards with hover effects
- Message board with voting system
- Status cards and progress indicators
- Dark mode implementation (custom JS + CSS)

---

## Migration Strategy

### Phase 1: Foundation Setup (Week 1)
**Goal:** Install Tailwind, configure build system, establish color/typography tokens

#### 1.1 Install Tailwind CSS
```bash
# Install Node.js dependencies
npm init -y
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init

# Install Django Tailwind integration (optional but recommended)
pip install django-tailwind
```

#### 1.2 Configure Tailwind
**File:** `tailwind.config.js`
```javascript
module.exports = {
  darkMode: 'class',
  content: [
    './pickem_homepage/templates/**/*.html',
    './pickem_homepage/**/*.py',
  ],
  theme: {
    extend: {
      colors: {
        // Dark Mode (Primary)
        'bg-dark': '#0B0E13',
        'surface': '#121821',
        'surface-hover': '#1A212C',
        'border-subtle': '#1F2937',
        'primary': '#FF6B1A',
        'secondary': '#9FE870',
        'text-primary': '#FFFFFF',
        'text-secondary': '#A9B4C4',
        'muted': '#6B7280',

        // Light Mode
        'bg-light': '#F8FAFC',
        'surface-light': '#FFFFFF',
        'border-light': '#E2E8F0',
        'secondary-light': '#3CA455',
        'text-dark': '#0F172A',
        'text-secondary-light': '#475569',
      },
      fontFamily: {
        sans: ['Inter', 'Urbanist', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'monospace'],
      },
      boxShadow: {
        'card': '0 4px 6px rgba(0, 0, 0, 0.1)',
        'card-hover': '0 8px 25px rgba(0,0,0,0.15)',
        'glow-primary': '0 0 20px rgba(255,107,26,0.4)',
      },
      borderRadius: {
        'xl': '1rem',
        '2xl': '1.5rem',
      },
    },
  },
  plugins: [],
}
```

#### 1.3 Set Up Build Process
**File:** `package.json`
```json
{
  "scripts": {
    "build:css": "tailwindcss -i ./pickem_homepage/static/css/input.css -o ./pickem_homepage/static/css/tailwind.css --watch",
    "build:prod": "tailwindcss -i ./pickem_homepage/static/css/input.css -o ./pickem_homepage/static/css/tailwind.css --minify"
  },
  "devDependencies": {
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0"
  }
}
```

**File:** `pickem_homepage/static/css/input.css`
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Custom component classes will go here */
```

#### 1.4 Update Google Fonts
Replace Heebo with Inter/Urbanist in `base.html`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;900&display=swap" rel="stylesheet">
```

---

### Phase 2: Base Template Migration (Week 1-2)
**Goal:** Convert base.html, establish reusable patterns

#### 2.1 Update base.html Structure
**Key Changes:**
- Remove Bootstrap CDN links
- Add Tailwind CSS link
- Convert HTML class to use dark mode class strategy
- Implement dark mode toggle

**Before (Bootstrap):**
```html
<html lang="en" data-bs-theme="{% if user_theme_preference %}{{ user_theme_preference }}{% else %}light{% endif %}">
```

**After (Tailwind):**
```html
<html lang="en" class="{% if user_theme_preference == 'dark' %}dark{% endif %}">
```

#### 2.2 Convert Navbar
**Bootstrap Classes → Tailwind Classes Mapping:**

| Bootstrap | Tailwind |
|-----------|----------|
| `navbar navbar-expand-lg fixed-top` | `fixed top-0 w-full z-50` |
| `container` | `max-w-7xl mx-auto px-4` |
| `navbar-brand` | `flex items-center` |
| `navbar-toggler` | `lg:hidden` button |
| `navbar-collapse` | `hidden lg:flex` |
| `nav-item` | Custom with flex |
| `dropdown-menu` | Custom dropdown (or use Headless UI) |
| `btn btn-primary` | `bg-primary hover:bg-primary/80 rounded-xl px-4 py-2` |

**New Navbar Structure:**
```html
<nav class="fixed top-0 w-full bg-[#0B0E13]/80 backdrop-blur-lg border-b border-border-subtle z-50">
  <div class="max-w-7xl mx-auto px-4">
    <div class="flex items-center justify-between h-16">
      <!-- Logo -->
      <a href="/" class="flex items-center space-x-2">
        <img src="{% static 'images/logo.png' %}" alt="Logo" class="h-10 w-10">
        <span class="hidden sm:inline text-white font-semibold">Family Pickem</span>
      </a>

      <!-- Mobile menu button -->
      <button class="lg:hidden p-2 text-white" id="mobile-menu-btn">
        <i class="fas fa-bars"></i>
      </button>

      <!-- Desktop Navigation -->
      <ul class="hidden lg:flex items-center space-x-1">
        <li><a href="/" class="px-4 py-2 rounded-xl text-text-secondary hover:text-white hover:bg-surface-hover transition-all">
          <i class="fas fa-home"></i>
        </a></li>
        <!-- More nav items -->
      </ul>

      <!-- Right side actions -->
      <div class="hidden lg:flex items-center space-x-4">
        {% if user.is_authenticated %}
          <a href="/picks" class="px-4 py-2 bg-primary text-white rounded-xl font-semibold hover:bg-primary/80 transition-all">
            <i class="fas fa-edit me-2"></i>Submit Weekly Picks
          </a>
        {% endif %}
      </div>
    </div>
  </div>

  <!-- Mobile menu (hidden by default) -->
  <div id="mobile-menu" class="hidden lg:hidden">
    <!-- Mobile nav items -->
  </div>
</nav>
```

#### 2.3 Convert Main Content Area
```html
<main class="pt-20 min-h-screen bg-bg-dark dark:bg-bg-dark">
  {% block content %}{% endblock %}
</main>
```

#### 2.4 Implement Dark Mode Toggle
**JavaScript for Theme Switching:**
```javascript
// Dark mode implementation
const ThemeManager = {
  init() {
    const html = document.documentElement;
    const currentTheme = localStorage.getItem('theme') || 'dark';

    if (currentTheme === 'dark') {
      html.classList.add('dark');
    }
  },

  toggle() {
    const html = document.documentElement;
    const isDark = html.classList.contains('dark');

    if (isDark) {
      html.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    } else {
      html.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    }

    // Optionally sync with Django backend
    this.syncWithBackend(isDark ? 'light' : 'dark');
  },

  syncWithBackend(theme) {
    fetch('/api/update-theme/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
      },
      body: JSON.stringify({ theme })
    });
  }
};

document.addEventListener('DOMContentLoaded', () => ThemeManager.init());
```

---

### Phase 3: Component Migration (Week 2-3)
**Goal:** Create reusable Tailwind components for key UI patterns

#### 3.1 Create Custom Component Classes
**File:** `pickem_homepage/static/css/input.css`

```css
@layer components {
  /* Cards */
  .card-base {
    @apply rounded-2xl p-6 bg-surface dark:bg-surface shadow-xl border border-border-subtle transition-all;
  }

  .card-hover {
    @apply hover:shadow-card-hover hover:-translate-y-1;
  }

  /* Buttons */
  .btn-primary {
    @apply px-4 py-2 bg-primary text-white rounded-xl font-semibold hover:bg-primary/80 transition-all duration-200;
  }

  .btn-secondary {
    @apply px-4 py-2 border border-border-subtle text-white rounded-xl hover:bg-surface-hover transition-all;
  }

  .btn-gradient {
    @apply bg-gradient-to-r from-primary to-orange-600 text-white px-6 py-3 rounded-xl font-semibold hover:shadow-glow-primary transition-all;
  }

  /* Status Cards */
  .status-card {
    @apply bg-surface rounded-2xl p-4 border border-border-subtle space-y-2;
  }

  /* Game Cards */
  .game-card {
    @apply bg-surface rounded-2xl p-5 border border-border-subtle shadow-lg hover:bg-surface-hover transition-all space-y-4;
  }

  /* Leaderboard Items */
  .leaderboard-card {
    @apply bg-surface rounded-2xl p-4 border border-border-subtle flex items-center justify-between hover:shadow-card-hover hover:-translate-y-1 transition-all;
  }

  /* Section Container */
  .section-container {
    @apply bg-surface dark:bg-surface rounded-2xl p-6 shadow-xl border border-border-subtle mb-4;
  }

  .section-title {
    @apply text-2xl font-bold text-white flex items-center mb-4;
  }
}
```

#### 3.2 Convert Home Page Components

**Hero Section:**
```html
<div class="max-w-7xl mx-auto px-4 py-8">
  <!-- Hero -->
  <div class="text-center mb-12">
    <div class="mb-6">
      <img src="{% static 'images/logo.png' %}" alt="Logo" class="w-32 h-32 mx-auto">
    </div>
    <h1 class="text-4xl lg:text-6xl font-extrabold text-white mb-4">
      Welcome to Family Pickem
    </h1>
    <p class="text-xl text-text-secondary max-w-2xl mx-auto">
      Your ultimate NFL pick 'em league experience
    </p>
  </div>
</div>
```

**Status Cards:**
```html
<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
  <div class="status-card">
    <div class="flex items-center space-x-3">
      <div class="w-12 h-12 bg-surface-hover rounded-xl flex items-center justify-center">
        <i class="fas fa-football-ball text-primary text-xl"></i>
      </div>
      <div>
        <div class="text-2xl font-bold text-white">{{ current_games }}</div>
        <div class="text-sm text-text-secondary">Games This Week</div>
      </div>
    </div>
  </div>
  <!-- More status cards -->
</div>
```

**Quick Action Cards:**
```html
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
  <a href="/picks/" class="group block">
    <div class="bg-surface rounded-2xl p-6 border border-border-subtle hover:border-primary hover:shadow-glow-primary transition-all">
      <div class="w-12 h-12 bg-primary/20 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
        <i class="fas fa-edit text-primary text-xl"></i>
      </div>
      <h5 class="text-lg font-semibold text-white mb-2">Submit Picks</h5>
      <p class="text-text-secondary text-sm">Make your Week {{ current_week }} predictions</p>
    </div>
  </a>
  <!-- More action cards -->
</div>
```

#### 3.3 Convert Picks Page

**Game Cards with Team Selection:**
```html
<div class="space-y-4">
  {% for game in game_list %}
  <div class="game-card">
    <!-- Game Header -->
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center space-x-2 text-sm text-text-secondary">
        <i class="fas fa-calendar"></i>
        <span>{{ game.startTimestamp|date:"D, M d" }}</span>
        <span class="text-muted">{{ game.startTimestamp|date:"g:i A" }}</span>
      </div>
      {% if game.statusType != 'notstarted' %}
      <span class="px-3 py-1 bg-red-500/20 text-red-400 rounded-lg text-sm">
        <i class="fas fa-lock mr-1"></i>Locked
      </span>
      {% else %}
      <span class="px-3 py-1 bg-secondary/20 text-secondary rounded-lg text-sm">
        <i class="fas fa-check-circle mr-1"></i>Available
      </span>
      {% endif %}
    </div>

    <!-- Team Selection -->
    <div class="grid grid-cols-2 gap-4">
      <!-- Away Team -->
      <button class="team-option group p-4 bg-surface-hover rounded-xl border-2 border-transparent hover:border-primary transition-all"
              data-team="{{ game.awayTeamSlug }}">
        <div class="flex flex-col items-center space-y-2">
          <img src="{{ away_logo }}" alt="{{ game.awayTeamName }}" class="w-16 h-16">
          <span class="font-semibold text-white">{{ game.awayTeamName }}</span>
          <span class="text-sm text-text-secondary">{{ game.awayTeamAbbrev }}</span>
        </div>
      </button>

      <!-- Home Team -->
      <button class="team-option group p-4 bg-surface-hover rounded-xl border-2 border-transparent hover:border-primary transition-all"
              data-team="{{ game.homeTeamSlug }}">
        <div class="flex flex-col items-center space-y-2">
          <img src="{{ home_logo }}" alt="{{ game.homeTeamName }}" class="w-16 h-16">
          <span class="font-semibold text-white">{{ game.homeTeamName }}</span>
          <span class="text-sm text-text-secondary">{{ game.homeTeamAbbrev }}</span>
        </div>
      </button>
    </div>
  </div>
  {% endfor %}
</div>
```

#### 3.4 Convert Standings/Leaderboard

```html
<div class="section-container">
  <h3 class="section-title">
    <i class="fas fa-medal mr-2"></i>Leaderboard
  </h3>

  <div class="space-y-2">
    {% for player in player_points %}
    <a href="{% url 'user_profile' player.userID %}" class="leaderboard-card block">
      <div class="flex items-center space-x-4">
        <!-- Rank Badge -->
        <div class="flex-shrink-0 w-10 h-10 rounded-full
                    {% if forloop.counter == 1 %}bg-yellow-500
                    {% elif forloop.counter == 2 %}bg-gray-400
                    {% elif forloop.counter == 3 %}bg-orange-600
                    {% else %}bg-surface-hover{% endif %}
                    flex items-center justify-center font-bold text-white">
          {{ forloop.counter }}
        </div>

        <!-- Avatar & Name -->
        <img src="{{ avatar }}" alt="{{ username }}" class="w-12 h-12 rounded-full">
        <div class="flex-grow">
          <div class="font-semibold text-white">{{ username }}</div>
          <div class="text-sm text-text-secondary">{{ tagline }}</div>
        </div>

        <!-- Points -->
        <div class="text-right">
          <div class="text-2xl font-bold text-secondary">{{ player.total_points }}</div>
          <div class="text-xs text-text-secondary">POINTS</div>
        </div>
      </div>
    </a>
    {% endfor %}
  </div>
</div>
```

---

### Phase 4: Advanced Features (Week 3-4)
**Goal:** Message board, animations, mobile optimizations

#### 4.1 Message Board with Voting
```html
<div class="section-container">
  <h3 class="section-title">
    <i class="fas fa-comments mr-2"></i>League Discussion
  </h3>

  <!-- Post Form -->
  <div class="mb-6 bg-surface-hover rounded-xl p-4">
    <form id="create-post-form">
      <div class="flex items-center space-x-3">
        <img src="{{ user_avatar }}" alt="You" class="w-10 h-10 rounded-full">
        <input type="text"
               class="flex-grow bg-surface border border-border-subtle rounded-xl px-4 py-2 text-white focus:border-primary focus:outline-none"
               placeholder="Share your thoughts...">
        <button type="submit" class="btn-primary">
          <i class="fas fa-paper-plane"></i>
        </button>
      </div>
    </form>
  </div>

  <!-- Posts -->
  <div class="space-y-4">
    {% for post in message_posts %}
    <div class="bg-surface-hover rounded-xl p-4 border border-border-subtle">
      <!-- Post Header -->
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center space-x-3">
          <img src="{{ post_avatar }}" alt="{{ post.user.username }}" class="w-10 h-10 rounded-full">
          <div>
            <div class="font-semibold text-white">{{ post.user.username }}</div>
            <div class="text-sm text-text-secondary">{{ post.created_at|timesince }} ago</div>
          </div>
        </div>
      </div>

      <!-- Post Content -->
      <div class="text-white mb-4">{{ post.content }}</div>

      <!-- Post Actions -->
      <div class="flex items-center space-x-4 text-text-secondary">
        <!-- Voting -->
        <div class="flex items-center space-x-2">
          <button class="vote-btn hover:text-primary transition-colors" data-vote="up">
            <i class="fas fa-arrow-up"></i>
          </button>
          <span class="font-semibold">{{ post.score }}</span>
          <button class="vote-btn hover:text-blue-400 transition-colors" data-vote="down">
            <i class="fas fa-arrow-down"></i>
          </button>
        </div>

        <!-- Comments -->
        <button class="flex items-center space-x-1 hover:text-white transition-colors">
          <i class="fas fa-comment"></i>
          <span>{{ post.comment_count }}</span>
        </button>
      </div>
    </div>
    {% endfor %}
  </div>
</div>
```

#### 4.2 Add Animations and Transitions
```css
@layer utilities {
  /* Hover glow effect */
  .hover-glow {
    @apply transition-all duration-200 hover:shadow-glow-primary;
  }

  /* Slide in animation */
  @keyframes slideIn {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .animate-slide-in {
    animation: slideIn 0.3s ease-out;
  }

  /* Pulse animation for live updates */
  @keyframes pulse-glow {
    0%, 100% {
      box-shadow: 0 0 0 0 rgba(255, 107, 26, 0.4);
    }
    50% {
      box-shadow: 0 0 20px 10px rgba(255, 107, 26, 0);
    }
  }

  .animate-pulse-glow {
    animation: pulse-glow 2s ease-in-out infinite;
  }
}
```

#### 4.3 Mobile Responsiveness
- All cards stack vertically on mobile
- Navbar collapses to hamburger menu
- Game cards show teams vertically
- Font sizes scale down appropriately
- Touch-friendly button sizes (min 44x44px)

---

### Phase 5: Testing & Optimization (Week 4)
**Goal:** QA, performance optimization, cleanup

#### 5.1 Testing Checklist
- [ ] All pages render correctly in both themes
- [ ] Mobile responsiveness (320px to 2560px)
- [ ] Cross-browser testing (Chrome, Firefox, Safari, Edge)
- [ ] Dark/light mode toggle works
- [ ] All forms submit correctly
- [ ] Dropdown menus work
- [ ] Interactive elements (voting, picks) function
- [ ] Images load correctly
- [ ] Font loading performance
- [ ] Accessibility (ARIA labels, keyboard navigation)

#### 5.2 Performance Optimization
```javascript
// Purge unused Tailwind classes in production
// tailwind.config.js
module.exports = {
  content: [
    './pickem_homepage/templates/**/*.html',
    './pickem_homepage/**/*.py',
  ],
  // This automatically purges unused classes
}
```

**CSS File Size Goals:**
- Development: ~3-4MB (all classes)
- Production: ~50-100KB (purged)

#### 5.3 Remove Bootstrap
Once migration is complete:
1. Remove Bootstrap CDN links from `base.html`
2. Remove Bootstrap JS dependencies
3. Remove `django-bootstrap-v5` from requirements.txt
4. Archive old `style.css` and `dark-mode.css`
5. Update any Django forms using Bootstrap classes

---

## Implementation Checklist

### Week 1: Foundation
- [ ] Install Tailwind CSS and dependencies
- [ ] Configure `tailwind.config.js` with design tokens
- [ ] Set up build process (npm scripts)
- [ ] Create `input.css` with base layers
- [ ] Update fonts to Inter/Urbanist
- [ ] Test build process

### Week 2: Base & Navigation
- [ ] Convert `base.html` structure
- [ ] Migrate navbar (desktop + mobile)
- [ ] Implement dark mode toggle
- [ ] Create reusable component classes
- [ ] Test base template on all pages
- [ ] Convert footer and banner system

### Week 3: Page Templates
- [ ] Convert `home.html`
  - [ ] Hero section
  - [ ] Status cards
  - [ ] Quick action cards
  - [ ] Leaderboard preview
  - [ ] League stats
- [ ] Convert `picks.html`
  - [ ] Progress indicator
  - [ ] Game cards
  - [ ] Team selection UI
- [ ] Convert `standings.html`
  - [ ] Leaderboard cards
  - [ ] Week winners grid
  - [ ] Detailed breakdown
- [ ] Convert `scores.html`
- [ ] Convert `stats.html`
- [ ] Convert `user_profile.html`
- [ ] Convert `rules.html`

### Week 4: Advanced Features & Polish
- [ ] Message board with voting
- [ ] Comment threading UI
- [ ] Add animations and transitions
- [ ] Mobile menu improvements
- [ ] Loading states
- [ ] Error states
- [ ] Empty states
- [ ] Toast notifications (if needed)

### Week 5: Testing & Cleanup
- [ ] Cross-browser testing
- [ ] Mobile device testing
- [ ] Accessibility audit
- [ ] Performance optimization
- [ ] Remove Bootstrap dependencies
- [ ] Clean up old CSS files
- [ ] Update documentation
- [ ] Deploy to staging
- [ ] User acceptance testing
- [ ] Deploy to production

---

## Risk Mitigation

### Potential Issues & Solutions

1. **Bootstrap JS Dependencies**
   - **Issue:** Dropdowns, modals, collapse require Bootstrap JS
   - **Solution:** Replace with vanilla JS or Alpine.js/Headless UI

2. **Django Forms with Bootstrap**
   - **Issue:** Crispy forms render Bootstrap markup
   - **Solution:** Create custom Tailwind form templates or use django-tailwind-forms

3. **Custom Dark Mode JS Conflicts**
   - **Issue:** Existing dark-mode.js may conflict with Tailwind's approach
   - **Solution:** Refactor to use Tailwind's `dark:` classes, localStorage sync

4. **Large CSS File in Development**
   - **Issue:** Full Tailwind CSS is 3-4MB
   - **Solution:** Use JIT mode (default in v3), purge for production

5. **Third-party Plugin Styles**
   - **Issue:** Some plugins may have Bootstrap-specific styling
   - **Solution:** Override with Tailwind utilities or custom CSS

---

## Rollback Plan

If critical issues arise:

1. **Keep Bootstrap loaded temporarily**
   - Run both frameworks in parallel during migration
   - Gradual page-by-page rollout

2. **Git branches**
   - Keep `main` branch stable
   - Work on `tailwind-migration` branch
   - Can revert if needed

3. **Feature flags**
   - Use Django settings to toggle Tailwind vs Bootstrap
   - A/B test with users

---

## Success Metrics

- **Performance:**
  - Page load time < 2s
  - CSS file size < 100KB (production)

- **Visual Quality:**
  - Dark mode properly implemented
  - Consistent spacing and typography
  - Smooth animations (60fps)

- **User Experience:**
  - No broken functionality
  - Mobile-friendly (touch targets ≥44px)
  - Accessible (WCAG 2.1 AA)

---

## Post-Migration Enhancements

Once migration is complete, consider:

1. **Progressive Web App (PWA)**
   - Add service worker
   - Offline support
   - Install prompts

2. **Advanced Animations**
   - Page transitions
   - Micro-interactions
   - Loading skeletons

3. **Component Library**
   - Document reusable components
   - Create style guide
   - Storybook integration?

4. **Design System**
   - Formalize spacing scale
   - Typography scale
   - Color palette documentation

---

## Resources & References

- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [Tailwind UI Components](https://tailwindui.com/)
- [Headless UI](https://headlessui.com/) - Unstyled accessible components
- [Alpine.js](https://alpinejs.dev/) - Lightweight JS framework (optional Bootstrap JS replacement)
- [Django Tailwind](https://django-tailwind.readthedocs.io/)

---

## Notes

- Keep Font Awesome icons (they work with Tailwind)
- Maintain existing Django template structure
- Preserve all backend functionality
- Focus on CSS/HTML changes only (no Python refactoring needed)
- Test incrementally (page by page)
- Document component patterns for future developers

---

**Last Updated:** 2025-12-02
**Migration Branch:** `tailwind-css-migration`
**Status:** Ready to begin Phase 1
