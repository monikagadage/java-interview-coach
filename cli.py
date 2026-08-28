#!/usr/bin/env python3
"""CLI practice mode: ask -> answer via stdin -> evaluate -> score.

Runs a full interview-practice session with no Streamlit involved,
reusing exactly the same pieces app.py drives from button clicks:

- ``corpus.load_collection`` for RAG retrieval (ChromaDB)
- ``graph.selection.pick_topic_for_auto_mode`` for auto-topic weighting
- ``graph.workflow.build_nodes`` (``graph/state.py``'s ``InterviewState``
  shape, ``ask``/``evaluate`` nodes) for the actual ask -> evaluate flow
- ``memory.store`` for cross-session persistence

That reuse is the point: if this script produces the same kind of
questions, scoring, and persisted history as the Streamlit app using none
of Streamlit's machinery, the business logic is genuinely decoupled from
the UI, not just nominally split into modules.

Usage:
    uv run python cli.py                       # auto topic, runs until you type 'quit'
    uv run python cli.py --topic OOP --questions 3
    echo "answer text\n\nquit" | uv run python cli.py --questions 5   # scripted/piped

Requires GROQ_API_KEY (via .env or the environment) — the evaluate step is
a real Groq call, same as app.py. Question retrieval/selection itself
needs no API key at all (see README.md / DESIGN.md for the split).
"""
from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from corpus import load_collection
from graph.selection import pick_topic_for_auto_mode
from graph.workflow import build_nodes
from memory import store

AUTO = "auto"
TOPICS = [
    "OOP", "Java Core", "Java Collections", "Spring",
    "JVM", "Multithreading", "Databases", "Java 8",
    "Patterns", "Testing",
]


def _prompt_answer() -> str | None:
    """Read a (possibly multi-line) answer from stdin, blank line to submit.

    Returns ``None`` if stdin is exhausted before any input arrives (e.g.
    piped input ran out) — distinct from a deliberately empty answer, so a
    scripted session stops cleanly instead of looping on a closed stream.
    """
    print("Your answer (blank line to submit):")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            if not lines:
                return None
            break
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines)


def run_session(nodes: dict, topic_arg: str, max_questions: int | None) -> None:
    session_id = store.start_session()
    score = 0
    total = 0
    weak_topics: list[str] = []

    print("=" * 52)
    print("Java Interview Coach -- CLI practice mode")
    print(f"Session: {session_id}")
    print("Type 'quit' at an answer prompt to stop early.")
    print("=" * 52)

    while max_questions is None or total < max_questions:
        topic = (
            pick_topic_for_auto_mode(TOPICS, db_path=store.DB_PATH)
            if topic_arg == AUTO
            else topic_arg
        )
        ask_state = {"topic": topic, "total_questions": total}
        question = nodes["ask"](ask_state)["current_question"]

        print(f"\n--- Question {total + 1} [{topic}] ---")
        print(question)

        answer = _prompt_answer()
        if answer is None:
            print("\n(end of input -- stopping session)")
            break
        if answer.strip().lower() == "quit":
            print("Stopping early.")
            break
        if not answer.strip():
            print("(skipped -- empty answer)")
            continue

        eval_state = {
            "topic": topic,
            "current_question": question,
            "user_answer": answer,
            "score": score,
            "weak_topics": weak_topics,
            "session_id": session_id,
        }
        print("Evaluating...")
        try:
            result = nodes["evaluate"](eval_state)
        except Exception as exc:
            print(f"\nERROR: the Groq evaluate call failed: {exc}", file=sys.stderr)
            print(
                "This is a live API call (same as app.py's evaluate step) -- check "
                "GROQ_API_KEY is valid and you have network access. Stopping session.",
                file=sys.stderr,
            )
            break
        feedback = result["feedback"]
        score = result["score"]
        weak_topics = result["weak_topics"]
        total += 1

        verdict = "CORRECT" if feedback.strip().upper().startswith("CORRECT") else "INCORRECT"
        print(f"\n[{verdict}]")
        print(feedback)
        print(f"\nScore so far: {score}/{total}")

    print("\n" + "=" * 52)
    print(f"Final score: {score}/{total}")
    if weak_topics:
        print("Topics to review: " + ", ".join(sorted(set(weak_topics))))
    print(f"Session id: {session_id}")
    print(f"Persisted to: {store.DB_PATH}")
    print("=" * 52)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Java Interview Coach -- CLI practice mode (no Streamlit)."
    )
    parser.add_argument(
        "--topic",
        default=AUTO,
        help=(
            f"Topic to practice ({', '.join(TOPICS)}), or 'auto' to weight "
            "toward your weak topics (default: auto)"
        ),
    )
    parser.add_argument(
        "--questions",
        type=int,
        default=None,
        help="Stop after this many questions (default: unlimited -- type 'quit' to stop)",
    )
    args = parser.parse_args()

    if args.topic != AUTO and args.topic not in TOPICS:
        print(f"ERROR: unknown --topic {args.topic!r}. Choose from: {', '.join(TOPICS)}, or 'auto'.", file=sys.stderr)
        sys.exit(1)

    load_dotenv()

    try:
        collection = load_collection()
    except FileNotFoundError:
        print(
            "ERROR: questions_db.json not found. Run rag.ipynb once to build it "
            "(see README.md 'Quick Start').",
            file=sys.stderr,
        )
        sys.exit(1)

    # Constructed here (not at import time) so the retrieval/selection path
    # above can be exercised, and this failure point stays precise, even
    # with no GROQ_API_KEY set at all.
    from langchain_groq import ChatGroq

    try:
        llm = ChatGroq(model="llama-3.3-70b-versatile")
    except Exception as exc:
        print(f"ERROR: could not construct the Groq client: {exc}", file=sys.stderr)
        print(
            "Set GROQ_API_KEY in your environment or .env file (see README.md) "
            "-- the evaluate step needs a real Groq call and cannot proceed without it.",
            file=sys.stderr,
        )
        sys.exit(1)

    nodes = build_nodes(collection, llm)

    try:
        run_session(nodes, args.topic, args.questions)
    except KeyboardInterrupt:
        print("\nInterrupted -- exiting.")


if __name__ == "__main__":
    main()
