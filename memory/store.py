"""SQLite-backed persistence for interview practice history.

Streamlit's ``st.session_state`` lives only as long as the process does, so
weak-topic tracking and scoring used to reset every time the app restarted.
This module persists every question attempt (topic, question, correctness,
timestamp, session id) with the stdlib ``sqlite3`` module (no ORM) so that
history accumulates across a user's whole practice history, not just one
sitting.

Round 2 adds a lightweight spaced-repetition schedule on top of the same
file: ``reviews`` tracks one row per (topic, question) with a
``next_review_at`` date, driven by a post-answer confidence rating (see
``record_review`` / ``RATING_INTERVALS_DAYS``).

The database file defaults to ``interview_history.db`` at the project root
(sibling to ``questions_db.json``) and is created on first use.
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
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

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    question TEXT NOT NULL,
    rating TEXT NOT NULL,
    next_review_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (topic, question)
);

CREATE INDEX IF NOT EXISTS idx_reviews_next_review ON reviews (next_review_at);
"""

# Confidence rating (chosen by the user right after seeing feedback) ->
# how many days out the next review of that exact question is scheduled.
# Deliberately simple fixed intervals rather than a full Anki-style
# ease-factor algorithm -- "similar in spirit to a standard SRS", not a
# reimplementation of one.
RATING_INTERVALS_DAYS: dict[str, int] = {
    "Again": 1,
    "Hard": 3,
    "Good": 7,
    "Easy": 14,
}


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


# ── Spaced repetition ───────────────────────────────────────────────────

def record_review(
    topic: str,
    question: str,
    rating: str,
    db_path: str | Path | None = None,
    now: datetime | None = None,
) -> str:
    """Record a post-answer confidence rating and (re)schedule the next
    review for this exact (topic, question) pair.

    ``rating`` must be one of ``RATING_INTERVALS_DAYS`` (Again/Hard/Good/
    Easy). Returns the new ``next_review_at`` as an ISO date string.
    Re-rating the same question later simply overwrites its schedule
    (``UNIQUE(topic, question)`` + upsert) — history of past ratings isn't
    kept, only the current one, since only the *next* due date matters for
    scheduling.
    """
    if rating not in RATING_INTERVALS_DAYS:
        raise ValueError(
            f"Unknown rating {rating!r}; must be one of {list(RATING_INTERVALS_DAYS)}"
        )
    init_db(db_path)
    now = now or datetime.now(timezone.utc)
    next_review_at = (now + timedelta(days=RATING_INTERVALS_DAYS[rating])).isoformat()
    updated_at = now.isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT INTO reviews (topic, question, rating, next_review_at, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(topic, question) DO UPDATE SET
                   rating = excluded.rating,
                   next_review_at = excluded.next_review_at,
                   updated_at = excluded.updated_at""",
            (topic, question, rating, next_review_at, updated_at),
        )
    return next_review_at


def get_due_questions(
    db_path: str | Path | None = None,
    topic: str | None = None,
    now: datetime | None = None,
    limit: int = 50,
) -> list[dict]:
    """Questions whose scheduled review date has arrived (or passed).

    Ordered most-overdue-first. Only questions that have actually been
    rated at least once show up here (a question with no ``reviews`` row
    was never rated, so it has no schedule to be "due" against).
    """
    init_db(db_path)
    now = now or datetime.now(timezone.utc)
    query = """SELECT topic, question, rating, next_review_at, updated_at
               FROM reviews WHERE next_review_at <= ?"""
    params: list = [now.isoformat()]
    if topic:
        query += " AND topic = ?"
        params.append(topic)
    query += " ORDER BY next_review_at ASC LIMIT ?"
    params.append(limit)
    with _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_review_state(
    topic: str, question: str, db_path: str | Path | None = None
) -> dict | None:
    """The current schedule for one (topic, question) pair, if it's ever been rated."""
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            """SELECT topic, question, rating, next_review_at, updated_at
               FROM reviews WHERE topic = ? AND question = ?""",
            (topic, question),
        ).fetchone()
    return dict(row) if row else None
