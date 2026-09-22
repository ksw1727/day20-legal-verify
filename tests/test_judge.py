from types import SimpleNamespace

from legal_verify.judge import ANSWER_QUESTIONS, CLAIM_QUESTIONS, judge_answer, judge_claim
from legal_verify.sources import ArticleSource
from legal_verify.verdict import ClaimJudgment


class FakeClient:
    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def system_one(self, state, questions, **kwargs):
        self.calls.append((state, questions))
        return SimpleNamespace(
            choices={k: v for k, v in self.answers.items() if hasattr(v, "choice")},
            nouls={k: v for k, v in self.answers.items() if hasattr(v, "noul")},
            scores={k: v for k, v in self.answers.items() if hasattr(v, "score")},
        )


def _article():
    return ArticleSource(
        law="주택임대차보호법",
        article="제4조",
        category="법률",
        text="##### 제4조\n기간을 정하지 아니한 임대차는 2년으로 본다.",
        version_date="2025-10-01",
        effective_date="2026-01-02",
        source_url="https://www.law.go.kr/법령/주택임대차보호법",
        path="kr/주택임대차보호법/법률.md",
    )


def test_claim_questions_cover_relation_and_overclaim():
    assert set(CLAIM_QUESTIONS) == {"relation", "overclaim"}
    assert set(CLAIM_QUESTIONS["relation"].criteria) == {"supports", "contradicts", "says_nothing"}


def test_answer_questions_cover_answered_and_tone():
    assert set(ANSWER_QUESTIONS) == {"answers_question", "definitive_tone"}
    assert len(ANSWER_QUESTIONS["answers_question"].criteria) == 4


def test_judge_claim_sends_claim_and_article_text_as_state():
    client = FakeClient(
        {
            "relation": SimpleNamespace(choice="supports", confidence=0.93, probabilities={}),
            "overclaim": SimpleNamespace(noul=0.12),
        }
    )
    result = judge_claim(client, question="임대차 기간은?", claim="기간을 정하지 않으면 2년이다.", article=_article())

    assert result == ClaimJudgment(relation="supports", relation_confidence=0.93, overclaim=0.12)
    state, questions = client.calls[0]
    assert state["claim"] == "기간을 정하지 않으면 2년이다."
    assert state["article"]["text"].startswith("##### 제4조")
    assert state["article"]["law"] == "주택임대차보호법"
    assert questions is CLAIM_QUESTIONS


def test_judge_answer_returns_score_and_tone_probability():
    client = FakeClient(
        {
            "answers_question": SimpleNamespace(score=2.6, confidence=0.7, probabilities={}),
            "definitive_tone": SimpleNamespace(noul=0.8),
        }
    )
    result = judge_answer(client, question="임대차 기간은?", answer="2년입니다.")
    assert result.answers_question == 2.6
    assert result.definitive_tone == 0.8
    state, questions = client.calls[0]
    assert state == {"question": "임대차 기간은?", "answer": "2년입니다."}
    assert questions is ANSWER_QUESTIONS
