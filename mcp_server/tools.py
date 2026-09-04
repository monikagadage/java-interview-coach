"""Tool logic, independent of the MCP wire layer.

Every function here is a plain callable with its heavy dependencies
(``collection``, ``llm``) passed in, so the store-backed tools can be unit
tested with nothing but ``pytest`` + a temp SQLite file, and the
retrieval/grading tools can be tested with a fake collection / fake LLM.
``mcp_server.server`` is the only place that builds the real ones.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from memory import store
from topics import TOPICS

# How many RAG candidates to pull before the adaptive layer ranks them.
_POOL_SIZE = 12


# ── store-backed tools (no API key, no vector store) ─────────────────────

def list_topics(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    """The practice topics, each with the user's running accuracy."""
    stats = store.get_topic_stats(db_path=db_path)
    out = []
    for topic in TOPICS:
        s = stats.get(topic)
        out.append(
            {
                "topic": topic,
                "attempts": s["total"] if s else 0,
                "accuracy": round(s["accuracy"], 2) if s else None,
            }
        )
    return out


def start_session(db_path: str | Path | None = None) -> dict[str, str]:
    """Open a new practice session; pass its id to ``evaluate_answer`` to
    have attempts recorded against it."""
    return {"session_id": store.start_session(db_path=db_path)}


def get_progress(db_path: str | Path | None = None) -> dict[str, Any]:
    """All-time totals plus the weakest topics by accuracy."""
    return store.get_cumulative_stats(db_path=db_path)


def record_attempt(
    session_id: str,
    topic: str,
    question: str,
    answer: str,
    feedback: str,
    is_correct: bool,
    db_path: str | Path | None = None,
) -> dict[str, bool]:
    """Persist an answered question directly (when grading happened elsewhere)."""
    store.record_attempt(
        session_id=session_id,
        topic=topic,
        question=question,
        answer=answer,
        feedback=feedback,
        is_correct=is_correct,
        db_path=db_path,
    )
    return {"recorded": True}


def rate_question(
    topic: str, question: str, rating: str, db_path: str | Path | None = None
) -> dict[str, str]:
    """Schedule a question's next spaced-repetition review from a confidence
    rating: one of ``Again`` / ``Hard`` / ``Good`` / ``Easy``."""
    next_review_at = store.record_review(topic, question, rating, db_path=db_path)
    return {
        "topic": topic,
        "question": question,
        "rating": rating,
        "next_review_at": next_review_at,
    }


def get_due_reviews(
    topic: str | None = None, db_path: str | Path | None = None
) -> list[dict[str, Any]]:
    """Questions whose scheduled review date has arrived, most overdue first."""
    return store.get_due_questions(topic=topic, db_path=db_path)


# ── retrieval + grading tools (need a collection / an llm) ───────────────

def _retrieve_candidates(collection, topic: str, n_results: int = _POOL_SIZE) -> list[str]:
    """The RAG step: semantic search against the ChromaDB collection.

    Inlined here (rather than imported from ``graph.workflow``) so this
    module stays free of the LangChain/LangGraph import chain and the tool
    logic is unit-testable with just a fake collection object.
    """
    results = collection.query(query_texts=[topic], n_results=n_results)
    documents = results.get("documents") or [[]]
    return documents[0]


def get_interview_question(
    collection,
    topic: str,
    mode: str = "topic",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """RAG retrieval + difficulty-adaptive selection.

    ``mode="auto"`` ignores ``topic`` and picks one weighted toward the
    user's weaker areas.
    """
    from graph.selection import (
        estimate_difficulty,
        pick_topic_for_auto_mode,
        select_question,
    )

    chosen_topic = (
        pick_topic_for_auto_mode(TOPICS, db_path=db_path) if mode == "auto" else topic
    )
    candidates = _retrieve_candidates(collection, chosen_topic)
    if not candidates:
        return {"topic": chosen_topic, "question": None,
                "error": f"no questions in the bank for topic {chosen_topic!r}"}

    question = select_question(candidates, chosen_topic, db_path=db_path)
    return {
        "topic": chosen_topic,
        "question": question,
        "estimated_difficulty": round(estimate_difficulty(question), 2),
    }


def evaluate_answer(
    llm,
    question: str,
    answer: str,
    topic: str | None = None,
    session_id: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Grade an answer against an ideal answer (CORRECT / INCORRECT + feedback).

    If both ``topic`` and ``session_id`` are given, the attempt is persisted
    so it counts toward progress and weak-topic tracking.
    """
    from prompts import EVAL_PROMPT

    response = llm.invoke(EVAL_PROMPT.format(question=question, answer=answer))
    feedback = response.content
    is_correct = feedback.strip().upper().startswith("CORRECT")

    if topic and session_id:
        store.record_attempt(
            session_id=session_id,
            topic=topic,
            question=question,
            answer=answer,
            feedback=feedback,
            is_correct=is_correct,
            db_path=db_path,
        )

    return {"is_correct": is_correct, "feedback": feedback, "recorded": bool(topic and session_id)}


def get_hint(llm, question: str) -> dict[str, str]:
    """A short hint for a question that doesn't give away the answer."""
    from prompts import HINT_PROMPT

    response = llm.invoke(HINT_PROMPT.format(question=question))
    return {"hint": response.content}
