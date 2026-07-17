from dataclasses import dataclass
from math import exp

@dataclass(frozen=True)
class ConfidenceEvidence:
    reporter_trust: float = .25
    gps_distance_km: float = 0
    account_age_days: int = 0
    previous_accuracy: float = .5
    confirmations: int = 0
    disputes: int = 0
    has_evidence: bool = False
    independent_source_match: bool = False
    age_hours: float = 0
    duplicate_probability: float = 0
    reports_last_hour: int = 0

def abuse_flags(e: ConfidenceEvidence) -> list[str]:
    flags = []
    if e.duplicate_probability > .7: flags.append("probable_duplicate")
    if e.gps_distance_km > 10: flags.append("reporter_far_from_event")
    if e.reports_last_hour > 8: flags.append("excessive_reporting_frequency")
    return flags

def calculate_confidence(e: ConfidenceEvidence) -> tuple[float, list[str]]:
    score = .10 + .22 * e.reporter_trust + .08 * min(e.account_age_days / 365, 1) + .12 * e.previous_accuracy
    score += .14 * min(e.confirmations, 3) - .13 * min(e.disputes, 3)
    score += .10 if e.has_evidence else 0
    score += .24 if e.independent_source_match else 0
    score *= exp(-max(e.age_hours, 0) / 168)
    score *= 1 - .45 * max(0, min(1, e.duplicate_probability))
    if e.gps_distance_km > 2: score *= max(.35, 1 - e.gps_distance_km / 25)
    return round(max(.05, min(.99, score)), 3), abuse_flags(e)
