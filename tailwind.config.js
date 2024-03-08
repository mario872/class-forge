/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/*.jinja",
            "./templates/partials/*.jinja"
            ],
  safelist: [
    {
      pattern: /^bg\-.*$/,
    },
  ],
  theme: {
    extend: {},
  },
  plugins: [require('@tailwindcss/forms'),],
}

