import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
  server: {
    proxy: {
      "/cohorts": "http://localhost:8000",
      "/runs": "http://localhost:8000",
      "/agent": "http://localhost:8000",
      "/jobs": "http://localhost:8000",
    },
  },
});
