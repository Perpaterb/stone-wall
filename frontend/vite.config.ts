import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    proxy: {
      // Host dev mode: proxy API calls to the backend container (exposed on 8000).
      "/api": "http://localhost:8000",
    },
  },
});
