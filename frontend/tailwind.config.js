/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        nexBg: '#0B1020',
        nexSurface: '#141C2C',
        nexSurfaceHover: '#1C273C',
        nexBorder: '#283347',
        nexPrimary: '#F3F6FC',
        nexSecondary: '#A7B4C7',
        nexCyan: '#4AC7DB',
        nexYellow: '#F0B84B',
        nexRed: '#F16F78',
        nexGreen: '#4CC9A6',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      }
    },
  },
  plugins: [],
}

