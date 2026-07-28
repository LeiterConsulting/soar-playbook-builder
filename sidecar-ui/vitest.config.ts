import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["tests/**/*.{test,spec}.{ts,tsx}"],
    setupFiles: ["./tests/setup.ts"],
    clearMocks: true,
    restoreMocks: true,
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary"],
      include: [
        "src/components/TrustedIrReviewPanel.tsx",
        "src/components/TemplateLibrary.tsx",
        "src/navigation.ts",
        "src/patterns/catalog.ts",
      ],
    },
  },
});
