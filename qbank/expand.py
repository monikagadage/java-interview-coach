"""LLM expansion: ask a model for more questions per (topic, subtopic).

``expand(llm, ...)`` takes any object with ``.invoke(str) -> obj.content``
(so a `ChatGroq`, or a fake in tests). Results are cached per
(topic, subtopic) to ``.cache/expand/`` so an interrupted run resumes and
re-runs are free. Every generated line goes back through ``normalize`` and
is deduped against the existing bank by the caller.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from qbank.normalize import normalize
from qbank.taxonomy import TAXONOMY

_CACHE = Path(__file__).resolve().parent / ".cache" / "expand"

_PROMPT = """You are writing a Java technical-interview question bank.

Topic: {topic}
Subtopic: {subtopic}

Write {n} distinct interview questions on this subtopic, ranging from
junior to senior difficulty. Rules:
- One question per line, no numbering, no answers, no commentary.
- Each must be a self-contained question a human interviewer would actually ask.
- Vary the phrasing and angle; do not just restate the subtopic.
- Plain text only, no markdown.
"""

_LINE = re.compile(r"^\s*(?:\d+[.)]\s*|[-*]\s*)?(.+?)\s*$")


def _parse(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        m = _LINE.match(line)
        if not m:
            continue
        q = normalize(m.group(1))
        if q:
            out.append(q)
    return out


def expand(
    llm,
    *,
    per_subtopic: int = 25,
    topics: list[str] | None = None,
    refresh: bool = False,
    progress=lambda *_: None,
) -> list[tuple[str, str]]:
    """Return ``[(topic, question), ...]`` generated across the taxonomy."""
    _CACHE.mkdir(parents=True, exist_ok=True)
    wanted = topics or list(TAXONOMY)
    results: list[tuple[str, str]] = []

    for topic in wanted:
        for subtopic in TAXONOMY.get(topic, []):
            slug = re.sub(r"[^a-z0-9]+", "-", f"{topic}-{subtopic}".lower()).strip("-")
            cache_file = _CACHE / f"{slug}.json"

            if cache_file.exists() and not refresh:
                questions = json.loads(cache_file.read_text())
            else:
                prompt = _PROMPT.format(topic=topic, subtopic=subtopic, n=per_subtopic)
                try:
                    content = llm.invoke(prompt).content
                    questions = _parse(content)
                except Exception as exc:  # keep going; a flaky call shouldn't abort the run
                    progress(topic, subtopic, f"error: {exc}")
                    questions = []
                cache_file.write_text(json.dumps(questions, indent=1))

            progress(topic, subtopic, f"{len(questions)} questions")
            results.extend((topic, q) for q in questions)

    return results
