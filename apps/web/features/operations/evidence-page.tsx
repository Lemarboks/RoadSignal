import type { RiskEvidence } from "../../lib/risk-evidence";

export function EvidencePage({
  evidence,
  source,
}: {
  evidence: RiskEvidence;
  source: "packaged" | "api";
}) {
  return (
    <>
      <section className="heading evidence-heading">
        <div>
          <p className="eyebrow">Reproducible risk governance</p>
          <h1>Risk evidence</h1>
          <p>
            See what the scoring method can prove, what it cannot, and why
            training is blocked.
          </p>
        </div>
        <span className={`evidence-source ${source}`}>
          {source === "api" ? "Verified by API" : "Packaged evidence"}
        </span>
      </section>
      <section
        className="evidence-hero"
        aria-labelledby="evidence-status-title"
      >
        <div className="evidence-verdict">
          <span aria-hidden="true">Baseline 1.0</span>
          <h2 id="evidence-status-title">No trained safety model</h2>
          <p>{evidence.claims.summary}</p>
        </div>
        <dl className="evidence-facts">
          <div>
            <dt>Method</dt>
            <dd>Transparent weighted baseline</dd>
          </div>
          <div>
            <dt>Training gate</dt>
            <dd>Blocked</dd>
          </div>
          <div>
            <dt>Artifact emitted</dt>
            <dd>No</dd>
          </div>
          <div>
            <dt>Hash verified</dt>
            <dd>{evidence.evaluation.sha256_verified ? "Yes" : "No"}</dd>
          </div>
        </dl>
      </section>
      <div className="evidence-layout">
        <section
          className="evidence-section"
          aria-labelledby="evaluation-title"
        >
          <div className="evidence-section-heading">
            <div>
              <p className="eyebrow">Synthetic evaluation only</p>
              <h2 id="evaluation-title">Baseline evaluation</h2>
            </div>
            <span>{evidence.evaluation.license}</span>
          </div>
          <dl className="evidence-metrics">
            <div>
              <dt>Validated rows</dt>
              <dd>{evidence.evaluation.rows}</dd>
            </div>
            <div>
              <dt>Held-out rows</dt>
              <dd>{evidence.evaluation.test_rows}</dd>
            </div>
            <div>
              <dt>Brier score</dt>
              <dd>{evidence.evaluation.brier.toFixed(3)}</dd>
            </div>
            <div>
              <dt>Calibration error</dt>
              <dd>
                {evidence.evaluation.expected_calibration_error.toFixed(3)}
              </dd>
            </div>
          </dl>
          <p className="evidence-note">
            AUC {evidence.evaluation.auc?.toFixed(3) ?? "not available"} is
            shown for pipeline verification only. The small synthetic holdout
            cannot establish real-world accuracy.
          </p>
        </section>
        <section className="evidence-section gate" aria-labelledby="gate-title">
          <p className="eyebrow">Fail-closed decision</p>
          <h2 id="gate-title">Why training stops here</h2>
          <ul className="gate-list">
            {evidence.training_gate.blockers.map((blocker) => (
              <li key={blocker}>{blocker}</li>
            ))}
          </ul>
          <p>
            A future candidate needs licensed outcome data, temporal and
            geographic holdouts, calibration, subgroup review, monitoring, and
            rollback evidence.
          </p>
        </section>
      </div>
      <section className="evidence-controls" aria-labelledby="controls-title">
        <div>
          <p className="eyebrow">Engineering controls</p>
          <h2 id="controls-title">Evidence before algorithms</h2>
        </div>
        <ul>
          <li>
            <strong>Provenance</strong>
            <span>
              Source, licence, permitted use, coverage, and SHA-256 digest
            </span>
          </li>
          <li>
            <strong>Leakage</strong>
            <span>
              Prediction-time feature contract and chronological partitions
            </span>
          </li>
          <li>
            <strong>Quality</strong>
            <span>
              Schema, coordinates, missingness, duplicates, ranges, and class
              checks
            </span>
          </li>
          <li>
            <strong>Evaluation</strong>
            <span>Calibration and geographic plus day/night subgroups</span>
          </li>
        </ul>
      </section>
      <p className="evidence-disclaimer">{evidence.claims.disclaimer}</p>
    </>
  );
}
