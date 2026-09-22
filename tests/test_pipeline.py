from types import SimpleNamespace

from legal_verify.generate import Claim, LegalAnswer
from legal_verify.pipeline import Report, run_pipeline
from legal_verify.sources import ArticleSource


class FakeJev:
    def __init__(self):
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def system_one(self, state, questions, **kwargs):
        self.calls += 1
        if "claim" in state:
            return SimpleNamespace(
                choices={"relation": SimpleNamespace(choice="supports", confidence=0.95, probabilities={})},
                nouls={"overclaim": SimpleNamespace(noul=0.1)},
                scores={},
            )
        return SimpleNamespace(
            choices={},
            nouls={"definitive_tone": SimpleNamespace(noul=0.1)},
            scores={"answers_question": SimpleNamespace(score=2.8, confidence=0.8, probabilities={})},
        )


def _article(law, art):
    return ArticleSource(law, art, "법률", f"##### {art}\n본문", "2025-10-01", "2026-01-02", "https://law", "kr/x.md")


def _fetch(law, article):
    return None if article == "제999조" else _article(law, article)


def _generated():
    return LegalAnswer(
        answer="2년으로 봅니다.",
        claims=[
            Claim(text="2년으로 본다.", law="주택임대차보호법", article="제4조"),
            Claim(text="없는 조문", law="주택임대차보호법", article="제999조"),
        ],
    )


def test_run_pipeline_generates_when_no_answer_text_and_reports_stages():
    stages = []
    jev = FakeJev()
    report = run_pipeline(
        "임대차 기간?",
        generate=lambda q: _generated(),
        extract=lambda q, a: (_ for _ in ()).throw(AssertionError("extract must not be called")),
        fetch=_fetch,
        jev_factory=lambda: jev,
        on_stage=lambda name, detail: stages.append((name, detail)),
    )
    assert isinstance(report, Report)
    assert [c.verdict.label for c in report.claims] == ["verified", "fabricated"]
    assert report.grade == "FAIL"
    assert [s[0] for s in stages] == ["generate", "generated", "fetch", "fetched", "judge", "judged"]
    assert stages[1][1] == {"claims": 2}
    assert stages[3][1] == {"found": 1, "total": 2}
    assert jev.calls == 2  # one claim with a source + one whole-answer call


def test_run_pipeline_extracts_when_answer_text_given_and_keeps_original_answer():
    captured = {}

    def extract(question, answer_text):
        captured["args"] = (question, answer_text)
        return LegalAnswer(answer=answer_text, claims=_generated().claims[:1])

    report = run_pipeline(
        "임대차 기간?",
        answer_text="다른 AI의 답변 원문",
        generate=lambda q: (_ for _ in ()).throw(AssertionError("generate must not be called")),
        extract=extract,
        fetch=_fetch,
        jev_factory=FakeJev,
    )
    assert captured["args"] == ("임대차 기간?", "다른 AI의 답변 원문")
    assert report.answer == "다른 AI의 답변 원문"
    assert report.grade == "PASS"
