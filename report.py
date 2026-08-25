"""Exportable session report (Markdown).

Pulls the current session's attempts back out of the SQLite store
(``memory.store``) so the report reflects exactly what was persisted, and
adds the cross-session weak-topic picture alongside it. Meant to be handed
to ``st.download_button`` from ``app.py``.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from memory import store


def build_session_report(session_id: str, db_path: str | Path | None = None) -> str:
    attempts = store.get_session_attempts(session_id, db_path=db_path)
    cumulative = store.get_cumulative_stats(db_path=db_path)

    total = len(attempts)
    correct = sum(1 for a in attempts if a["is_correct"])
    weak_this_session = sorted({a["topic"] for a in attempts if not a["is_correct"]})
    weakest_overall = cumulative["weakest_topics"]

    lines = [
        "# Java Interview Coach — Session Report",
        "",
        f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        "## This Session",
        f"- Questions answered: **{total}**",
        f"- Correct: **{correct}/{total}**",
        "- Topics to review: "
        + (", ".join(weak_this_session) if weak_this_session else "None — nice work!"),
        "",
        "## All-Time Progress",
        f"- Total questions answered across all sessions: **{cumulative['total_questions']}**",
        f"- Total correct across all sessions: **{cumulative['total_correct']}**",
        f"- Total practice sessions: **{cumulative['total_sessions']}**",
        "- Weakest topics overall: "
        + (", ".join(weakest_overall) if weakest_overall else "Not enough data yet"),
        "",
        "## Question-by-Question",
        "",
    ]

    if not attempts:
        lines.append("_No questions were answered this session._")
    else:
        for i, a in enumerate(attempts, start=1):
            verdict = "CORRECT" if a["is_correct"] else "INCORRECT"
            lines += [
                f"### {i}. [{a['topic']}] — {verdict}",
                "",
                f"**Question:** {a['question']}",
                "",
                f"**Your answer:** {a['answer']}",
                "",
                "**Feedback / ideal answer:**",
                "",
                f"{a['feedback']}",
                "",
                "---",
                "",
            ]

    return "\n".join(lines)
