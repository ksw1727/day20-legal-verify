import json

from fastapi.testclient import TestClient

from legal_verify.generate import Claim, LegalAnswer
from legal_verify.judge import AnswerJudgment
from legal_verify.pipeline import build_report
from legal_verify.sources import ArticleSource
from legal_verify.verdict import ClaimJudgment
from legal_verify.web import create_app


def _report(question):
    generated = LegalAnswer(answer="2년", claims=[Claim(text="2년으로 본다", law="주택임대차보호법", article="제4조")])
    src = ArticleSource("주택임대차보호법", "제4조", "법률", "본문", "2025-10-01", "2026-01-02", "https://law", "kr/x.md")
    return build_report(
        question=question,
        generated=generated,
        sources=[src],
        claim_judgments=[ClaimJudgment("supports", 0.95, 0.1)],
        answer_judgment=AnswerJudgment(2.8, 0.1),
    )


def _fake_pipeline(question, *, answer_text=None, on_stage=None, **kwargs):
    on_stage("generate", {"mode": "extract" if answer_text else "generate"})
    on_stage("generated", {"claims": 1})
    on_stage("fetch", {"total": 1})
    on_stage("fetched", {"found": 1, "total": 1})
    on_stage("judge", {"claims": 1})
    on_stage("judged", {})
    return _report(question)


def _events(text):
    out = []
    for block in text.strip().split("\n\n"):
        ev = {}
        for line in block.splitlines():
            key, _, value = line.partition(": ")
            ev[key] = value
        out.append((ev["event"], json.loads(ev["data"])))
    return out


def test_index_serves_html_page():
    client = TestClient(create_app(pipeline=_fake_pipeline, save_dir=None))
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "법률" in r.text


def test_verify_streams_stages_then_result(tmp_path):
    client = TestClient(create_app(pipeline=_fake_pipeline, save_dir=tmp_path))
    with client.stream("POST", "/api/verify", json={"question": "임대차 기간?"}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        events = _events("".join(r.iter_text()))

    names = [e[0] for e in events]
    assert names == ["stage", "stage", "stage", "stage", "stage", "stage", "result"]
    assert events[0][1] == {"name": "generate", "mode": "generate"}
    report = events[-1][1]
    assert report["grade"] == "PASS"
    assert report["claims"][0]["verdict"]["label"] == "verified"
    assert report["claims"][0]["source"]["law"] == "주택임대차보호법"
    assert len(list(tmp_path.glob("report_*.json"))) == 1


def test_verify_with_answer_text_runs_extract_mode():
    client = TestClient(create_app(pipeline=_fake_pipeline, save_dir=None))
    with client.stream("POST", "/api/verify", json={"question": "q", "answer_text": "붙인 답변"}) as r:
        events = _events("".join(r.iter_text()))
    assert events[0][1] == {"name": "generate", "mode": "extract"}


def test_verify_reports_pipeline_error_as_event():
    def boom(question, **kwargs):
        raise RuntimeError("Model refused")

    client = TestClient(create_app(pipeline=boom, save_dir=None))
    with client.stream("POST", "/api/verify", json={"question": "q"}) as r:
        events = _events("".join(r.iter_text()))
    assert events == [("error", {"message": "Model refused"})]


def test_verify_rejects_empty_question():
    client = TestClient(create_app(pipeline=_fake_pipeline, save_dir=None))
    r = client.post("/api/verify", json={"question": "   "})
    assert r.status_code == 422


def test_server_config_reads_host_and_port_from_env(monkeypatch):
    from legal_verify.web import server_config

    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    assert server_config() == ("127.0.0.1", 8000)
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "10000")
    assert server_config() == ("0.0.0.0", 10000)
