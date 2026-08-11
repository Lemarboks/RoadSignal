import { describe, expect, it } from "vitest";

import { packagedRiskEvidence } from "./risk-evidence";

describe("risk evidence", () => {
  it("fails closed instead of presenting a synthetic trained model", () => {
    expect(packagedRiskEvidence.method.trained_model).toBe(false);
    expect(packagedRiskEvidence.training_gate.eligible).toBe(false);
    expect(packagedRiskEvidence.training_gate.artifact_emitted).toBe(false);
    expect(packagedRiskEvidence.training_gate.blockers).toContain(
      "dataset is synthetic demonstration data",
    );
  });

  it("labels evaluation metrics as synthetic evidence", () => {
    expect(packagedRiskEvidence.evaluation.synthetic).toBe(true);
    expect(packagedRiskEvidence.evaluation.sha256_verified).toBe(true);
    expect(packagedRiskEvidence.claims.summary).toContain(
      "do not establish real-world safety effectiveness",
    );
  });
});
