import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The browser talks to the FastAPI service directly (CORS is open in
// backend/app/main.py). VITE_API_BASE selects the backend base URL.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
});
