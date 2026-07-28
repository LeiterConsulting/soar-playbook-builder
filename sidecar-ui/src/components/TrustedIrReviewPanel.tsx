import { useEffect, useState } from "react";
import type { BuilderResponse } from "../types";

interface TrustedIrReviewPanelProps {
  templateId: string;
  isLegacyPythonTemplate?: boolean;
  busy?: boolean;
  onReview: (templateId: string) => Promise<BuilderResponse>;
}

function shortHash(value?: string): string {
  if (!value) return "unavailable";
  return `${value.slice(0, 12)}…${value.slice(-8)}`;
}

export function TrustedIrReviewPanel({
  templateId,
  isLegacyPythonTemplate = false,
  busy = false,
  onReview,
}: TrustedIrReviewPanelProps) {
  const [review, setReview] = useState<BuilderResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setReview(null);
  }, [templateId]);

  const runReview = async () => {
    setLoading(true);
    try {
      setReview(await onReview(templateId));
    } catch {
      setReview({
        status: "error",
        error_code: "TRUSTED_REVIEW_FAILED",
        error: "Trusted review could not be completed.",
        review_only: true,
        import_enabled: false,
      });
    } finally {
      setLoading(false);
    }
  };

  const gaps = review?.gap_report?.gaps ?? [];
  const reportStatus = review?.gap_report?.status;

  return (
    <section className="trusted-ir-review" aria-label="Trusted IR review">
      <div className="trusted-ir-review-head">
        <div>
          <strong>Trusted IR preview</strong>
          <span>Deterministic · review only</span>
        </div>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          disabled={busy || loading || isLegacyPythonTemplate}
          onClick={() => void runReview()}
        >
          {loading ? "Reviewing…" : "Review canonical IR"}
        </button>
      </div>

      {isLegacyPythonTemplate && (
        <p className="trusted-ir-note warn">
          This organization template is legacy Python, not canonical IR. It
          cannot enter the trusted review path.
        </p>
      )}

      {!review && !isLegacyPythonTemplate && (
        <p className="trusted-ir-note">
          Parses the shipped IR, rebinds current capability evidence, runs
          preflight, and compiles preview artifacts. Import stays locked.
        </p>
      )}

      {review?.status === "error" && (
        <div className="trusted-ir-result blocked" role="alert">
          <strong>{review.error_code || "REVIEW_FAILED"}</strong>
          <span>{review.error || "Trusted review failed."}</span>
        </div>
      )}

      {review?.status === "success" && (
        <div className={`trusted-ir-result ${reportStatus || "blocked"}`}>
          <div className="trusted-ir-badges">
            <span>IR valid</span>
            <span>Preflight: {reportStatus || "unknown"}</span>
            <span>Import locked</span>
          </div>
          <p>
            {review.compile_eligible
              ? "Preview compilation passed. Live SOAR qualification and trusted import wiring are still required."
              : `${gaps.length} blocker/warning item${gaps.length === 1 ? "" : "s"} require review.`}
          </p>
          {gaps.length > 0 && (
            <ul className="trusted-ir-gaps">
              {gaps.slice(0, 8).map((gap) => (
                <li key={`${gap.id}:${gap.node || ""}`}>
                  <strong>{gap.id}</strong>
                  {gap.node && <code>{gap.node}</code>}
                  <span>{gap.summary}</span>
                </li>
              ))}
            </ul>
          )}
          <details className="template-detail-fold trusted-ir-provenance">
            <summary>Artifact provenance</summary>
            <dl>
              <div>
                <dt>IR</dt>
                <dd>{shortHash(review.ir_sha256)}</dd>
              </div>
              <div>
                <dt>Review</dt>
                <dd>{shortHash(review.review_id)}</dd>
              </div>
              <div>
                <dt>Python preview</dt>
                <dd>{shortHash(review.artifacts?.python_sha256)}</dd>
              </div>
              <div>
                <dt>Visual preview</dt>
                <dd>{shortHash(review.artifacts?.visual_sha256)}</dd>
              </div>
              <div>
                <dt>Native VPE schema</dt>
                <dd>
                  {review.artifacts?.native_schema_status ||
                    "unverified_without_live_soar"}
                </dd>
              </div>
            </dl>
          </details>
        </div>
      )}
    </section>
  );
}
