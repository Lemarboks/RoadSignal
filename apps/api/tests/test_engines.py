from datetime import datetime, timedelta, timezone
from app.risk.engine import RiskIncident, recency_decay, distance_decay, segment_score, route_score
from app.incidents.confidence import ConfidenceEvidence, calculate_confidence

def test_decay_is_deterministic_and_monotonic():
    now=datetime.now(timezone.utc)
    assert recency_decay(now-timedelta(hours=1),now) > recency_decay(now-timedelta(hours=8),now)
    assert distance_decay(.1) > distance_decay(5)
def test_high_severity_nearby_incident_reduces_score():
    now=datetime.now(timezone.utc); baseline={"crime":5}
    clean=segment_score((-33.94,18.45),[],baseline)[0]
    risky=segment_score((-33.94,18.45),[RiskIncident("crime",5,.9,now,-33.94,18.45)],baseline)[0]
    assert risky < clean
def test_route_score_considers_worst_segment():
    assert route_score([90,90,40],.8) < route_score([75,75,75],.8)
def test_confirmations_raise_confidence_and_disputes_lower_it():
    base=ConfidenceEvidence(reporter_trust=.5,account_age_days=100)
    confirmed=calculate_confidence(ConfidenceEvidence(**{**base.__dict__,"confirmations":2}))[0]
    disputed=calculate_confidence(ConfidenceEvidence(**{**base.__dict__,"disputes":2}))[0]
    assert confirmed > calculate_confidence(base)[0] > disputed
