/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/*.jinja",
            "./templates/partials/*.jinja"
            ],
  theme: {
    extend: {},
  },
  plugins: [require('@tailwindcss/forms'),],
}

