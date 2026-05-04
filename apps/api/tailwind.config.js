const path = require('path')

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [path.join(__dirname, 'templates/**/*.html')],
  theme: {
    extend: {},
  },
  plugins: [],
}
