"""Tests for mcp_server/tools.py.

``mcp_server.tools`` is deliberately free of the LangChain / ChromaDB / mcp
import chain, so every tool is exercised here with just pytest + a temp
SQLite file and, where needed, a fake collection / fake LLM.
"""
from __future__ import annotations

import pytest

from mcp_server import tools
from topics import TOPICS


@pytest.fixture
def db(tmp_path):
    return tmp_path / "hist.db"


# ── fakes ──────────────────────────────────────────────────────────────

class _FakeCollection:
    """Stands in for a ChromaDB collection: returns a fixed candidate list."""

    def __init__(self, documents):
        self._documents = documents

    def query(self, query_texts, n_results):
        return {"documents": [self._documents[:n_results]]}


class _FakeLLM:
    def __init__(self, content):
        self._content = content

    def invoke(self, _prompt):
        return type("Resp", (), {"content": self._content})()


# ── store-backed tools ─────────────────────────────────────────────────

def test_list_topics_reports_zero_before_any_practice(db):
    rows = tools.list_topics(db_path=db)
    assert [r["topic"] for r in rows] == TOPICS
    assert all(r["attempts"] == 0 and r["accuracy"] is None for r in rows)


def test_start_session_returns_an_id(db):
    out = tools.start_session(db_path=db)
    assert isinstance(out["session_id"], str) and out["session_id"]


def test_record_attempt_then_progress_and_topic_accuracy(db):
    sid = tools.start_session(db_path=db)["session_id"]
    tools.record_attempt(sid, "OOP", "What is encapsulation?", "hiding state",
                         "CORRECT ...", True, db_path=db)
    tools.record_attempt(sid, "OOP", "What is a JVM?", "no idea",
                         "INCORRECT ...", False, db_path=db)

    progress = tools.get_progress(db_path=db)
    assert progress["total_questions"] == 2
    assert progress["total_correct"] == 1

    oop = next(r for r in tools.list_topics(db_path=db) if r["topic"] == "OOP")
    assert oop["attempts"] == 2
    assert oop["accuracy"] == 0.5


def test_rate_question_schedules_a_review_and_it_comes_due(db):
    out = tools.rate_question("Spring", "What is a bean?", "Again", db_path=db)
    assert out["next_review_at"]  # Again -> 1 day out
    # Nothing is due yet...
    assert tools.get_due_reviews(db_path=db) == []


def test_rate_question_rejects_an_unknown_rating(db):
    with pytest.raises(ValueError):
        tools.rate_question("Spring", "q", "Sometimes", db_path=db)


# ── retrieval + grading tools (fakes, still no heavy deps) ──────────────

def test_get_interview_question_selects_from_the_candidate_pool(db):
    pool = [
        "What is the difference between an interface and an abstract class?",
        "Define polymorphism.",
        "How does the JVM implement method dispatch under the hood?",
    ]
    out = tools.get_interview_question(_FakeCollection(pool), "OOP", db_path=db)
    assert out["question"] in pool
    assert 0.0 <= out["estimated_difficulty"] <= 1.0
    assert out["topic"] == "OOP"


def test_get_interview_question_auto_mode_picks_a_known_topic(db):
    out = tools.get_interview_question(
        _FakeCollection(["Define polymorphism."]), "ignored", mode="auto", db_path=db
    )
    assert out["topic"] in TOPICS


def test_get_interview_question_handles_an_empty_bank(db):
    out = tools.get_interview_question(_FakeCollection([]), "OOP", db_path=db)
    assert out["question"] is None
    assert "no questions" in out["error"]


def test_evaluate_answer_parses_correct_and_persists_when_scoped(db):
    sid = tools.start_session(db_path=db)["session_id"]
    llm = _FakeLLM("CORRECT\nGood, that's the idea.\nIdeal: ...")
    out = tools.evaluate_answer(llm, "What is encapsulation?", "hiding internal state",
                                topic="OOP", session_id=sid, db_path=db)
    assert out["is_correct"] is True
    assert out["recorded"] is True
    assert tools.get_progress(db_path=db)["total_questions"] == 1


def test_evaluate_answer_does_not_persist_without_topic_and_session(db):
    llm = _FakeLLM("INCORRECT\nNot quite.\nIdeal: ...")
    out = tools.evaluate_answer(llm, "q", "a", db_path=db)
    assert out["is_correct"] is False
    assert out["recorded"] is False
    assert tools.get_progress(db_path=db)["total_questions"] == 0


def test_get_hint_returns_the_model_text(db):
    out = tools.get_hint(_FakeLLM("Think about what 'private' buys you."), "q")
    assert out["hint"].startswith("Think about")
