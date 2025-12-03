/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './pickem/pickem_homepage/templates/**/*.html',
    './pickem/pickem_homepage/**/*.py',
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
