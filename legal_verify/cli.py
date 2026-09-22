"""Pipeline: question -> Claude answer -> statute lookup -> Jev judgments -> report."""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from legal_verify.generate import LegalAnswer
from legal_verify.pipeline import ClaimReport, Report, build_report, run_pipeline  # noqa: F401 (re-exported)

LABEL_KO = {
    "verified": "검증됨",
    "contradicted": "반박됨",
    "unsupported": "근거없음",
    "fabricated": "조문없음",
}
LABEL_STYLE = {
    "verified": "green",
    "contradicted": "red",
    "unsupported": "yellow",
    "fabricated": "red bold",
}
GRADE_STYLE = {"PASS": "green", "CAUTION": "yellow", "FAIL": "red"}


def render_report(report: Report) -> str:
    console = Console(record=True, width=110, file=io.StringIO(), force_terminal=False)
    console.print(Panel(report.question, title="질문"))
    console.print(Panel(report.answer, title="AI 답변"))

    table = Table(title="주장별 검증", show_lines=True)
    table.add_column("#", width=3)
    table.add_column("주장", ratio=3)
    table.add_column("인용 조문", ratio=1)
    table.add_column("판정", width=10)
    table.add_column("신뢰도", width=7)
    table.add_column("과잉단정", width=8)
    table.add_column("처리", width=9)
    for i, c in enumerate(report.claims, 1):
        label = c.verdict.label
        cite = f"{c.claim.law} {c.claim.article}"
        if c.source:
            cite += f"\n[dim]({c.source.version_date} 기준)[/dim]"
        conf = "-" if c.verdict.confidence is None else f"{c.verdict.confidence:.2f}"
        over = "-" if c.judgment is None else f"{c.judgment.overclaim:.2f}" + (" ⚠" if c.verdict.overclaim else "")
        table.add_row(
            str(i),
            c.claim.text,
            cite,
            f"[{LABEL_STYLE[label]}]{LABEL_KO[label]}[/]",
            conf,
            over,
            "[yellow]사람 검토[/]" if c.verdict.needs_review else "자동",
        )
    console.print(table)

    aj = report.answer_judgment
    summary = (
        f"질문 응답도: {aj.answers_question:.2f} / 3.00\n"
        f"확정적 조언 어조 확률: {aj.definitive_tone:.2f}\n"
        f"종합 등급: [{GRADE_STYLE[report.grade]} bold]{report.grade}[/]"
    )
    console.print(Panel(summary, title="답변 전체 평가"))
    return console.export_text()


def load_generated(path: Path) -> LegalAnswer:
    """Load an existing AI answer (answer + claims) instead of generating one."""
    return LegalAnswer.model_validate_json(Path(path).read_text(encoding="utf-8"))


def run(question: str, *, out_dir: Path, generated: LegalAnswer | None = None) -> Report:
    console = Console()
    status = console.status("시작...")
    messages = {
        "generate": lambda d: "GPT가 답변을 생성하는 중..." if d["mode"] == "generate" else "GPT가 주장을 추출하는 중...",
        "generated": lambda d: f"[dim]답변 준비 완료: 주장 {d['claims']}개[/dim]",
        "fetch": lambda d: "legalize로 인용 조문을 조회하는 중...",
        "fetched": lambda d: f"[dim]조문 조회 완료: {d['found']}/{d['total']}개 존재[/dim]",
        "judge": lambda d: "Jev가 주장을 검증하는 중...",
        "judged": lambda d: "[dim]검증 완료[/dim]",
    }

    def on_stage(name, detail):
        text = messages[name](detail)
        if name in ("generate", "fetch", "judge"):
            status.update(text)
        else:
            console.print(text)

    with status:
        report = run_pipeline(question, generated=generated, on_stage=on_stage)
    print(render_report(report))

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"report_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[dim]원본 판단값 저장: {path}[/dim]")
    return report


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="AI 법률 답변을 법령 조문과 Jev로 검증합니다.")
    parser.add_argument("question", nargs="?", help="법률 질문. 생략하면 입력을 받습니다.")
    parser.add_argument("--out", default="reports", help="JSON 리포트 저장 폴더 (기본: reports)")
    parser.add_argument(
        "--from-json",
        metavar="PATH",
        help="답변 생성을 건너뛰고, {answer, claims:[{text,law,article}]} 형식의 기존 AI 답변 JSON을 검증",
    )
    args = parser.parse_args(argv)

    missing = []
    if not os.environ.get("TYPESAFE_API_KEY"):
        missing.append("TYPESAFE_API_KEY")
    if not args.from_json and not (os.environ.get("OPENAI_API_KEY") or os.environ.get("GPT_API_KEY")):
        missing.append("OPENAI_API_KEY (또는 GPT_API_KEY)")
    if missing:
        print(f"환경변수가 없습니다: {', '.join(missing)}. .env.example을 참고해 .env를 만들어 주세요.", file=sys.stderr)
        return 2

    question = args.question or input("법률 질문을 입력하세요: ").strip()
    if not question:
        print("질문이 비어 있습니다.", file=sys.stderr)
        return 2
    generated = load_generated(Path(args.from_json)) if args.from_json else None
    run(question, out_dir=Path(args.out), generated=generated)
    return 0


if __name__ == "__main__":
    sys.exit(main())
