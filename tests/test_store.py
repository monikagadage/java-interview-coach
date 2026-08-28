"""Tests for memory/store.py (SQLite persistence).

Every test points ``db_path`` at a fresh temp SQLite file (via pytest's
``tmp_path`` fixture) so nothing here ever touches the real
``interview_history.db`` at the project root, and tests don't leak state
into each other.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from memory import store


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_history.db"


# ── init_db / schema ─────────────────────────────────────────────────────

def test_init_db_creates_tables(db_path):
    store.init_db(db_path)
    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()
    assert {"sessions", "attempts"} <= tables


def test_init_db_is_idempotent(db_path):
    store.init_db(db_path)
    store.init_db(db_path)  # must not raise on re-create


# ── sessions ──────────────────────────────────────────────────────────────

def test_start_session_returns_unique_ids(db_path):
    s1 = store.start_session(db_path)
    s2 = store.start_session(db_path)
    assert s1 != s2
    assert isinstance(s1, str) and len(s1) > 0


def test_start_session_persists_row(db_path):
    session_id = store.start_session(db_path)
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT id FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == session_id


# ── record_attempt / get_session_attempts ────────────────────────────────

def test_record_attempt_and_get_session_attempts(db_path):
    session_id = store.start_session(db_path)
    store.record_attempt(
        session_id=session_id,
        topic="OOP",
        question="What is inheritance?",
        answer="Reusing code from a base class.",
        feedback="CORRECT - good answer.",
        is_correct=True,
        db_path=db_path,
    )
    store.record_attempt(
        session_id=session_id,
        topic="JVM",
        question="What is the heap?",
        answer="I don't know.",
        feedback="INCORRECT - the heap stores objects.",
        is_correct=False,
        db_path=db_path,
    )

    attempts = store.get_session_attempts(session_id, db_path=db_path)
    assert len(attempts) == 2
    # Returned in the order asked (ascending id).
    assert attempts[0]["topic"] == "OOP"
    assert attempts[0]["is_correct"] == 1
    assert attempts[1]["topic"] == "JVM"
    assert attempts[1]["is_correct"] == 0


def test_get_session_attempts_only_returns_that_session(db_path):
    session_a = store.start_session(db_path)
    session_b = store.start_session(db_path)

    store.record_attempt(
        session_id=session_a, topic="OOP", question="Q-A",
        answer="a", feedback="CORRECT", is_correct=True, db_path=db_path,
    )
    store.record_attempt(
        session_id=session_b, topic="OOP", question="Q-B",
        answer="b", feedback="CORRECT", is_correct=True, db_path=db_path,
    )

    attempts_a = store.get_session_attempts(session_a, db_path=db_path)
    assert len(attempts_a) == 1
    assert attempts_a[0]["question"] == "Q-A"


def test_get_session_attempts_empty_for_unknown_session(db_path):
    store.init_db(db_path)
    assert store.get_session_attempts("no-such-session", db_path=db_path) == []


# ── get_topic_stats (cumulative accuracy) ────────────────────────────────

def test_get_topic_stats_computes_accuracy(db_path):
    session_id = store.start_session(db_path)
    # OOP: 2 correct, 1 incorrect -> accuracy 2/3
    for is_correct in (True, True, False):
        store.record_attempt(
            session_id=session_id, topic="OOP", question=f"q-{is_correct}",
            answer="a", feedback="f", is_correct=is_correct, db_path=db_path,
        )
    # JVM: 1 correct out of 1 -> accuracy 1.0
    store.record_attempt(
        session_id=session_id, topic="JVM", question="q-jvm",
        answer="a", feedback="f", is_correct=True, db_path=db_path,
    )

    stats = store.get_topic_stats(db_path=db_path)
    assert stats["OOP"]["total"] == 3
    assert stats["OOP"]["correct"] == 2
    assert stats["OOP"]["accuracy"] == pytest.approx(2 / 3)
    assert stats["JVM"]["total"] == 1
    assert stats["JVM"]["accuracy"] == pytest.approx(1.0)


def test_get_topic_stats_accumulates_across_sessions(db_path):
    """Cross-session persistence: stats aren't scoped to one session."""
    session_1 = store.start_session(db_path)
    store.record_attempt(
        session_id=session_1, topic="Spring", question="q1",
        answer="a", feedback="f", is_correct=True, db_path=db_path,
    )
    session_2 = store.start_session(db_path)
    store.record_attempt(
        session_id=session_2, topic="Spring", question="q2",
        answer="a", feedback="f", is_correct=False, db_path=db_path,
    )

    stats = store.get_topic_stats(db_path=db_path)
    assert stats["Spring"]["total"] == 2
    assert stats["Spring"]["correct"] == 1


def test_get_topic_stats_empty_db(db_path):
    store.init_db(db_path)
    assert store.get_topic_stats(db_path=db_path) == {}


# ── get_cumulative_stats ──────────────────────────────────────────────────

def test_get_cumulative_stats_totals(db_path):
    session_id = store.start_session(db_path)
    store.record_attempt(
        session_id=session_id, topic="OOP", question="q1",
        answer="a", feedback="f", is_correct=True, db_path=db_path,
    )
    store.record_attempt(
        session_id=session_id, topic="OOP", question="q2",
        answer="a", feedback="f", is_correct=False, db_path=db_path,
    )

    cumulative = store.get_cumulative_stats(db_path=db_path)
    assert cumulative["total_questions"] == 2
    assert cumulative["total_correct"] == 1
    assert cumulative["total_sessions"] == 1


def test_get_cumulative_stats_weakest_topics_excludes_undersampled(db_path):
    session_id = store.start_session(db_path)
    # Only 1 attempt on "Patterns" -> below the min-2 threshold, excluded.
    store.record_attempt(
        session_id=session_id, topic="Patterns", question="q1",
        answer="a", feedback="f", is_correct=False, db_path=db_path,
    )
    # 2 attempts on "JVM", both wrong -> accuracy 0.0, eligible.
    for _ in range(2):
        store.record_attempt(
            session_id=session_id, topic="JVM", question="q-jvm",
            answer="a", feedback="f", is_correct=False, db_path=db_path,
        )

    cumulative = store.get_cumulative_stats(db_path=db_path)
    assert "Patterns" not in cumulative["weakest_topics"]
    assert "JVM" in cumulative["weakest_topics"]


def test_get_cumulative_stats_weakest_topics_ordered_by_accuracy(db_path):
    session_id = store.start_session(db_path)
    # Databases: 2/2 correct -> accuracy 1.0
    for _ in range(2):
        store.record_attempt(
            session_id=session_id, topic="Databases", question="q",
            answer="a", feedback="f", is_correct=True, db_path=db_path,
        )
    # Multithreading: 0/2 correct -> accuracy 0.0 (weakest)
    for _ in range(2):
        store.record_attempt(
            session_id=session_id, topic="Multithreading", question="q",
            answer="a", feedback="f", is_correct=False, db_path=db_path,
        )

    cumulative = store.get_cumulative_stats(db_path=db_path)
    assert cumulative["weakest_topics"][0] == "Multithreading"


# ── get_recent_questions ───────────────────────────────────────────────────

def test_get_recent_questions_returns_asked_questions(db_path):
    session_id = store.start_session(db_path)
    store.record_attempt(
        session_id=session_id, topic="OOP", question="What is polymorphism?",
        answer="a", feedback="f", is_correct=True, db_path=db_path,
    )
    recent = store.get_recent_questions("OOP", db_path=db_path)
    assert "What is polymorphism?" in recent


def test_get_recent_questions_respects_limit(db_path):
    session_id = store.start_session(db_path)
    for i in range(5):
        store.record_attempt(
            session_id=session_id, topic="OOP", question=f"q-{i}",
            answer="a", feedback="f", is_correct=True, db_path=db_path,
        )
    recent = store.get_recent_questions("OOP", limit=3, db_path=db_path)
    assert len(recent) == 3
    # Most recently asked (highest id) should be kept.
    assert {"q-4", "q-3", "q-2"} == recent


def test_get_recent_questions_scoped_to_topic(db_path):
    session_id = store.start_session(db_path)
    store.record_attempt(
        session_id=session_id, topic="OOP", question="oop-q",
        answer="a", feedback="f", is_correct=True, db_path=db_path,
    )
    store.record_attempt(
        session_id=session_id, topic="JVM", question="jvm-q",
        answer="a", feedback="f", is_correct=True, db_path=db_path,
    )
    recent_oop = store.get_recent_questions("OOP", db_path=db_path)
    assert recent_oop == {"oop-q"}


# ── Spaced repetition: record_review / get_due_questions / get_review_state ─

def test_record_review_rejects_unknown_rating(db_path):
    with pytest.raises(ValueError):
        store.record_review("OOP", "What is a class?", "Meh", db_path=db_path)


@pytest.mark.parametrize(
    "rating,days",
    [("Again", 1), ("Hard", 3), ("Good", 7), ("Easy", 14)],
)
def test_record_review_schedules_correct_interval(db_path, rating, days):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    next_review_at = store.record_review(
        "OOP", "What is a class?", rating, db_path=db_path, now=now
    )
    expected = (now + timedelta(days=days)).isoformat()
    assert next_review_at == expected


def test_record_review_upserts_same_question(db_path):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store.record_review("OOP", "What is a class?", "Again", db_path=db_path, now=now)
    store.record_review("OOP", "What is a class?", "Easy", db_path=db_path, now=now)

    state = store.get_review_state("OOP", "What is a class?", db_path=db_path)
    assert state["rating"] == "Easy"
    assert state["next_review_at"] == (now + timedelta(days=14)).isoformat()

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    conn.close()
    assert count == 1  # overwritten, not duplicated


def test_get_review_state_none_when_never_rated(db_path):
    store.init_db(db_path)
    assert store.get_review_state("OOP", "never rated", db_path=db_path) is None


def test_get_due_questions_returns_only_due(db_path):
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    # Rated "Again" 2 days ago -> due yesterday (already due).
    store.record_review(
        "OOP", "overdue question", "Again", db_path=db_path,
        now=now - timedelta(days=2),
    )
    # Rated "Easy" just now -> due in 14 days (not due).
    store.record_review(
        "OOP", "not due question", "Easy", db_path=db_path, now=now
    )

    due = store.get_due_questions(db_path=db_path, now=now)
    due_questions = {row["question"] for row in due}
    assert "overdue question" in due_questions
    assert "not due question" not in due_questions


def test_get_due_questions_orders_most_overdue_first(db_path):
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    store.record_review(
        "OOP", "slightly overdue", "Hard", db_path=db_path,
        now=now - timedelta(days=3, hours=1),  # due ~1h ago
    )
    store.record_review(
        "OOP", "very overdue", "Again", db_path=db_path,
        now=now - timedelta(days=5),  # due 4 days ago
    )

    due = store.get_due_questions(db_path=db_path, now=now)
    assert [row["question"] for row in due] == ["very overdue", "slightly overdue"]


def test_get_due_questions_filters_by_topic(db_path):
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    store.record_review(
        "OOP", "oop due", "Again", db_path=db_path, now=now - timedelta(days=2)
    )
    store.record_review(
        "JVM", "jvm due", "Again", db_path=db_path, now=now - timedelta(days=2)
    )

    due_oop = store.get_due_questions(db_path=db_path, topic="OOP", now=now)
    assert {row["question"] for row in due_oop} == {"oop due"}


def test_get_due_questions_empty_when_nothing_rated(db_path):
    store.init_db(db_path)
    assert store.get_due_questions(db_path=db_path) == []


def test_get_due_questions_respects_limit(db_path):
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    for i in range(5):
        store.record_review(
            "OOP", f"q-{i}", "Again", db_path=db_path, now=now - timedelta(days=2)
        )
    due = store.get_due_questions(db_path=db_path, now=now, limit=2)
    assert len(due) == 2
