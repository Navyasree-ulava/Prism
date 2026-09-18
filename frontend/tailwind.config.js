/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        mono: [
          'IBM Plex Mono',
          'Cascadia Code',
          'Fira Code',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Monaco',
          'Courier New',
          'monospace',
        ],
      },
      colors: {
        surface: {
          DEFAULT: '#ffffff',
          dark: '#0d0d1c',
        },
      },
    },
  },
  plugins: [],
}
