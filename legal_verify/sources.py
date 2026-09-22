"""Fetch statute text from the legalize-kr mirror via the `legalize` CLI."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

Runner = Callable[[list[str]], tuple[int, str, str]]

# Some laws are mirrored under a variant category (e.g. 근로기준법 lives in 법률(법률).md
# because the plain 법률.md is the 1997 repeal act). Try in order.
CATEGORIES = ("법률", "법률(법률)")

_ARTICLE_RE = re.compile(r"제?\s*(\d+)\s*조(?:\s*의\s*(\d+))?")


@dataclass(frozen=True)
class ArticleSource:
    law: str
    article: str
    category: str
    text: str
    version_date: str
    effective_date: str
    source_url: str
    path: str


def _jo_id(m: re.Match) -> str:
    jo, ui = m.groups()
    return f"제{jo}조" + (f"의{ui}" if ui else "")


def normalize_article(raw: str) -> str:
    """Reduce '제60조 제1항', '60조', '제839조의2 제2항' to the 조-level id the CLI expects."""
    m = _ARTICLE_RE.search(raw)
    if not m:
        raise ValueError(f"조문 번호를 인식할 수 없습니다: {raw!r}")
    return _jo_id(m)


def split_articles(raw: str) -> list[str]:
    """'제11조, 제60조 제1항' -> ['제11조', '제60조']. Distinct, in citation order."""
    ids = [_jo_id(m) for m in _ARTICLE_RE.finditer(raw)]
    if not ids:
        raise ValueError(f"조문 번호를 인식할 수 없습니다: {raw!r}")
    return list(dict.fromkeys(ids))


def _github_token() -> str | None:
    if token := os.environ.get("GITHUB_TOKEN"):
        return token
    if shutil.which("gh"):
        proc = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    return None


def run_legalize(args: list[str]) -> tuple[int, str, str]:
    env = dict(os.environ)
    if token := _github_token():
        env["GITHUB_TOKEN"] = token
    proc = subprocess.run(["legalize", *args], capture_output=True, text=True, env=env, timeout=120)
    return proc.returncode, proc.stdout, proc.stderr


@lru_cache(maxsize=256)
def _fetch_cached(law: str, article: str) -> ArticleSource | None:
    return fetch_article(law, article, run=run_legalize)


def fetch_article_cached(law: str, article: str) -> ArticleSource | None:
    """Cached variant for the CLI/web path; tests use fetch_article with an injected runner."""
    return _fetch_cached(law, ", ".join(split_articles(article)))


def fetch_article(law: str, article: str, run: Runner = run_legalize) -> ArticleSource | None:
    """Fetch every 조 cited in `article`. Several citations are merged into one source; any miss -> None."""
    ids = split_articles(article)
    parts = [_fetch_one(law, article_id, run) for article_id in ids]
    if any(p is None for p in parts):
        return None
    if len(parts) == 1:
        return parts[0]
    first = parts[0]
    return ArticleSource(
        law=first.law,
        article=", ".join(ids),
        category=first.category,
        text="\n\n".join(p.text for p in parts),
        version_date=first.version_date,
        effective_date=first.effective_date,
        source_url=first.source_url,
        path=first.path,
    )


def _fetch_one(law: str, article_id: str, run: Runner) -> ArticleSource | None:
    for category in CATEGORIES:
        code, out, _err = run(["laws", "article", law, article_id, "--category", category, "--json"])
        if code != 0 or not out.strip():
            continue
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            continue
        if not data.get("content"):
            continue
        return ArticleSource(
            law=data.get("law", law),
            article=article_id,
            category=data.get("category", category),
            text=data["content"],
            version_date=data.get("resolved_version_date", ""),
            effective_date=data.get("시행일자", ""),
            source_url=data.get("출처", ""),
            path=data.get("path", ""),
        )
    return None
