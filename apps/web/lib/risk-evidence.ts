export type RiskEvidence = {
  method: {
    id: string;
    kind: "deterministic_baseline";
    trained_model: false;
    explainable: true;
    version: string;
  };
  evaluation: {
    dataset_id: string;
    dataset_version: string;
    synthetic: true;
    rows: number;
    test_rows: number;
    brier: number;
    auc: number | null;
    expected_calibration_error: number;
    license: string;
    sha256_verified: boolean;
  };
  training_gate: {
    eligible: boolean;
    minimum_rows: number;
    blockers: string[];
    artifact_emitted: boolean;
  };
  claims: {
    status: "evaluation_only";
    summary: string;
    disclaimer: string;
  };
};

export const packagedRiskEvidence: RiskEvidence = {
  method: {
    id: "transparent_weighted_risk_v1",
    kind: "deterministic_baseline",
    trained_model: false,
    explainable: true,
    version: "1.0.0",
  },
  evaluation: {
    dataset_id: "saferoute-demo-risk-events",
    dataset_version: "1.0.0",
    synthetic: true,
    rows: 40,
    test_rows: 8,
    brier: 0.189994,
    auc: 1,
    expected_calibration_error: 0.346187,
    license: "CC0-1.0",
    sha256_verified: true,
  },
  training_gate: {
    eligible: false,
    minimum_rows: 1000,
    blockers: [
      "dataset is synthetic demonstration data",
      "license manifest does not permit training",
      "fewer than 1000 validated rows",
    ],
    artifact_emitted: false,
  },
  claims: {
    status: "evaluation_only",
    summary:
      "The transparent baseline is reproducibly evaluated on synthetic scenarios. These metrics do not establish real-world safety effectiveness.",
    disclaimer: "Risk scores are decision-support estimates and do not guarantee safety.",
  },
};
