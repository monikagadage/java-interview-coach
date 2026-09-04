"""Build questions_db.json from the sources (+ optional LLM expansion).

    python -m qbank.build                # sources -> normalize -> dedupe -> classify
    python -m qbank.build --expand       # also run LLM expansion (needs GROQ_API_KEY)
    python -m qbank.build --expand --per-subtopic 40
    python -m qbank.build --stats        # summarize the current questions_db.json
    python -m qbank.build --refresh      # ignore the download / expansion cache
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from qbank import fetch as _fetch
from qbank.classify import classify
from qbank.dedup import dedupe
from qbank.normalize import normalize
from qbank.sources import CATEGORY_MAP, SOURCES

OUT_PATH = Path(__file__).resolve().parent.parent / "questions_db.json"
CURATED_DIR = Path(__file__).resolve().parent / "curated"


def _collect_curated() -> list[tuple[str, str]]:
    """Hand-authored questions in qbank/curated/<topic>.txt (one per line).

    The file name is the topic, so these skip the keyword classifier. They
    give every topic solid baseline coverage regardless of what the scraped
    sources happen to contain, and stand in as a checked-in sample of what
    `--expand` produces at larger scale.
    """
    out: list[tuple[str, str]] = []
    if not CURATED_DIR.exists():
        return out
    for path in sorted(CURATED_DIR.glob("*.txt")):
        # "<Topic>.txt" or "<Topic>.2.txt" -> topic is the part before the first dot.
        topic = path.name.split(".", 1)[0]
        n = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            q = normalize(line)
            if q:
                out.append((topic, q))
                n += 1
        print(f"  · curated/{path.name}: {n} questions")
    return out


def _route(category_hint: str | None, question: str) -> str | None:
    """Source category hint -> canonical topic; else keyword classifier;
    else None (drop it — an unlabelled question the classifier can't place
    is almost always source noise)."""
    if category_hint:
        mapped = CATEGORY_MAP.get(category_hint.strip().lower())
        if mapped:
            return mapped
    # classify() falls back to "Java Core" for anything unmatched; only trust
    # it here when it actually matched a keyword rule.
    from qbank.classify import _COMPILED

    if any(p.search(question) for _t, pats in _COMPILED for p in pats):
        return classify(question)
    return None


def _collect_from_sources(refresh: bool) -> tuple[list[tuple[str, str]], Counter]:
    labeled: list[tuple[str, str]] = []
    per_source: Counter = Counter()
    for src in SOURCES:
        try:
            text = _fetch.fetch(src.url, refresh=refresh)
        except Exception as exc:
            print(f"  ! {src.name}: fetch failed ({exc}) — skipping", file=sys.stderr)
            continue
        pairs = src.parser(text)
        kept = 0
        for raw, hint in pairs:
            q = normalize(raw)
            if not q:
                continue
            topic = _route(hint, q)
            if topic:
                labeled.append((topic, q))
                kept += 1
        per_source[src.name] = kept
        print(f"  · {src.name}: {len(pairs)} raw → {kept} kept")
    return labeled, per_source


def _expanded(per_subtopic: int, refresh: bool) -> list[tuple[str, str]]:
    import os

    from dotenv import load_dotenv

    load_dotenv()
    if not os.environ.get("GROQ_API_KEY"):
        print("  ! --expand needs GROQ_API_KEY (env or .env) — skipping expansion",
              file=sys.stderr)
        return []
    from langchain_groq import ChatGroq

    from qbank.expand import expand

    llm = ChatGroq(model="llama-3.3-70b-versatile")
    return expand(
        llm,
        per_subtopic=per_subtopic,
        refresh=refresh,
        progress=lambda t, s, msg: print(f"  · {t} / {s}: {msg}"),
    )


def build(expand_llm: bool, per_subtopic: int, refresh: bool) -> dict[str, list[str]]:
    print("Sources:")
    labeled, _ = _collect_from_sources(refresh)

    print("Curated:")
    labeled.extend(_collect_curated())

    if expand_llm:
        print("LLM expansion:")
        labeled.extend(_expanded(per_subtopic, refresh))

    # Dedupe globally (across sources + generated), then bucket by topic.
    by_topic: dict[str, list[str]] = {}
    for topic, q in labeled:
        by_topic.setdefault(topic, []).append(q)

    bank: dict[str, list[str]] = {}
    total = 0
    for topic, qs in sorted(by_topic.items()):
        deduped = sorted(dedupe(qs))
        bank[topic] = deduped
        total += len(deduped)

    print(f"\n{total} unique questions across {len(bank)} topics")
    for topic, qs in bank.items():
        print(f"  {topic:<18} {len(qs)}")
    return bank


def stats() -> None:
    if not OUT_PATH.exists():
        sys.exit(f"{OUT_PATH.name} not found — run `python -m qbank.build` first")
    bank = json.loads(OUT_PATH.read_text())
    total = sum(len(v) for v in bank.values())
    print(f"{OUT_PATH.name}: {total} questions across {len(bank)} topics")
    for topic, qs in sorted(bank.items(), key=lambda kv: -len(kv[1])):
        print(f"  {topic:<18} {len(qs)}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="qbank.build", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--expand", action="store_true", help="also run LLM expansion")
    p.add_argument("--per-subtopic", type=int, default=25,
                   help="questions per (topic, subtopic) prompt (default 25)")
    p.add_argument("--refresh", action="store_true", help="ignore caches")
    p.add_argument("--stats", action="store_true", help="summarize questions_db.json and exit")
    args = p.parse_args(argv)

    if args.stats:
        stats()
        return

    bank = build(args.expand, args.per_subtopic, args.refresh)
    OUT_PATH.write_text(json.dumps(bank, indent=1, ensure_ascii=False))
    print(f"\nwrote {OUT_PATH}")


if __name__ == "__main__":
    main()
