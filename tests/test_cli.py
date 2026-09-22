from legal_verify.cli import ClaimReport, Report, build_report, render_report
from legal_verify.generate import Claim, LegalAnswer
from legal_verify.judge import AnswerJudgment
from legal_verify.sources import ArticleSource
from legal_verify.verdict import ClaimJudgment


def _article():
    return ArticleSource("주택임대차보호법", "제4조", "법률", "본문", "2025-10-01", "2026-01-02", "https://law", "kr/x.md")


def _answer():
    return LegalAnswer(
        answer="2년으로 봅니다.",
        claims=[
            Claim(text="기간을 정하지 않으면 2년으로 본다.", law="주택임대차보호법", article="제4조 제1항"),
            Claim(text="임차인은 3년을 주장할 수 있다.", law="주택임대차보호법", article="제999조"),
        ],
    )


def test_build_report_marks_missing_article_as_fabricated_and_grades_fail():
    report = build_report(
        question="임대차 기간?",
        generated=_answer(),
        sources=[_article(), None],
        claim_judgments=[ClaimJudgment("supports", 0.95, 0.1), None],
        answer_judgment=AnswerJudgment(answers_question=2.8, definitive_tone=0.2),
    )
    assert isinstance(report, Report)
    assert [c.verdict.label for c in report.claims] == ["verified", "fabricated"]
    assert report.grade == "FAIL"
    assert report.claims[0].source is not None
    assert report.claims[1].source is None


def test_render_report_lists_each_claim_with_verdict_and_grade():
    report = build_report(
        question="임대차 기간?",
        generated=_answer(),
        sources=[_article(), None],
        claim_judgments=[ClaimJudgment("supports", 0.55, 0.1), None],
        answer_judgment=AnswerJudgment(answers_question=2.8, definitive_tone=0.2),
    )
    text = render_report(report)
    assert "검증됨" in text
    assert "조문없음" in text
    assert "사람 검토" in text
    assert "FAIL" in text
    assert "제4조" in text


def test_report_to_dict_keeps_raw_probabilities_for_later_repolicy():
    report = build_report(
        question="q",
        generated=_answer(),
        sources=[_article(), None],
        claim_judgments=[ClaimJudgment("supports", 0.95, 0.42), None],
        answer_judgment=AnswerJudgment(answers_question=2.8, definitive_tone=0.2),
    )
    d = report.to_dict()
    assert d["claims"][0]["judgment"]["overclaim"] == 0.42
    assert d["claims"][1]["judgment"] is None
    assert d["answer_judgment"]["answers_question"] == 2.8
    assert d["grade"] == "FAIL"


def test_render_report_does_not_write_to_stdout(capsys):
    report = build_report(
        question="q",
        generated=_answer(),
        sources=[_article(), None],
        claim_judgments=[ClaimJudgment("supports", 0.95, 0.1), None],
        answer_judgment=AnswerJudgment(answers_question=2.8, definitive_tone=0.2),
    )
    text = render_report(report)
    assert "검증됨" in text
    assert capsys.readouterr().out == ""
