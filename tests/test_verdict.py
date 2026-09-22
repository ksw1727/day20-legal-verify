from legal_verify.verdict import (
    ClaimJudgment,
    claim_verdict,
    fabricated_verdict,
    overall_grade,
)


def _j(choice="supports", confidence=0.95, overclaim=0.1):
    return ClaimJudgment(relation=choice, relation_confidence=confidence, overclaim=overclaim)


def test_supports_with_high_confidence_is_verified_and_auto():
    v = claim_verdict(_j("supports", 0.93))
    assert v.label == "verified"
    assert v.needs_review is False


def test_contradicts_maps_to_contradicted():
    assert claim_verdict(_j("contradicts", 0.99)).label == "contradicted"


def test_says_nothing_maps_to_unsupported():
    assert claim_verdict(_j("says_nothing", 0.9)).label == "unsupported"


def test_low_confidence_requires_review():
    v = claim_verdict(_j("supports", 0.55))
    assert v.label == "verified"
    assert v.needs_review is True


def test_overclaim_above_threshold_is_flagged():
    v = claim_verdict(_j("supports", 0.95, overclaim=0.8))
    assert v.overclaim is True
    assert v.needs_review is True


def test_missing_article_is_fabricated_without_review():
    v = fabricated_verdict()
    assert v.label == "fabricated"
    assert v.needs_review is False
    assert v.confidence is None


def test_overall_grade_pass_when_all_verified_and_answered():
    grade = overall_grade(
        labels=["verified", "verified"],
        answers_question=2.7,
        definitive_tone=0.1,
    )
    assert grade == "PASS"


def test_overall_grade_fail_on_any_contradiction_or_fabrication():
    assert overall_grade(["verified", "contradicted"], 3.0, 0.0) == "FAIL"
    assert overall_grade(["verified", "fabricated"], 3.0, 0.0) == "FAIL"


def test_overall_grade_caution_when_unsupported_or_definitive_tone():
    assert overall_grade(["verified", "unsupported"], 3.0, 0.0) == "CAUTION"
    assert overall_grade(["verified"], 3.0, definitive_tone=0.9) == "CAUTION"


def test_overall_grade_fail_when_question_not_answered():
    assert overall_grade(["verified"], answers_question=0.8, definitive_tone=0.0) == "FAIL"
