/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#131314",
        panel: "#1e1f20",
        accent: "#a8c7fa",
        border: "#444746",
      },
    },
  },
  plugins: [],
}
