/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['var(--gc-mono)'],
      },
      colors: {
        gc: {
          bg: 'var(--gc-bg)',
          panel: 'var(--gc-panel)',
          text: 'var(--gc-text)',
          muted: 'var(--gc-muted)',
          blue: 'var(--gc-blue)',
          amber: 'var(--gc-amber)',
          red: 'var(--gc-red)',
        },
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(0, 212, 255, 0.25), 0 0 24px rgba(0, 212, 255, 0.12)',
        glowAmber: '0 0 0 1px rgba(255, 170, 0, 0.28), 0 0 24px rgba(255, 170, 0, 0.12)',
        glowRed: '0 0 0 1px rgba(255, 68, 68, 0.28), 0 0 24px rgba(255, 68, 68, 0.12)',
      },
    },
  },
  plugins: [],
}

