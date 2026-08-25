"""Difficulty-adaptive question selection.

This sits *on top of* the existing ChromaDB RAG retrieval, not in place of
it: the vector search still finds the pool of questions semantically
relevant to the chosen topic; this module only decides *which* one from
that pool to actually ask, using the persisted history in
``memory.store`` to lean toward weak topics and to nudge difficulty as the
user's accuracy on a topic changes.

The 1,715-question bank has no explicit difficulty labels, so difficulty is
approximated with a small heuristic (``_estimate_difficulty``) based on
question length and "deeper" phrasing (comparisons, internals, "why", "how
does X work") vs. simple recall-style phrasing ("what is", "define"). This
is a proxy, not a labeled ground truth — called out here so it isn't
mistaken for one.
"""
from __future__ import annotations

import random
import re
from pathlib import Path

from memory import store

_HARD_HINTS = re.compile(
    r"\b(difference between|internally|under the hood|implement|design|"
    r"why|trade-?off|compare|how does .* work|architecture|complexity)\b",
    re.IGNORECASE,
)
_EASY_HINTS = re.compile(r"\bwhat is\b|\bdefine\b|\blist\b", re.IGNORECASE)

# Below this many attempts on a topic we don't trust the accuracy signal yet.
_MIN_ATTEMPTS_FOR_ADAPTATION = 3
# New/under-sampled topics start slightly on the easier side.
_DEFAULT_TARGET_DIFFICULTY = 0.35


def estimate_difficulty(question: str) -> float:
    """Heuristic 0 (easy) .. 1 (hard) proxy score for a question's difficulty."""
    words = len(question.split())
    score = min(words / 40.0, 1.0) * 0.6  # longer questions tend to probe more
    if _HARD_HINTS.search(question):
        score += 0.3
    if _EASY_HINTS.search(question):
        score -= 0.2
    return max(0.0, min(1.0, score))


def select_question(
    candidates: list[str], topic: str, db_path: str | Path | None = None
) -> str:
    """Pick the best candidate question for this user's current skill level.

    ``candidates`` is the pool already returned by the ChromaDB RAG query for
    ``topic`` — this function only re-ranks/filters that existing pool, it
    never generates or fetches questions itself.
    """
    if not candidates:
        raise ValueError("No candidate questions to select from")

    topic_stats = store.get_topic_stats(db_path=db_path)
    stats = topic_stats.get(topic)

    if stats and stats["total"] >= _MIN_ATTEMPTS_FOR_ADAPTATION:
        # Accuracy improving on this topic -> ask harder questions next.
        target = stats["accuracy"]
    else:
        target = _DEFAULT_TARGET_DIFFICULTY

    # Avoid immediate repeats of recently-asked questions for this topic,
    # falling back to the full pool if everything has been asked recently.
    recent = store.get_recent_questions(topic, db_path=db_path)
    pool = [q for q in candidates if q not in recent] or list(candidates)

    scored = sorted(pool, key=lambda q: abs(estimate_difficulty(q) - target))
    # Keep the closest-difficulty half, then randomize within it so the
    # same accuracy level doesn't always produce the exact same question.
    top_n = scored[: max(1, len(scored) // 2)] or scored
    return random.choice(top_n)


def pick_topic_for_auto_mode(
    available_topics: list[str], db_path: str | Path | None = None
) -> str:
    """For 'Auto / focus on weak topics' mode: weight topic choice toward
    topics the user has historically answered incorrectly more often."""
    topic_stats = store.get_topic_stats(db_path=db_path)
    weights = []
    for topic in available_topics:
        s = topic_stats.get(topic)
        if s and s["total"] >= 2:
            weights.append(max(0.15, 1.0 - s["accuracy"]))
        else:
            weights.append(0.7)  # unseen topics still get sampled reasonably often
    return random.choices(available_topics, weights=weights, k=1)[0]
