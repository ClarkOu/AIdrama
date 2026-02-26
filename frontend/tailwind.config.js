/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#f0f4ff',
          100: '#dde6ff',
          500: '#4f6ef7',
          600: '#3b5af5',
          700: '#2d47e0',
          900: '#1a2c8a',
        },
      },
    },
  },
  plugins: [],
}
