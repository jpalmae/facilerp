/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./app/**/*.py",
  ],
  theme: {
    extend: {
      fontFamily: {
        body: ["Manrope", "sans-serif"],
        display: ["Manrope", "sans-serif"],
      },
      colors: {
        brand: {
          primary: "var(--color-primary)",
          secondary: "var(--color-accent)",
          surface: "var(--surface-base)",
          muted: "var(--text-muted)",
          success: "var(--color-success)",
          warning: "var(--color-warning)",
          danger: "var(--color-danger)",
        },
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        card: "var(--shadow-card)",
        panel: "var(--shadow-panel)",
        soft: "var(--shadow-sm)",
      },
      borderRadius: {
        card: "var(--radius-md)",
        hero: "var(--radius-lg)",
        "4xl": "2rem",
      },
    },
  },
  plugins: [],
};
