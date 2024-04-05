/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/*.jinja",
            "./templates/partials/*.jinja",
            "./templates/*.html",
            "./templates/partials/*.html",
            "./node_modules/flowbite/**/*.js",
            ],
  theme: {},
  plugins: [require('@tailwindcss/forms'),
            require('@tailwindcss/typography'),
            require("flowbite/plugin"),],
  safelist: [
    'prose',
    'prose-slate'
  ]
}