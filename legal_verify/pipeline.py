"""Shared pipeline used by the CLI and the web app: answer -> statutes -> Jev -> report."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from legal_verify.generate import Claim, LegalAnswer, extract_claims, generate_answer
from legal_verify.judge import AnswerJudgment, judge_answer, judge_claim
from legal_verify.sources import ArticleSource, fetch_article_cached
from legal_verify.verdict import ClaimJudgment, Verdict, claim_verdict, fabricated_verdict, overall_grade

StageCallback = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True)
class ClaimReport:
    claim: Claim
    source: ArticleSource | None
    judgment: ClaimJudgment | None
    verdict: Verdict


@dataclass(frozen=True)
class Report:
    question: str
    answer: str
    claims: list[ClaimReport]
    answer_judgment: AnswerJudgment
    grade: str

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.answer,
            "claims": [
                {
                    "claim": c.claim.model_dump(),
                    "source": asdict(c.source) if c.source else None,
                    "judgment": asdict(c.judgment) if c.judgment else None,
                    "verdict": asdict(c.verdict),
                }
                for c in self.claims
            ],
            "answer_judgment": asdict(self.answer_judgment),
            "grade": self.grade,
        }


def build_report(
    *,
    question: str,
    generated: LegalAnswer,
    sources: list[ArticleSource | None],
    claim_judgments: list[ClaimJudgment | None],
    answer_judgment: AnswerJudgment,
) -> Report:
    claims = []
    for claim, source, judgment in zip(generated.claims, sources, claim_judgments, strict=True):
        verdict = claim_verdict(judgment) if judgment is not None else fabricated_verdict()
        claims.append(ClaimReport(claim, source, judgment, verdict))
    grade = overall_grade(
        [c.verdict.label for c in claims],
        answer_judgment.answers_question,
        answer_judgment.definitive_tone,
    )
    return Report(question, generated.answer, claims, answer_judgment, grade)


def _default_jev():
    from typesafe_sdk import TypeSafeClient

    return TypeSafeClient()


def run_pipeline(
    question: str,
    *,
    answer_text: str | None = None,
    generated: LegalAnswer | None = None,
    generate: Callable[[str], LegalAnswer] = generate_answer,
    extract: Callable[[str, str], LegalAnswer] = extract_claims,
    fetch: Callable[[str, str], ArticleSource | None] = fetch_article_cached,
    jev_factory: Callable[[], Any] = _default_jev,
    on_stage: StageCallback | None = None,
) -> Report:
    """Run the full verification. `generated` skips generation; `answer_text` extracts claims from it."""
    emit = on_stage or (lambda name, detail: None)

    if generated is None:
        emit("generate", {"mode": "extract" if answer_text else "generate"})
        generated = extract(question, answer_text) if answer_text else generate(question)
    emit("generated", {"claims": len(generated.claims)})

    emit("fetch", {"total": len(generated.claims)})
    sources = [fetch(c.law, c.article) for c in generated.claims]
    emit("fetched", {"found": sum(s is not None for s in sources), "total": len(sources)})

    emit("judge", {"claims": sum(s is not None for s in sources)})
    with jev_factory() as client:
        judgments = [
            judge_claim(client, question=question, claim=c.text, article=s) if s else None
            for c, s in zip(generated.claims, sources, strict=True)
        ]
        answer_judgment = judge_answer(client, question=question, answer=generated.answer)
    emit("judged", {})

    return build_report(
        question=question,
        generated=generated,
        sources=sources,
        claim_judgments=judgments,
        answer_judgment=answer_judgment,
    )
