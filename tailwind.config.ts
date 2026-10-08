import type { Config } from 'tailwindcss'

export default {
  theme: {
    extend: {
      // Palette from src/assets/dataguard-reference.html.
      colors: {
        ivory: '#F8F4EC',
        porcelain: '#FFFCF7',
        ink: '#2E2A27',
        coral: '#F46B50',
        'coral-soft': '#FCE4DC',
        'coral-text': '#9B3D29',
        cobalt: '#355DE5',
        'cobalt-soft': '#E5EBFD',
        emerald: '#169B6B',
        'emerald-soft': '#DEF4E8',
        'green-text': '#116C4C',
        muted: '#716B64',
        line: '#E4DDD2',
        'nav-muted': '#B7AEA3',
        'nav-text': '#D8D1C7',
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
    },
  },
} satisfies Config
