import { describe, expect, it } from "vitest";

import { resolveHandlerBase } from "../src/api";
import { parseHashRoute, routeHref } from "../src/navigation";
import { patternsFromApiPayload } from "../src/patterns/catalog";

describe("catalog trust metadata", () => {
  it("preserves strict organization IR and diagnostics", () => {
    const parsed = patternsFromApiPayload({
      patterns: [
        {
          id: "org-review-note",
          label: "Review Note",
          category: "Organization",
          org: true,
          trusted_ir: true,
          template_kind: "ir",
        },
      ],
      org_template_count: 1,
      org_errors: ["bad entry"],
      org_warnings: ["legacy ignored"],
    });

    expect(parsed.patterns[0]).toMatchObject({
      id: "org-review-note",
      org: true,
      trusted_ir: true,
      template_kind: "ir",
    });
    expect(parsed.orgTemplateCount).toBe(1);
    expect(parsed.orgErrors).toEqual(["bad entry"]);
    expect(parsed.orgWarnings).toEqual(["legacy ignored"]);
  });
});

describe("native hash navigation", () => {
  it("accepts only declared routes", () => {
    expect(parseHashRoute("#/build")).toBe("build");
    expect(parseHashRoute("#/coach?tab=respond")).toBe("coach");
    expect(parseHashRoute("#/unknown")).toBeNull();
    expect(parseHashRoute("javascript:alert(1)")).toBeNull();
    expect(routeHref("help")).toBe("#/help");
  });
});

describe("handler URL boundary", () => {
  it("keeps root-mode asset and API paths same-origin", () => {
    const previous = window.location.href;
    window.history.replaceState({}, "", "/");
    expect(resolveHandlerBase()).toBe("");

    window.history.replaceState(
      {},
      "",
      "/rest/handler/soarplaybookbuilder_fixture/asset/chat",
    );
    expect(resolveHandlerBase()).toBe(
      "/rest/handler/soarplaybookbuilder_fixture/asset",
    );
    window.history.replaceState({}, "", previous);
  });
});
