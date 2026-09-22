import json

from legal_verify.cli import load_generated
from legal_verify.generate import LegalAnswer


def test_load_generated_reads_answer_and_claims_from_json(tmp_path):
    path = tmp_path / "answer.json"
    path.write_text(
        json.dumps(
            {
                "answer": "2년으로 봅니다.",
                "claims": [{"text": "기간을 정하지 않으면 2년으로 본다.", "law": "주택임대차보호법", "article": "제4조 제1항"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    result = load_generated(path)
    assert isinstance(result, LegalAnswer)
    assert result.claims[0].law == "주택임대차보호법"
