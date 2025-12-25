/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#3891cf', // Updated to match NOMI Logo
        secondary: '#a855f7', // Kept purple as secondary accent
        danger: '#ef4444',
        bgDark: '#111827', // Darker gray-blue
        bgLight: '#1f2937', // Lighter gray-blue
      },
    },
  },
  plugins: [],
}
