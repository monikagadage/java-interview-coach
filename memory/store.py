"""SQLite-backed persistence for interview practice history.

Streamlit's ``st.session_state`` lives only as long as the process does, so
weak-topic tracking and scoring used to reset every time the app restarted.
This module persists every question attempt (topic, question, correctness,
timestamp, session id) with the stdlib ``sqlite3`` module (no ORM) so that
history accumulates across a user's whole practice history, not just one
sitting.

The database file defaults to ``interview_history.db`` at the project root
(sibling to ``questions_db.json``) and is created on first use.
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

DB_PATH = Path(__file__).resolve().parent.parent / "interview_history.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    feedback TEXT,
    is_correct INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions (id)
);

CREATE INDEX IF NOT EXISTS idx_attempts_topic ON attempts (topic);
CREATE INDEX IF NOT EXISTS idx_attempts_session ON attempts (session_id);
"""


def _resolve(db_path: str | Path | None) -> str:
    return str(db_path or DB_PATH)


@contextmanager
def _connect(db_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_resolve(db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str | Path | None = None) -> None:
    """Create the sessions/attempts tables if they don't exist yet. Idempotent."""
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)


def start_session(db_path: str | Path | None = None) -> str:
    """Register a new practice session and return its id."""
    init_db(db_path)
    session_id = str(uuid.uuid4())
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO sessions (id, started_at) VALUES (?, ?)",
            (session_id, datetime.now(timezone.utc).isoformat()),
        )
    return session_id


def record_attempt(
    session_id: str,
    topic: str,
    question: str,
    answer: str,
    feedback: str,
    is_correct: bool,
    db_path: str | Path | None = None,
) -> None:
    """Persist one answered question so it survives a restart."""
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT INTO attempts
                   (session_id, topic, question, answer, feedback, is_correct, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                topic,
                question,
                answer,
                feedback,
                int(bool(is_correct)),
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def get_topic_stats(db_path: str | Path | None = None) -> dict[str, dict]:
    """Return ``{topic: {"correct", "total", "accuracy"}}`` across ALL history."""
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT topic, SUM(is_correct) AS correct, COUNT(*) AS total
               FROM attempts GROUP BY topic"""
        ).fetchall()

    stats: dict[str, dict] = {}
    for row in rows:
        total = row["total"]
        correct = row["correct"] or 0
        stats[row["topic"]] = {
            "correct": correct,
            "total": total,
            "accuracy": correct / total if total else 0.0,
        }
    return stats


def get_cumulative_stats(db_path: str | Path | None = None) -> dict:
    """High-level counters for the sidebar: totals + weakest topics overall."""
    init_db(db_path)
    with _connect(db_path) as conn:
        total_questions = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
        total_correct = conn.execute(
            "SELECT COALESCE(SUM(is_correct), 0) FROM attempts"
        ).fetchone()[0]
        total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

    topic_stats = get_topic_stats(db_path)

    # Weakest = lowest accuracy among topics with enough attempts to be
    # meaningful, ties broken toward the topic practiced more.
    candidates = [
        (topic, s["accuracy"], s["total"])
        for topic, s in topic_stats.items()
        if s["total"] >= 2
    ]
    candidates.sort(key=lambda t: (t[1], -t[2]))

    return {
        "total_questions": total_questions,
        "total_correct": total_correct,
        "total_sessions": total_sessions,
        "weakest_topics": [c[0] for c in candidates[:3]],
        "topic_stats": topic_stats,
    }


def get_recent_questions(
    topic: str, limit: int = 15, db_path: str | Path | None = None
) -> set[str]:
    """Questions recently asked for a topic (any session), to dodge repeats."""
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT question FROM attempts
               WHERE topic = ? ORDER BY id DESC LIMIT ?""",
            (topic, limit),
        ).fetchall()
    return {row["question"] for row in rows}


def get_session_attempts(session_id: str, db_path: str | Path | None = None) -> list[dict]:
    """All attempts for one session, in order asked — feeds the exportable report."""
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT topic, question, answer, feedback, is_correct, created_at
               FROM attempts WHERE session_id = ? ORDER BY id ASC""",
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]
