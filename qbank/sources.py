"""Where seed questions come from, and how to pull questions out of each.

Every source is a public GitHub Markdown file. A parser returns a list of
``(raw_question, category_hint)`` pairs — the hint is the source's own topic
label when it has one (used by ``build.py`` to route the question before
falling back to the keyword classifier), or ``None``. ``normalize`` +
``classify`` + ``dedupe`` happen downstream. See ``SOURCES.md`` for links
and licensing notes.

To add a source: append a ``Source(...)`` here with the right ``parser``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

Parsed = list[tuple[str, str | None]]

# ── parsers ────────────────────────────────────────────────────────────

_TABLE_ROW = re.compile(r"^\|(?P<a>[^|]+)\|(?P<b>[^|]+)\|")
_HEADING_Q = re.compile(r"^#{1,4}\s+(?:Q\s*[.:-]?\s*|Q?\d+\s*[.:)-]\s*)?(?P<q>.+?)\s*#*\s*$")
_HEADING_NUMBERED = re.compile(r"^#{1,3}\s+\d+\s*[.):-]\s+(?P<q>.+?)\s*#*\s*$")
_BULLET_Q = re.compile(r"^\s*[-*+]\s+(?:\[[ xX]\]\s*)?(?P<q>.+)$")
_MD_LINK_ONLY = re.compile(r"^\[(?P<q>[^\]]+)\]\([^)]*\)$")


def parse_markdown_table(text: str) -> Parsed:
    """`| question | category |` rows (the teamlead corpus), keeping the category."""
    out: Parsed = []
    for line in text.splitlines():
        m = _TABLE_ROW.match(line)
        if not m:
            continue
        q = m.group("a").strip()
        cat = m.group("b").strip()
        if not q or set(q) <= {"-", ":", " "} or q.lower() == "question":
            continue
        out.append((q, cat or None))
    return out


def parse_qa_headings(text: str) -> Parsed:
    """`## Q. <question>` heading style (learning-zone)."""
    out: Parsed = []
    for line in text.splitlines():
        if not line.startswith("#"):
            continue
        # Only treat "## Q. ..." / "## Q: ..." as questions here — plain
        # numbered sub-headings in these repos are answer sections.
        if re.match(r"^#{1,4}\s+Q\s*[.:-]", line):
            m = _HEADING_Q.match(line)
            if m:
                out.append((m.group("q").strip(), None))
    return out


def parse_numbered_headings(text: str) -> Parsed:
    """`## 12. <question>` top-level numbered headings (Devinterview)."""
    out: Parsed = []
    for line in text.splitlines():
        m = _HEADING_NUMBERED.match(line)
        if m:
            out.append((m.group("q").strip(), None))
    return out


def parse_toc_link_table(text: str) -> Parsed:
    """`| 12 | [question text](#anchor) |` table-of-contents rows (sudheerj)."""
    out: Parsed = []
    for line in text.splitlines():
        m = _TABLE_ROW.match(line)
        if not m:
            continue
        link = _MD_LINK_ONLY.match(m.group("b").strip())
        if link:
            out.append((link.group("q").strip(), None))
    return out


def parse_bullets(text: str) -> list[str]:
    """`- <question>` bullet lists (only lines that look like questions)."""
    out = []
    for line in text.splitlines():
        m = _BULLET_Q.match(line)
        if m and ("?" in m.group("q") or len(m.group("q").split()) >= 4):
            out.append(m.group("q").strip())
    return out


# ── registry ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Source:
    name: str
    url: str
    parser: Callable[[str], Parsed]
    note: str = ""


# The source's own topic labels, mapped to our canonical topics. Anything a
# source labels but that isn't here (XML, HTML, Git, "No", "General", ...)
# has no reliable topic, so build.py runs the keyword classifier and drops
# it if that finds nothing — those rows are almost all noise.
CATEGORY_MAP: dict[str, str] = {
    "java core": "Java Core",
    "core java": "Java Core",
    "oop": "OOP",
    "object-oriented": "OOP",
    "java collections": "Java Collections",
    "collections": "Java Collections",
    "multithreading": "Multithreading",
    "concurrency": "Multithreading",
    "spring": "Spring",
    "spring boot": "Spring",
    "frameworks": "Spring",
    "hibernate": "Databases",
    "jvm": "JVM",
    "java 8": "Java 8",
    "streams": "Java 8",
    "lambda": "Java 8",
    "databases": "Databases",
    "database": "Databases",
    "sql": "Databases",
    "jdbc": "Databases",
    "patterns": "Patterns",
    "design patterns": "Patterns",
    "testing": "Testing",
    "serialization": "Java Core",
    "exceptions": "Java Core",
    "generics": "Java Core",
}


SOURCES: list[Source] = [
    Source(
        "teamlead/java-interview-questions",
        "https://raw.githubusercontent.com/teamlead/java-interview-questions/main/README.md",
        parse_markdown_table,
        "1,715 questions ranked by frequency across 600 analyzed interviews; the project's original seed.",
    ),
    Source(
        "learning-zone/java-interview-questions",
        "https://raw.githubusercontent.com/learning-zone/java-interview-questions/master/README.md",
        parse_qa_headings,
        "~400 Q&A-style questions across 23 topic sections.",
    ),
    Source(
        "Devinterview-io/java-interview-questions",
        "https://raw.githubusercontent.com/Devinterview-io/java-interview-questions/main/README.md",
        parse_numbered_headings,
        "~100 curated core-Java questions with model answers.",
    ),
    Source(
        "sudheerj/java-interview-questions",
        "https://raw.githubusercontent.com/sudheerj/java-interview-questions/master/README.md",
        parse_toc_link_table,
        "A long-running Java Q&A repo; questions taken from its table of contents.",
    ),
]
