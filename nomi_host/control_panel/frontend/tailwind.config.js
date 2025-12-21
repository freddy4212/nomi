/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#00d9ff',
        secondary: '#00ff88',
        danger: '#ff6464',
        bgDark: '#1a1a2e',
        bgLight: '#16213e',
      },
    },
  },
  plugins: [],
}
