"""Tests for graph/selection.py (difficulty-adaptive ranking).

``graph.selection`` never imports ChromaDB itself — ``select_question`` and
``pick_topic_for_auto_mode`` operate on a plain ``list[str]`` of candidate
question strings that the caller (``graph/workflow.py``'s RAG retrieval
step) already fetched from Chroma. So there is no vector-store client to
mock here; these tests exercise the ranking/filtering logic directly with
fixture candidate lists and a temp SQLite file for ``memory.store`` history,
never touching a real Chroma collection or the project's real
``interview_history.db``.
"""
from __future__ import annotations

import random

import pytest

from graph import selection
from memory import store


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test_history.db"
    store.init_db(path)
    return path


# ── estimate_difficulty ───────────────────────────────────────────────────

def test_estimate_difficulty_easy_phrasing_scores_low():
    easy = selection.estimate_difficulty("What is a variable?")
    assert easy < 0.5


def test_estimate_difficulty_hard_phrasing_scores_high():
    hard = selection.estimate_difficulty(
        "Explain the difference between HashMap and ConcurrentHashMap "
        "internally, and describe the trade-off in a multithreaded design."
    )
    assert hard > 0.5


def test_estimate_difficulty_hard_beats_easy():
    easy = selection.estimate_difficulty("What is a variable?")
    hard = selection.estimate_difficulty(
        "Explain how the JVM garbage collector works internally and the "
        "trade-offs between different collection algorithms."
    )
    assert hard > easy


def test_estimate_difficulty_is_bounded_0_to_1():
    for q in [
        "What is Java?",
        "Explain in detail the internal difference between how the JVM "
        "class loader, why the trade-off of design and architecture and "
        "complexity of implement compare under the hood works internally "
        "for a very very very very very very very very very long question",
        "",
    ]:
        score = selection.estimate_difficulty(q)
        assert 0.0 <= score <= 1.0


# ── select_question: difficulty re-ranking ───────────────────────────────

def test_select_question_raises_on_empty_candidates(db_path):
    with pytest.raises(ValueError):
        selection.select_question([], "OOP", db_path=db_path)


def test_select_question_defaults_to_easy_target_with_few_attempts(db_path):
    """With < 3 recorded attempts on a topic, target difficulty is the
    fixed easy-ish default (0.35), not the (noisy/absent) accuracy."""
    session_id = store.start_session(db_path)
    # Only 1 attempt recorded -- below _MIN_ATTEMPTS_FOR_ADAPTATION (3).
    store.record_attempt(
        session_id=session_id, topic="OOP", question="unrelated question",
        answer="a", feedback="f", is_correct=True, db_path=db_path,
    )

    candidates = [
        "What is a variable?",  # very easy (difficulty ~0.0)
        "Explain in complete internal detail the difference between how "
        "the JVM class loader architecture works, the trade-off and "
        "complexity of each garbage collection implementation design, why "
        "the under the hood compare of each internally matters for a "
        "production multithreaded system",  # very hard (difficulty ~0.9)
    ]

    random.seed(0)
    picks = {
        selection.select_question(candidates, "OOP", db_path=db_path)
        for _ in range(20)
    }
    # Target ~0.35 is much closer to the easy question's difficulty (~0.0)
    # than the very-hard one's (~0.9), so the easy one should always win.
    assert picks == {"What is a variable?"}


def test_select_question_targets_high_accuracy_with_harder_questions(db_path):
    """With >= 3 attempts and high accuracy, target difficulty rises, so
    harder questions should be selected."""
    session_id = store.start_session(db_path)
    for _ in range(5):
        store.record_attempt(
            session_id=session_id, topic="OOP", question="filler",
            answer="a", feedback="f", is_correct=True, db_path=db_path,
        )  # 5/5 correct -> accuracy 1.0

    candidates = [
        "What is a class?",  # easy
        "Explain the internal trade-off and architecture difference "
        "between composition and inheritance design under the hood",  # hard
    ]

    random.seed(0)
    picks = {
        selection.select_question(candidates, "OOP", db_path=db_path)
        for _ in range(20)
    }
    assert candidates[1] in picks
    assert "What is a class?" not in picks


def test_select_question_filters_recently_asked(db_path):
    session_id = store.start_session(db_path)
    store.record_attempt(
        session_id=session_id, topic="OOP", question="recently asked question",
        answer="a", feedback="f", is_correct=True, db_path=db_path,
    )

    candidates = ["recently asked question", "brand new question"]
    for _ in range(10):
        pick = selection.select_question(candidates, "OOP", db_path=db_path)
        assert pick == "brand new question"


def test_select_question_falls_back_to_full_pool_if_all_recent(db_path):
    """If every candidate was recently asked, don't error out -- fall back
    to the full (unfiltered) pool instead of an empty one."""
    session_id = store.start_session(db_path)
    store.record_attempt(
        session_id=session_id, topic="OOP", question="only question",
        answer="a", feedback="f", is_correct=True, db_path=db_path,
    )

    candidates = ["only question"]
    pick = selection.select_question(candidates, "OOP", db_path=db_path)
    assert pick == "only question"


# ── pick_topic_for_auto_mode ─────────────────────────────────────────────

def test_pick_topic_for_auto_mode_favors_weak_topics(db_path):
    session_id = store.start_session(db_path)
    # "Strong" topic: high accuracy.
    for _ in range(10):
        store.record_attempt(
            session_id=session_id, topic="Strong", question="q",
            answer="a", feedback="f", is_correct=True, db_path=db_path,
        )
    # "Weak" topic: low accuracy.
    for _ in range(10):
        store.record_attempt(
            session_id=session_id, topic="Weak", question="q",
            answer="a", feedback="f", is_correct=False, db_path=db_path,
        )

    random.seed(42)
    picks = [
        selection.pick_topic_for_auto_mode(["Strong", "Weak"], db_path=db_path)
        for _ in range(500)
    ]
    weak_count = picks.count("Weak")
    strong_count = picks.count("Strong")
    # Weak topic (accuracy 0.0 -> weight 1.0) should come up meaningfully
    # more often than the strong topic (accuracy 1.0 -> weight 0.15).
    assert weak_count > strong_count


def test_pick_topic_for_auto_mode_returns_only_from_available(db_path):
    random.seed(1)
    topics = ["OOP", "JVM", "Spring"]
    for _ in range(20):
        pick = selection.pick_topic_for_auto_mode(topics, db_path=db_path)
        assert pick in topics


def test_pick_topic_for_auto_mode_unseen_topics_still_sampled(db_path):
    """Unseen topics get a flat weight (0.7), not zero -- they must still
    be selectable, not starved out entirely."""
    random.seed(7)
    topics = ["NeverAskedTopic"]
    picks = {
        selection.pick_topic_for_auto_mode(topics, db_path=db_path)
        for _ in range(5)
    }
    assert picks == {"NeverAskedTopic"}
