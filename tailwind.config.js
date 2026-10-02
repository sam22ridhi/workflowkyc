/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        paytm: {
          deep: '#002970',    // Paytm signature corporate dark navy
          navy: '#001b4c',    // Ultra-deep contrast navy
          blue: '#0052cc',    // Vibrant merchant primary
          cyan: '#00BAF2',    // Signature Paytm bright cyan
          light: '#e6f7fc',   // Cyan soft tint
          soft: '#f0f7ff',    // Paytm light blue tint
          border: '#cfe9fc',  // Border cyan tint
        }
      }
    },
  },
  plugins: [],
};
