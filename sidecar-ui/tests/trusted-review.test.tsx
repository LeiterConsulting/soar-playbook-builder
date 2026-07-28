import axe from "axe-core";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TrustedIrReviewPanel } from "../src/components/TrustedIrReviewPanel";
import { TemplateLibrary } from "../src/components/TemplateLibrary";
import type { PatternDefinition } from "../src/patterns/catalog";
import type { BuilderResponse } from "../src/types";

const CLEAN_REVIEW: BuilderResponse = {
  status: "success",
  review_only: true,
  import_enabled: false,
  ready_for_import: false,
  import_block_reason: "TRUSTED_IMPORT_DISABLED",
  compile_eligible: true,
  review_id: "a".repeat(64),
  ir_sha256: "b".repeat(64),
  gap_report: { status: "ok", gaps: [] },
  artifacts: {
    python_sha256: "c".repeat(64),
    visual_sha256: "d".repeat(64),
    native_schema_status: "unverified_without_live_soar",
  },
};

async function expectNoStructuralA11yViolations(
  container: HTMLElement,
): Promise<void> {
  const result = await axe.run(container, {
    rules: {
      // jsdom does not calculate layout/color, so contrast is browser-E2E work.
      "color-contrast": { enabled: false },
    },
  });
  expect(result.violations).toEqual([]);
}

describe("TrustedIrReviewPanel", () => {
  it("renders deterministic evidence while keeping import locked", async () => {
    const onReview = vi.fn(async () => CLEAN_REVIEW);
    const { container } = render(
      <TrustedIrReviewPanel templateId="hello" onReview={onReview} />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Review canonical IR" }),
    );

    expect(await screen.findByText("IR valid")).toBeInTheDocument();
    expect(screen.getByText("Preflight: ok")).toBeInTheDocument();
    expect(screen.getByText("Import locked")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /import/i }),
    ).not.toBeInTheDocument();
    expect(onReview).toHaveBeenCalledWith("hello");
    await expectNoStructuralA11yViolations(container);
  });

  it("cannot review a legacy Python organization template", async () => {
    const onReview = vi.fn(async () => CLEAN_REVIEW);
    const { container } = render(
      <TrustedIrReviewPanel
        templateId="org-legacy"
        isLegacyPythonTemplate
        onReview={onReview}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Review canonical IR" }),
    ).toBeDisabled();
    expect(
      screen.getByText(/legacy Python, not canonical IR/i),
    ).toBeInTheDocument();
    expect(onReview).not.toHaveBeenCalled();
    await expectNoStructuralA11yViolations(container);
  });
});

describe("TemplateLibrary trust states", () => {
  const strictOrg: PatternDefinition = {
    id: "org-review-note",
    label: "Organization Review Note",
    description: "Strict organization IR fixture.",
    category: "Organization",
    integrations: [],
    offline: true,
    org: true,
    trusted_ir: true,
    template_kind: "ir",
    tier: "safe",
  };

  it("routes strict organization IR only into review", async () => {
    const onLoad = vi.fn();
    const onValidate = vi.fn();
    const { container } = render(
      <TemplateLibrary
        patterns={[strictOrg]}
        value={strictOrg.id}
        onChange={vi.fn()}
        onLoad={onLoad}
        onValidate={onValidate}
        onTrustedReview={async () => CLEAN_REVIEW}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Review IR below" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "Validate" })).toBeDisabled();
    expect(screen.getByText("Strict IR")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Review canonical IR" }),
    ).toBeEnabled();
    expect(onLoad).not.toHaveBeenCalled();
    expect(onValidate).not.toHaveBeenCalled();
    await expectNoStructuralA11yViolations(container);
  });

  it("labels legacy Python as untrusted and blocks trusted review", () => {
    const legacyOrg: PatternDefinition = {
      ...strictOrg,
      id: "org-legacy-note",
      label: "Legacy Note",
      trusted_ir: false,
      template_kind: "legacy_python",
    };
    render(
      <TemplateLibrary
        patterns={[legacyOrg]}
        value={legacyOrg.id}
        onChange={vi.fn()}
        onLoad={vi.fn()}
        onValidate={vi.fn()}
        onTrustedReview={async () => CLEAN_REVIEW}
      />,
    );

    expect(screen.getByText("Legacy Python · untrusted")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Review canonical IR" }),
    ).toBeDisabled();
  });
});
