import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// // https://vite.dev/config/
// export default defineConfig({
//   plugins: [react()],
//   cacheDir: "./.vite-cache",
// })

export default defineConfig({
  plugins: [react()],
  cacheDir: "C:/temp/schedula-vite-cache",
  server: {
    allowedHosts: ["schedula.cs.bgu.ac.il"],
  },
});