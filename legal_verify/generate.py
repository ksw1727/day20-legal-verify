"""Ask an LLM a Korean legal question and get back an answer plus the claims it rests on."""

from __future__ import annotations

import os

import openai
from pydantic import BaseModel, Field

DEFAULT_MODEL = "gpt-5.4"

SYSTEM_PROMPT = """당신은 한국 법률 정보를 안내하는 어시스턴트입니다. 질문에 한국어로 답하세요.

답변과 함께, 답변이 의존하는 법률적 주장(claims)을 나열하세요. 각 주장은:
- text: 한 문장으로 된 구체적인 법률 주장
- law: 근거 법령명 (정식 명칭, 예: "근로기준법", "주택임대차보호법", "민법")
- article: 근거 조문 (예: "제60조 제1항", "제839조의2")

주장은 답변에 실제로 쓰인 내용만 적고, 확실히 아는 조문만 인용하세요. 조문 번호를 추측하지 마세요.
법령명은 약칭이 아니라 정식 명칭을 사용하세요."""


class Claim(BaseModel):
    text: str = Field(description="한 문장으로 된 법률 주장")
    law: str = Field(description="근거 법령의 정식 명칭")
    article: str = Field(description="근거 조문, 예: 제60조 제1항")


class LegalAnswer(BaseModel):
    answer: str = Field(description="질문에 대한 한국어 답변")
    claims: list[Claim] = Field(description="답변이 의존하는 법률 주장과 근거 조문")


def _default_client() -> openai.OpenAI:
    # Accept GPT_API_KEY as an alias for OPENAI_API_KEY.
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("GPT_API_KEY")
    return openai.OpenAI(api_key=api_key)


def generate_answer(question: str, *, client=None, model: str | None = None) -> LegalAnswer:
    client = client or _default_client()
    model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    response = client.responses.parse(
        model=model,
        instructions=SYSTEM_PROMPT,
        input=question,
        text_format=LegalAnswer,
    )
    for item in response.output:
        if getattr(item, "type", None) == "message":
            for part in item.content:
                if getattr(part, "type", None) == "refusal":
                    raise RuntimeError(f"Model refused to answer: {part.refusal}")
    if response.output_parsed is None:
        raise RuntimeError("No structured output returned from the model")
    return response.output_parsed


EXTRACT_PROMPT = """당신은 법률 답변 검토 보조원입니다. 사용자가 다른 AI에게 한 질문(question)과 그 AI의 답변(answer)이 주어집니다.

답변을 새로 쓰지 말고, 답변 안에 들어 있는 법률적 주장(claims)만 추출하세요. 각 주장은:
- text: 답변에 실제로 나온 내용을 한 문장으로 옮긴 구체적인 법률 주장
- law: 그 주장이 근거로 삼는 법령명 (정식 명칭). 답변에 명시되어 있으면 그대로, 없으면 해당 주장이 근거해야 할 법령
- article: 근거 조문 (예: "제60조 제1항"). 답변에 명시되어 있으면 그대로, 없으면 해당 주장을 규정하는 조문

답변에 없는 내용을 추가하지 마세요. answer 필드에는 원문을 그대로 넣으세요."""


def extract_claims(question: str, answer_text: str, *, client=None, model: str | None = None) -> LegalAnswer:
    """Pull claims + citations out of an existing answer. The answer text itself is kept verbatim."""
    client = client or _default_client()
    model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    response = client.responses.parse(
        model=model,
        instructions=EXTRACT_PROMPT,
        input=f"[question]\n{question}\n\n[answer]\n{answer_text}",
        text_format=LegalAnswer,
    )
    for item in response.output:
        if getattr(item, "type", None) == "message":
            for part in item.content:
                if getattr(part, "type", None) == "refusal":
                    raise RuntimeError(f"Model refused: {part.refusal}")
    if response.output_parsed is None:
        raise RuntimeError("No structured output returned from the model")
    return LegalAnswer(answer=answer_text, claims=response.output_parsed.claims)
