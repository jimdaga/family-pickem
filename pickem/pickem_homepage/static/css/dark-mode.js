/**
 * Dark Mode Management System for Django + Bootstrap 5
 * 
 * Features:
 * - System preference detection via prefers-color-scheme
 * - User preference persistence in localStorage and Django backend
 * - FOUC (Flash of Unstyled Content) prevention
 * - Real-time theme switching without page reload
 * - Accessibility support with proper ARIA attributes
 */

class DarkModeManager {
    constructor() {
        this.storageKey = 'theme-preference';
        this.themes = {
            LIGHT: 'light',
            DARK: 'dark'
        };
        
        // Initialize theme as early as possible to prevent FOUC
        this.init();
    }

    /**
     * Initialize dark mode system
     * Called immediately when script loads
     */
    init() {
        // Apply theme immediately to prevent FOUC
        this.applyTheme(this.getEffectiveTheme());
        
        // Wait for DOM to be ready for toggle setup
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupToggle());
        } else {
            this.setupToggle();
        }
        
        // Listen for system theme changes
        this.watchSystemTheme();
    }

    /**
     * Get the current user preference from localStorage
     * Defaults to 'light' if no preference is stored
     */
    getUserPreference() {
        return localStorage.getItem(this.storageKey) || this.themes.LIGHT;
    }

    /**
     * Get system preference from CSS media query
     */
    getSystemPreference() {
        return window.matchMedia('(prefers-color-scheme: dark)').matches 
            ? this.themes.DARK 
            : this.themes.LIGHT;
    }

    /**
     * Get the effective theme to apply
     */
    getEffectiveTheme() {
        return this.getUserPreference();
    }

    /**
     * Apply theme to the HTML element using Bootstrap 5 data-bs-theme
     */
    applyTheme(theme) {
        const htmlElement = document.documentElement;

        // Set Bootstrap 5 theme attribute
        htmlElement.setAttribute('data-bs-theme', theme);
        
        // Add custom class for additional styling hooks
        htmlElement.classList.remove('theme-light', 'theme-dark');
        htmlElement.classList.add(`theme-${theme}`);

        // Emit custom event for other components that might need to respond
        window.dispatchEvent(new CustomEvent('themechange', { 
            detail: { theme: theme, userPreference: this.getUserPreference() }
        }));
    }

    /**
     * Set user preference and apply theme
     */
    setTheme(theme) {
        if (!Object.values(this.themes).includes(theme)) {
            console.warn(`Invalid theme: ${theme}`);
            return;
        }

        // Store preference locally
        localStorage.setItem(this.storageKey, theme);
        
        // Apply theme immediately
        this.applyTheme(theme);
        
        // Update toggle UI
        this.updateToggleUI();
        
        // Save to Django backend for authenticated users
        this.saveToBackend(theme);
    }

    /**
     * Save theme preference to Django backend via AJAX
     */
    async saveToBackend(theme) {
        // Only save for authenticated users
        const isAuthenticated = document.querySelector('meta[name="user-authenticated"]')?.content === 'true';
        if (!isAuthenticated) return;

        try {
            const response = await fetch('/toggle-theme/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({
                    theme: theme
                })
            });

            if (!response.ok) {
                console.warn('Failed to save theme preference to backend');
            }
        } catch (error) {
            console.warn('Error saving theme preference:', error);
        }
    }

    /**
     * Get CSRF token from Django
     */
    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
               document.querySelector('meta[name="csrf-token"]')?.content ||
               '';
    }

    /**
     * Watch for system theme changes (no longer needed but kept for compatibility)
     */
    watchSystemTheme() {
        // No longer watching system changes since we removed system option
    }

    /**
     * Setup theme toggle button functionality
     */
    setupToggle() {
        const toggleButton = document.getElementById('theme-toggle');
        if (!toggleButton) return;

        // Set initial state
        this.updateToggleUI();

        // Add click handler
        toggleButton.addEventListener('click', (e) => {
            e.preventDefault();
            this.toggleTheme();
        });

        // Add keyboard support
        toggleButton.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.toggleTheme();
            }
        });
    }

    /**
     * Toggle between light and dark themes
     */
    toggleTheme() {
        const current = this.getUserPreference();
        const next = current === this.themes.LIGHT ? this.themes.DARK : this.themes.LIGHT;
        this.setTheme(next);
    }

    /**
     * Update toggle button UI to reflect current state
     */
    updateToggleUI() {
        const toggleButton = document.getElementById('theme-toggle');
        const toggleIcon = document.getElementById('theme-toggle-icon');
        const toggleText = document.getElementById('theme-toggle-text');
        
        if (!toggleButton) return;

        const userPref = this.getUserPreference();
        const effectiveTheme = this.getEffectiveTheme();
        
        // Update icon and text based on current preference
        const configs = {
            [this.themes.LIGHT]: {
                icon: 'fas fa-sun',
                text: 'Light',
                label: 'Switch to Dark Mode'
            },
            [this.themes.DARK]: {
                icon: 'fas fa-moon',
                text: 'Dark',
                label: 'Switch to Light Mode'
            }
        };

        const config = configs[userPref] || configs[this.themes.LIGHT];
        
        if (toggleIcon) {
            toggleIcon.className = config.icon;
        }
        
        if (toggleText) {
            toggleText.textContent = config.text;
        }
        
        // Update ARIA attributes for accessibility
        toggleButton.setAttribute('aria-label', config.label);
        toggleButton.setAttribute('title', config.label);
        
        // Update data attribute for CSS styling
        toggleButton.setAttribute('data-theme', userPref);
    }

    /**
     * Initialize theme from Django backend for authenticated users
     */
    static initFromBackend(userDarkMode) {
        if (userDarkMode !== null && userDarkMode !== undefined) {
            const theme = userDarkMode ? 'dark' : 'light';
            localStorage.setItem('theme-preference', theme);
        }
    }
}

// Initialize dark mode manager immediately (before DOM ready to prevent FOUC)
const darkModeManager = new DarkModeManager();

// Expose global functions for Django template integration
window.DarkMode = {
    init: (userDarkMode) => DarkModeManager.initFromBackend(userDarkMode),
    manager: darkModeManager
}; 