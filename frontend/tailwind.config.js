/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#3b82f6',
          hover: '#2563eb',
        },
        admin: {
          bg: '#0f1623',
          surface: '#1a2333',
          border: '#2a3547',
        },
      },
      fontFamily: {
        sans: ['Heebo', 'Arial', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
