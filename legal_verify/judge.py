"""Jev question definitions and the two calls we make: per claim, and once per whole answer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from typesafe_sdk import Choice, Noul, Score

from legal_verify.sources import ArticleSource
from legal_verify.verdict import ClaimJudgment


class SystemOneClient(Protocol):
    def system_one(self, state, questions, **kwargs): ...


CLAIM_QUESTIONS = {
    "relation": Choice(
        instructions=(
            "`article.text`는 한국 법령의 실제 조문이고, `claim`은 AI가 그 조문을 근거로 제시한 법률 주장이다. "
            "조문이 주장과 어떤 관계인지 판단하라."
        ),
        criteria={
            "supports": "조문이 주장의 내용을 명시하거나 논리적으로 뒷받침한다",
            "contradicts": "조문이 주장과 반대되는 내용을 정하거나, 주장이 틀렸음을 보여준다",
            "says_nothing": "조문이 주장이 말하는 사항을 다루지 않는다 (다른 주제, 다른 요건)",
        },
    ),
    "overclaim": Noul(
        instructions=(
            "`claim`이 `article.text`에 있는 요건, 예외, 단서, 기간, 대통령령 위임 등의 조건을 빼고 "
            "조문보다 더 넓거나 더 확정적으로 말하는가?"
        ),
        criteria={
            "true": "조문에는 조건이나 예외가 있는데 주장은 그것을 생략하고 일반화하거나 단정한다",
            "false": "주장이 조문의 범위와 조건을 그대로 반영하거나, 조문보다 더 좁게 말한다",
        },
    ),
}

ANSWER_QUESTIONS = {
    "answers_question": Score(
        instructions="`answer`가 `question`에 실제로 답했는지 평가하라.",
        criteria=[
            "질문과 무관한 내용이거나, 답변을 회피한다",
            "관련 법률을 언급하지만 질문자가 알고 싶은 결론을 말하지 않는다",
            "질문에 결론을 제시하지만 핵심 조건이나 질문의 일부를 빠뜨린다",
            "질문의 모든 부분에 결론과 근거를 갖춰 답한다",
        ],
    ),
    "definitive_tone": Noul(
        instructions=(
            "`answer`가 사안의 구체적 사실관계에 따라 결론이 달라질 수 있음이나 전문가 상담 필요성을 "
            "전혀 밝히지 않고, 확정적인 법률 조언처럼 단정적으로 말하는가?"
        ),
        criteria={
            "true": "결론을 단정하고, 사실관계에 따른 차이나 전문가 확인 필요성을 언급하지 않는다",
            "false": "일반적인 설명임을 밝히거나, 상황에 따라 다를 수 있음 또는 전문가 상담을 언급한다",
        },
    ),
}


@dataclass(frozen=True)
class AnswerJudgment:
    answers_question: float  # 0-3 weighted score
    definitive_tone: float  # probability of yes


def judge_claim(client: SystemOneClient, *, question: str, claim: str, article: ArticleSource) -> ClaimJudgment:
    state = {
        "question": question,
        "claim": claim,
        "article": {
            "law": article.law,
            "article_no": article.article,
            "version_date": article.version_date,
            "text": article.text,
        },
    }
    response = client.system_one(state, CLAIM_QUESTIONS)
    relation = response.choices["relation"]
    return ClaimJudgment(
        relation=relation.choice,
        relation_confidence=relation.confidence,
        overclaim=response.nouls["overclaim"].noul,
    )


def judge_answer(client: SystemOneClient, *, question: str, answer: str) -> AnswerJudgment:
    response = client.system_one({"question": question, "answer": answer}, ANSWER_QUESTIONS)
    return AnswerJudgment(
        answers_question=response.scores["answers_question"].score,
        definitive_tone=response.nouls["definitive_tone"].noul,
    )
