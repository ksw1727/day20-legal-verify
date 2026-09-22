"""FastAPI app: serves the single page and streams pipeline progress over Server-Sent Events."""

from __future__ import annotations

import json
import os
import queue
import threading
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from legal_verify.pipeline import Report, run_pipeline
from legal_verify.sources import ArticleSource, fetch_article_cached

STATIC_DIR = Path(__file__).parent / "static"
_DONE = object()


class VerifyRequest(BaseModel):
    question: str = Field(min_length=1)
    answer_text: str | None = None

    @field_validator("question")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be blank")
        return v.strip()

    @field_validator("answer_text")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        return v.strip() if v and v.strip() else None


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _save(report: Report, save_dir: Path) -> Path:
    save_dir.mkdir(parents=True, exist_ok=True)
    path = save_dir / f"report_{datetime.now():%Y%m%d_%H%M%S_%f}.json"
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


HEALTH_STATUTE = ("민법", "제750조")  # a stable article used to prove statute lookup works on this host


def create_app(
    *,
    pipeline: Callable[..., Report] = run_pipeline,
    save_dir: Path | None = Path("reports"),
    fetch: Callable[[str, str], ArticleSource | None] = fetch_article_cached,
) -> FastAPI:
    app = FastAPI(title="법률 AI 답변 검증기")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html", media_type="text/html")

    @app.get("/api/health")
    def health() -> JSONResponse:
        """Checks the legalize subprocess + network path and reports which API keys are configured (never their values)."""
        try:
            src = fetch(*HEALTH_STATUTE)
            error = None
        except Exception as exc:  # subprocess or parsing failure
            src, error = None, str(exc)
        body: dict[str, Any] = {
            "legalize": "ok" if src else "failed",
            "statute": {"law": src.law, "article": src.article, "version_date": src.version_date} if src else None,
            "keys": {
                "typesafe": bool(os.environ.get("TYPESAFE_API_KEY")),
                "openai": bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("GPT_API_KEY")),
            },
        }
        if error:
            body["error"] = error
        return JSONResponse(body, status_code=200 if src else 503)

    @app.post("/api/verify")
    def verify(req: VerifyRequest) -> StreamingResponse:
        events: queue.Queue = queue.Queue()

        def on_stage(name: str, detail: dict[str, Any]) -> None:
            events.put(_sse("stage", {"name": name, **detail}))

        def work() -> None:
            try:
                report = pipeline(req.question, answer_text=req.answer_text, on_stage=on_stage)
                if save_dir is not None:
                    _save(report, save_dir)
                events.put(_sse("result", report.to_dict()))
            except Exception as exc:  # surface any pipeline failure to the page
                events.put(_sse("error", {"message": str(exc)}))
            finally:
                events.put(_DONE)

        threading.Thread(target=work, daemon=True).start()

        def stream() -> Iterator[str]:
            while (item := events.get()) is not _DONE:
                yield item

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    return app


def server_config() -> tuple[str, int]:
    """Bind address from HOST/PORT env (deploy platforms inject PORT); local default is loopback:8000."""
    import os

    return os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", "8000"))


def main() -> None:
    import uvicorn
    from dotenv import load_dotenv

    load_dotenv()
    host, port = server_config()
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
