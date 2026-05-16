const path = require('path')

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [path.join(__dirname, 'templates/**/*.html')],
  theme: {
    extend: {
      colors: {
        cream: {
          50: '#FFFDF7',
          100: '#FFF8E7',
          200: '#FBEFD0',
          300: '#F5E2B0',
        },
        ink: {
          DEFAULT: '#1A1A2E',
          soft: '#2D2D44',
          mute: '#5C5C75',
        },
        tangerine: {
          DEFAULT: '#FF6B35',
          dark: '#E5501F',
          light: '#FFE4D6',
        },
        teal: {
          DEFAULT: '#06A77D',
          dark: '#048062',
          light: '#D2F4E8',
        },
        berry: {
          DEFAULT: '#E63946',
          dark: '#C72F3B',
          light: '#FBD9DC',
        },
        honey: {
          DEFAULT: '#FFB627',
          dark: '#E59A12',
          light: '#FFEFCC',
        },
        sky: {
          DEFAULT: '#3A86FF',
          dark: '#1E6BE6',
          light: '#D7E6FF',
        },
        lavender: '#F4E9FF',
      },
      fontFamily: {
        display: ['Fraunces', 'ui-serif', 'Georgia', 'serif'],
        sans: ['"DM Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        'pop-sm': '4px 4px 0 #1A1A2E',
        'pop': '6px 6px 0 #1A1A2E',
        'pop-lg': '10px 10px 0 #1A1A2E',
        'pop-tangerine': '6px 6px 0 #FF6B35',
        'pop-teal': '6px 6px 0 #06A77D',
        'pressed': 'inset 0 -4px 0 rgba(0,0,0,0.18)',
      },
      backgroundImage: {
        'dot-grid': "radial-gradient(circle, #1A1A2E 1px, transparent 1px)",
      },
      backgroundSize: {
        'dot-grid': '24px 24px',
      },
      keyframes: {
        'flip-in': {
          '0%': { transform: 'rotateY(90deg)', opacity: '0' },
          '100%': { transform: 'rotateY(0deg)', opacity: '1' },
        },
        'pop-in': {
          '0%': { transform: 'scale(0.85) rotate(-2deg)', opacity: '0' },
          '60%': { transform: 'scale(1.04) rotate(-1deg)', opacity: '1' },
          '100%': { transform: 'scale(1) rotate(-1.5deg)', opacity: '1' },
        },
        'rise': {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        'wiggle': {
          '0%, 100%': { transform: 'rotate(-2deg)' },
          '50%': { transform: 'rotate(2deg)' },
        },
        'confetti': {
          '0%': { transform: 'translateY(-20px) rotate(0deg)', opacity: '1' },
          '100%': { transform: 'translateY(220px) rotate(720deg)', opacity: '0' },
        },
        'sparkle': {
          '0%, 100%': { transform: 'scale(0.8)', opacity: '0.4' },
          '50%': { transform: 'scale(1.2)', opacity: '1' },
        },
      },
      animation: {
        'flip-in': 'flip-in 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) both',
        'pop-in': 'pop-in 0.55s cubic-bezier(0.34, 1.56, 0.64, 1) both',
        'rise': 'rise 0.5s ease-out both',
        'wiggle': 'wiggle 0.6s ease-in-out',
        'sparkle': 'sparkle 1.6s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
