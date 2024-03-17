/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/*.jinja",
            "./templates/partials/*.jinja",
            "./templates/*.html",
            "./templates/partials/*.html",
            ],
  theme: {},
  plugins: [require('@tailwindcss/forms'),
            require('@tailwindcss/typography'),
            require("flowbite/plugin"),],
}