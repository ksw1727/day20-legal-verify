from types import SimpleNamespace

import pytest

from legal_verify.generate import Claim, LegalAnswer, generate_answer


class FakeResponses:
    def __init__(self, parsed, refusal=None):
        self.parsed = parsed
        self.refusal = refusal
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        content = [SimpleNamespace(type="refusal", refusal=self.refusal)] if self.refusal else []
        return SimpleNamespace(
            output_parsed=self.parsed,
            output=[SimpleNamespace(type="message", content=content)],
        )


def _client(parsed, refusal=None):
    return SimpleNamespace(responses=FakeResponses(parsed, refusal))


def test_generate_answer_returns_parsed_legal_answer_with_claims():
    expected = LegalAnswer(
        answer="기간을 정하지 않은 임대차는 2년으로 봅니다.",
        claims=[Claim(text="기간을 정하지 않은 임대차는 2년으로 본다.", law="주택임대차보호법", article="제4조 제1항")],
    )
    client = _client(expected)

    result = generate_answer("임대차 기간을 정하지 않았으면?", client=client)

    assert result == expected
    kwargs = client.responses.kwargs
    assert kwargs["text_format"] is LegalAnswer
    assert kwargs["input"] == "임대차 기간을 정하지 않았으면?"
    assert "법령명" in kwargs["instructions"]


def test_generate_answer_raises_on_refusal():
    client = _client(None, refusal="I can't help with that.")
    with pytest.raises(RuntimeError, match="refus"):
        generate_answer("질문", client=client)


def test_extract_claims_keeps_answer_verbatim_and_uses_extraction_prompt():
    from legal_verify.generate import extract_claims

    parsed = LegalAnswer(answer="모델이 바꿔 쓴 답변", claims=[Claim(text="t", law="민법", article="제750조")])
    client = _client(parsed)

    result = extract_claims("차를 긁었어요", "원래 답변 그대로", client=client)

    assert result.answer == "원래 답변 그대로"
    assert result.claims == parsed.claims
    kwargs = client.responses.kwargs
    assert kwargs["text_format"] is LegalAnswer
    assert "원래 답변 그대로" in kwargs["input"]
    assert "차를 긁었어요" in kwargs["input"]
    assert "추출" in kwargs["instructions"]
