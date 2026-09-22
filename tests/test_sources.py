import json

import pytest

from legal_verify.sources import ArticleSource, fetch_article, normalize_article


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("제60조", "제60조"),
        ("60조", "제60조"),
        ("제60조 제1항", "제60조"),
        ("제60조제1항", "제60조"),
        ("제839조의2", "제839조의2"),
        ("제839조의2 제2항", "제839조의2"),
        ("제4조(임대차기간 등)", "제4조"),
    ],
)
def test_normalize_article_keeps_only_jo_level(raw, expected):
    assert normalize_article(raw) == expected


def _ok_payload(category="법률"):
    return json.dumps(
        {
            "law": "주택임대차보호법",
            "category": category,
            "resolved_version_date": "2025-10-01",
            "시행일자": "2026-01-02",
            "출처": "https://www.law.go.kr/법령/주택임대차보호법",
            "path": f"kr/주택임대차보호법/{category}.md",
            "content": "##### 제4조 (임대차기간 등)\n\n**①** 기간을 정하지 아니한 임대차는 2년으로 본다.",
        },
        ensure_ascii=False,
    )


def test_fetch_article_returns_source_from_cli_json():
    calls = []

    def run(args):
        calls.append(args)
        return 0, _ok_payload(), ""

    src = fetch_article("주택임대차보호법", "제4조 제1항", run=run)
    assert isinstance(src, ArticleSource)
    assert src.law == "주택임대차보호법"
    assert src.article == "제4조"
    assert "임대차기간" in src.text
    assert src.version_date == "2025-10-01"
    assert calls[0][:4] == ["laws", "article", "주택임대차보호법", "제4조"]


def test_fetch_article_falls_back_to_alternate_category():
    calls = []

    def run(args):
        calls.append(args)
        if "법률(법률)" in args:
            return 0, _ok_payload("법률(법률)"), ""
        return 1, "", "error: article 제60조 not found in 근로기준법/법률 at 2026-09-22"

    src = fetch_article("근로기준법", "제60조", run=run)
    assert src is not None
    assert src.category == "법률(법률)"
    assert len(calls) == 2


def test_fetch_article_returns_none_when_all_categories_fail():
    def run(args):
        return 1, "", "error: article 제999조 not found"

    assert fetch_article("근로기준법", "제999조", run=run) is None


def test_fetch_article_returns_none_for_unknown_law():
    def run(args):
        return 1, "", "error: law 존재하지않는법 not found"

    assert fetch_article("존재하지않는법", "제1조", run=run) is None


def test_split_articles_handles_multiple_citations():
    from legal_verify.sources import split_articles

    assert split_articles("제11조, 제60조 제1항") == ["제11조", "제60조"]
    assert split_articles("제60조 제1항 및 제7항") == ["제60조"]
    assert split_articles("제839조의2") == ["제839조의2"]


def test_fetch_article_merges_multiple_articles_into_one_source():
    def run(args):
        art = args[3]
        return 0, json.dumps({"law": "근로기준법", "category": "법률", "resolved_version_date": "2026-06-09",
                              "content": f"##### {art}\n{art} 본문", "path": "kr/근로기준법/법률.md"}, ensure_ascii=False), ""

    src = fetch_article("근로기준법", "제11조, 제60조 제1항", run=run)
    assert src is not None
    assert src.article == "제11조, 제60조"
    assert "제11조 본문" in src.text and "제60조 본문" in src.text


def test_fetch_article_with_multiple_citations_returns_none_if_any_missing():
    def run(args):
        if args[3] == "제999조":
            return 1, "", "not found"
        return 0, json.dumps({"law": "근로기준법", "category": "법률", "content": "본문"}, ensure_ascii=False), ""

    assert fetch_article("근로기준법", "제11조, 제999조", run=run) is None
