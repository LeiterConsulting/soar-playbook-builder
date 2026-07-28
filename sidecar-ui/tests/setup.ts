import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
  if (typeof window.localStorage?.clear === "function") {
    window.localStorage.clear();
  }
});
