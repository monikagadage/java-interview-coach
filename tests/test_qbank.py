"""Tests for the qbank/ build pipeline. Hermetic — no network, no API key.

The one build-integration test monkeypatches ``qbank.fetch.fetch`` with
small fixture Markdown so the whole scrape → normalize → classify → dedupe
path runs offline.
"""
from __future__ import annotations

import pytest

from qbank import build, sources
from qbank.classify import classify
from qbank.dedup import dedupe
from qbank.normalize import dedupe_key, normalize


# ── normalize ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1. What is encapsulation?", "What is encapsulation?"),
        ("**Q. Explain the JVM**", "Explain the JVM"),
        ("Q: How does a HashMap work", "How does a HashMap work"),
        ("  What is `volatile`?  ", "What is volatile?"),
        ("What is DI? Answer: it is inversion of control", "What is DI?"),
        ("[What is a bean?](#bean)", "What is a bean?"),
    ],
)
def test_normalize_cleans(raw, expected):
    assert normalize(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "", "Java", "## Heading", "> a quote", "See the table of contents",
        "http://example.com", "answer: because it is immutable", "ok",
    ],
)
def test_normalize_rejects_non_questions(raw):
    assert normalize(raw) is None


def test_normalize_keeps_imperative_prompts():
    assert normalize("Explain how garbage collection works") is not None
    assert normalize("Compare ArrayList and LinkedList") is not None


def test_dedupe_key_is_punctuation_insensitive():
    assert dedupe_key("What is a Bean?") == dedupe_key("what is a bean")


# ── classify ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("q", "topic"),
    [
        ("How does volatile differ from synchronized?", "Multithreading"),
        ("What is a Spring bean scope?", "Spring"),
        ("Explain garbage collection in the JVM", "JVM"),
        ("What does flatMap do on a Stream?", "Java 8"),
        ("How does a HashMap resize?", "Java Collections"),
        ("What is an ACID transaction?", "Databases"),
        ("What is a Mockito spy?", "Testing"),
        ("What is the Singleton design pattern?", "Patterns"),
        ("What is method overriding?", "OOP"),
    ],
)
def test_classify_routes_by_keyword(q, topic):
    assert classify(q) == topic


def test_classify_falls_back_to_java_core():
    assert classify("What year was Java released?") == "Java Core"


# ── dedupe ─────────────────────────────────────────────────────────────

def test_dedupe_drops_exact_after_normalization():
    out = dedupe(["What is a bean?", "what is a bean", "What is a BEAN?"])
    assert len(out) == 1


def test_dedupe_drops_near_duplicates():
    out = dedupe([
        "What is the difference between an interface and an abstract class?",
        "Difference between abstract class and interface in Java",
        "What is polymorphism?",
    ])
    assert len(out) == 2
    assert any("polymorphism" in q for q in out)


def test_dedupe_keeps_distinct_questions():
    qs = [
        "What is a HashMap?", "What is a TreeMap?", "What is a LinkedHashMap?",
        "How does a HashMap handle collisions?",
    ]
    assert len(dedupe(qs)) == 4


# ── source parsers ─────────────────────────────────────────────────────

def test_parse_markdown_table_keeps_category():
    md = (
        "| Question | Category |\n"
        "|---|---|\n"
        "| What is OOP? | OOP |\n"
        "| Explain the JVM memory model | JVM |\n"
    )
    parsed = sources.parse_markdown_table(md)
    assert parsed == [("What is OOP?", "OOP"), ("Explain the JVM memory model", "JVM")]


def test_parse_qa_headings_only_takes_question_headings():
    md = "## Q. What is a stream?\n### Some answer section\n## Q: Define a lambda\n"
    assert sources.parse_qa_headings(md) == [
        ("What is a stream?", None),
        ("Define a lambda", None),
    ]


def test_parse_numbered_headings():
    md = "## 1. What is Java?\n#### 2. sub point\n## 2. Why is Java portable?\n"
    assert sources.parse_numbered_headings(md) == [
        ("What is Java?", None),
        ("Why is Java portable?", None),
    ]


def test_parse_toc_link_table():
    md = "| 1 | [What is the JVM?](#jvm) |\n| 2 | [What is a JAR?](#jar) |\n"
    assert sources.parse_toc_link_table(md) == [
        ("What is the JVM?", None),
        ("What is a JAR?", None),
    ]


# ── routing ────────────────────────────────────────────────────────────

def test_route_uses_category_hint_first():
    assert build._route("SQL", "some vague text") == "Databases"


def test_route_falls_back_to_classifier():
    assert build._route(None, "How does volatile work?") == "Multithreading"


def test_route_drops_unclassifiable_unlabelled_noise():
    assert build._route(None, "In what university did you study") is None
    assert build._route("No", "As if organized the Delete method") is None


# ── expand (fake LLM) ──────────────────────────────────────────────────

class _FakeLLM:
    def __init__(self):
        self.calls = 0

    def invoke(self, _prompt):
        self.calls += 1
        text = "1. What is a thread?\n- How does a lock work?\nExplain wait and notify\n"
        return type("R", (), {"content": text})()


def test_expand_generates_and_caches(tmp_path, monkeypatch):
    from qbank import expand

    monkeypatch.setattr(expand, "_CACHE", tmp_path / "expand")
    llm = _FakeLLM()
    got = expand.expand(llm, topics=["Multithreading"], per_subtopic=3)
    assert got and all(t == "Multithreading" for t, _q in got)
    first_calls = llm.calls

    # Second run hits the cache — no new LLM calls.
    expand.expand(llm, topics=["Multithreading"], per_subtopic=3)
    assert llm.calls == first_calls


# ── build integration (fixture Markdown, no network) ───────────────────

_FIXTURES = {
    "table": (
        "| Question | Category |\n|---|---|\n"
        "| What is encapsulation? | OOP |\n"
        "| How does a HashMap resize? | Java Collections |\n"
        "| In what university did you study | No |\n"
    ),
    "headings": "## Q. What is the volatile keyword?\n## Q. Difference between wait and sleep?\n",
}


def test_build_end_to_end(monkeypatch, tmp_path):
    fake_sources = [
        sources.Source("fix-table", "url://table", sources.parse_markdown_table),
        sources.Source("fix-headings", "url://headings", sources.parse_qa_headings),
    ]
    monkeypatch.setattr(build, "SOURCES", fake_sources)
    monkeypatch.setattr(build, "CURATED_DIR", tmp_path / "none")
    monkeypatch.setattr(
        "qbank.fetch.fetch",
        lambda url, **kw: _FIXTURES["table" if "table" in url else "headings"],
    )

    bank = build.build(expand_llm=False, per_subtopic=0, refresh=True)
    flat = [q for qs in bank.values() for q in qs]
    assert "What is encapsulation?" in bank["OOP"]
    assert "How does a HashMap resize?" in bank["Java Collections"]
    assert any("volatile" in q for q in bank.get("Multithreading", []))
    # The unlabelled junk row was dropped.
    assert not any("university" in q for q in flat)
