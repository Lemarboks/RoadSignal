from fastapi.testclient import TestClient

from app.main import app
from app.risk.evidence import risk_evidence

client = TestClient(app)


def test_risk_evidence_exposes_honest_reproducible_baseline_metadata():
    response = client.get("/api/v1/risk/evidence")

    assert response.status_code == 200
    evidence = response.json()
    assert evidence["method"] == {
        "id": "transparent_weighted_risk_v1",
        "kind": "deterministic_baseline",
        "trained_model": False,
        "explainable": True,
        "version": "1.0.0",
    }
    assert evidence["evaluation"]["synthetic"] is True
    assert evidence["evaluation"]["sha256_verified"] is True
    assert evidence["training_gate"]["eligible"] is False
    assert evidence["training_gate"]["artifact_emitted"] is False
    assert "do not establish real-world safety" in evidence["claims"]["summary"]


def test_packaged_evidence_matches_canonical_report():
    evidence = risk_evidence()

    assert evidence["evaluation"]["rows"] == 40
    assert evidence["evaluation"]["test_rows"] == 8
    assert evidence["training_gate"]["blockers"]
