import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const soarTarget = env.VITE_SOAR_URL || "https://10.236.39.108:8443";

  return {
    base: "./",
    define: {
      "process.env.NODE_ENV": JSON.stringify(mode === "production" ? "production" : "development"),
    },
    plugins: [react()],
    server: {
      port: 5173,
      proxy: env.VITE_SOAR_HANDLER_BASE
        ? {
            "/rest": {
              target: soarTarget,
              changeOrigin: true,
              secure: false,
              configure: (proxy) => {
                const user = env.VITE_SOAR_USER;
                const pass = env.VITE_SOAR_PASS;
                if (user && pass) {
                  const token = Buffer.from(`${user}:${pass}`).toString("base64");
                  proxy.on("proxyReq", (proxyReq) => {
                    proxyReq.setHeader("Authorization", `Basic ${token}`);
                  });
                }
              },
            },
          }
        : undefined,
    },
    build: {
      outDir: resolve(__dirname, "../soar_playbook_builder/widgets"),
      emptyOutDir: false,
      rollupOptions: {
        input: resolve(__dirname, "index.html"),
        output: {
          entryFileNames: "playbook_builder.js",
          chunkFileNames: "playbook_builder-[name].js",
          inlineDynamicImports: true,
          assetFileNames: (assetInfo) => {
            if (assetInfo.name?.endsWith(".css")) return "playbook_builder.css";
            return "assets/[name][extname]";
          },
        },
      },
    },
  };
});
