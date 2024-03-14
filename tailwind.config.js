/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/*.jinja",
            "./templates/partials/*.jinja",
            ],
  theme: {},
  plugins: [require('@tailwindcss/forms'),],
}