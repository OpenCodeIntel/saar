/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        serif: ['"Instrument Serif"', 'Georgia', 'serif'],
        sans: ['"DM Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        // RGB format so Tailwind opacity modifiers (/20, /50 etc) work
        navy: {
          950: 'rgb(var(--navy-950) / <alpha-value>)',
          900: 'rgb(var(--navy-900) / <alpha-value>)',
          800: 'rgb(var(--navy-800) / <alpha-value>)',
          700: 'rgb(var(--navy-700) / <alpha-value>)',
        },
        amber: {
          saar: 'rgb(var(--amber-saar) / <alpha-value>)',
          muted: 'rgb(var(--amber-saar) / 0.09)',
          glow: 'rgb(var(--amber-saar) / 0.15)',
        },
        cream: {
          DEFAULT: 'rgb(var(--cream) / <alpha-value>)',
          muted: 'rgb(var(--cream-muted) / <alpha-value>)',
          dim: 'rgb(var(--cream-dim) / <alpha-value>)',
        },
      },
      animation: {
        'type-cursor': 'blink 1s step-end infinite',
        'fade-up': 'fadeUp 0.6s ease forwards',
        'fade-in': 'fadeIn 0.4s ease forwards',
      },
      keyframes: {
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        fadeUp: {
          from: { opacity: '0', transform: 'translateY(24px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
