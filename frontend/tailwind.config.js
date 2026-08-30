/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        blood: {
          50: '#fef2f2',
          100: '#ffe1e1',
          200: '#ffc8c8',
          500: '#ef4444',
          600: '#dc2626',
          700: '#b91c1c',
          800: '#991b1b',
          900: '#7f1d1d',
          950: '#450a0a',
        },
        slate: {
          850: '#1e293b',
          950: '#0b0f19',
        }
      }
    },
  },
  plugins: [],
}
