"""Clean one raw question string, or reject it.

Sources are messy: leading numbering, Markdown links/emphasis, inline code
fences, trailing colons, answer text glued on. ``normalize`` returns a
canonical question string, or ``None`` if the line isn't a usable question.
"""
from __future__ import annotations

import re

_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")          # [text](url) -> text
_LEAD_NUMBER = re.compile(r"^\s*(?:Q(?:uestion)?\s*)?\d+\s*[.):\-]\s*", re.I)
_LEAD_QMARK = re.compile(r"^\s*Q\s*[.:\-]\s*", re.I)
_EMPHASIS = re.compile(r"[*_`]{1,3}")
_WS = re.compile(r"\s+")
_HTML = re.compile(r"<[^>]+>")

# Lines that look like a heading/section, boilerplate, or an answer rather
# than a question.
_REJECT_SUBSTR = (
    "table of contents", "contributing", "license", "acknowledg",
    "star this repo", "buy me a coffee", "click here", "read more",
    "answer:", "explanation:", "example:", "output:", "http://", "https://",
)
_MIN_LEN = 10
_MAX_LEN = 320
_MIN_WORDS = 3


def normalize(raw: str) -> str | None:
    q = raw.strip()
    if not q:
        return None

    q = _HTML.sub(" ", q)
    q = _MD_LINK.sub(r"\1", q)
    q = _EMPHASIS.sub("", q)
    q = _LEAD_NUMBER.sub("", q)
    q = _LEAD_QMARK.sub("", q)
    q = q.strip(" \t-–—:•*")
    q = _WS.sub(" ", q).strip()

    # If an answer got glued on after the question, keep only up to the "?".
    if "?" in q:
        q = q[: q.index("?") + 1]

    low = q.lower()
    if len(q) < _MIN_LEN or len(q) > _MAX_LEN:
        return None
    if len(q.split()) < _MIN_WORDS:
        return None
    if any(s in low for s in _REJECT_SUBSTR):
        return None
    if q.startswith(("#", ">", "|", "!", "[")):
        return None
    # Must read like a question: end with '?' or open with an interrogative/imperative.
    starters = (
        "what", "why", "how", "when", "where", "which", "who", "whom", "whose",
        "is", "are", "can", "could", "would", "should", "do", "does", "did",
        "explain", "describe", "define", "name", "list", "compare", "differ",
        "tell", "give", "write", "implement", "design",
    )
    if not q.endswith("?") and not low.startswith(starters):
        return None

    return q[:1].upper() + q[1:]


def dedupe_key(question: str) -> str:
    """A loose key for exact-after-normalization matching: lowercase, no
    punctuation, collapsed spaces."""
    k = re.sub(r"[^a-z0-9 ]", "", question.lower())
    return _WS.sub(" ", k).strip()
