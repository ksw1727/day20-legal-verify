"""Turn Jev's raw probabilities into verdicts. Pure functions; policy lives here, not in the model."""

from __future__ import annotations

from dataclasses import dataclass

AUTO_ACCEPT = 0.8  # Choice confidence below this goes to human review
OVERCLAIM_THRESHOLD = 0.5  # Noul probability above this flags the claim as overstated
ANSWERED_MIN = 1.5  # Score (0-3) below this means the question was not really answered
DEFINITIVE_TONE_THRESHOLD = 0.5

RELATION_TO_LABEL = {
    "supports": "verified",
    "contradicts": "contradicted",
    "says_nothing": "unsupported",
}


@dataclass(frozen=True)
class ClaimJudgment:
    relation: str
    relation_confidence: float
    overclaim: float


@dataclass(frozen=True)
class Verdict:
    label: str
    confidence: float | None
    needs_review: bool
    overclaim: bool = False


def claim_verdict(j: ClaimJudgment) -> Verdict:
    label = RELATION_TO_LABEL[j.relation]
    overclaim = j.overclaim > OVERCLAIM_THRESHOLD
    needs_review = j.relation_confidence < AUTO_ACCEPT or overclaim
    return Verdict(label, j.relation_confidence, needs_review, overclaim)


def fabricated_verdict() -> Verdict:
    return Verdict("fabricated", None, False)


def overall_grade(labels: list[str], answers_question: float, definitive_tone: float) -> str:
    if answers_question < ANSWERED_MIN:
        return "FAIL"
    if any(label in ("contradicted", "fabricated") for label in labels):
        return "FAIL"
    if "unsupported" in labels or definitive_tone > DEFINITIVE_TONE_THRESHOLD:
        return "CAUTION"
    return "PASS"
