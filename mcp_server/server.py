"""FastMCP wiring for Java Interview Coach.

Run it:

    python -m mcp_server                 # stdio (Claude Desktop / Cursor / VS Code)
    python -m mcp_server --http          # streamable-HTTP on 127.0.0.1:8000/mcp

The ChromaDB collection (a few seconds to embed 1,715 questions) and the
Groq client are built lazily on first use, so `list_tools` and the
store-backed tools respond instantly and a missing GROQ_API_KEY only
matters if you actually call a grading tool.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from mcp_server import tools
from topics import TOPICS

load_dotenv()

mcp = FastMCP(
    "java-interview-coach",
    instructions=(
        "Run mock Java technical interviews. Typical loop: start_session -> "
        "get_interview_question -> (get_hint if the candidate is stuck) -> "
        "evaluate_answer -> rate_question. Use get_due_reviews to resurface "
        "questions that are due, and get_progress to report on weak topics."
    ),
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8000")),
)

# ── lazily-built heavy dependencies ─────────────────────────────────────

_collection = None
_llm = None


def _get_collection():
    global _collection
    if _collection is None:
        from corpus import load_collection

        _collection = load_collection()
    return _collection


def _get_llm():
    global _llm
    if _llm is None:
        if not os.environ.get("GROQ_API_KEY"):
            raise RuntimeError(
                "GROQ_API_KEY is not set. The grading tools (evaluate_answer, "
                "get_hint) need a Groq API key — add it to the MCP client's env "
                "config or a .env file. Retrieval, progress, and spaced-repetition "
                "tools work without one."
            )
        from langchain_groq import ChatGroq

        _llm = ChatGroq(model="llama-3.3-70b-versatile")
    return _llm


# ── tools ──────────────────────────────────────────────────────────────

@mcp.tool()
def list_topics() -> list[dict]:
    """List the Java practice topics with the user's running accuracy on each."""
    return tools.list_topics()


@mcp.tool()
def start_session() -> dict:
    """Start a new practice session. Pass the returned session_id to
    evaluate_answer so attempts are recorded against it."""
    return tools.start_session()


@mcp.tool()
def get_interview_question(topic: str, mode: str = "topic") -> dict:
    """Get one interview question. mode="topic" uses the given topic;
    mode="auto" ignores it and picks one weighted toward weak areas.
    Returns {topic, question, estimated_difficulty}."""
    return tools.get_interview_question(_get_collection(), topic, mode=mode)


@mcp.tool()
def evaluate_answer(
    question: str, answer: str, topic: str = "", session_id: str = ""
) -> dict:
    """Grade an answer (CORRECT/INCORRECT + feedback + ideal answer).
    Pass topic and session_id to record the attempt toward progress.
    Needs GROQ_API_KEY."""
    return tools.evaluate_answer(
        _get_llm(),
        question,
        answer,
        topic=topic or None,
        session_id=session_id or None,
    )


@mcp.tool()
def get_hint(question: str) -> dict:
    """A short hint for a question that doesn't give away the answer.
    Needs GROQ_API_KEY."""
    return tools.get_hint(_get_llm(), question)


@mcp.tool()
def record_attempt(
    session_id: str,
    topic: str,
    question: str,
    answer: str,
    feedback: str,
    is_correct: bool,
) -> dict:
    """Persist an answered question directly (if grading happened elsewhere)."""
    return tools.record_attempt(
        session_id, topic, question, answer, feedback, is_correct
    )


@mcp.tool()
def rate_question(topic: str, question: str, rating: str) -> dict:
    """Schedule a question's next spaced-repetition review.
    rating is one of Again / Hard / Good / Easy."""
    return tools.rate_question(topic, question, rating)


@mcp.tool()
def get_due_reviews(topic: str = "") -> list[dict]:
    """Questions whose spaced-repetition review date has arrived, most overdue first."""
    return tools.get_due_reviews(topic=topic or None)


@mcp.tool()
def get_progress() -> dict:
    """All-time totals and the weakest topics by accuracy."""
    return tools.get_progress()


# ── resources ──────────────────────────────────────────────────────────

@mcp.resource("interview://topics")
def topics_resource() -> str:
    """The topic list as plain text."""
    return "\n".join(TOPICS)


@mcp.resource("interview://progress")
def progress_resource() -> str:
    """A Markdown progress report."""
    s = tools.get_progress()
    lines = [
        "# Java Interview Coach — progress",
        "",
        f"- Sessions: {s['total_sessions']}",
        f"- Questions answered: {s['total_questions']}",
        f"- Correct: {s['total_correct']}",
        f"- Weakest topics: {', '.join(s['weakest_topics']) or '—'}",
        "",
        "| Topic | Attempts | Accuracy |",
        "|---|---:|---:|",
    ]
    for topic, st in sorted(s["topic_stats"].items()):
        lines.append(f"| {topic} | {st['total']} | {st['accuracy']:.0%} |")
    return "\n".join(lines)


@mcp.resource("interview://question-bank/{topic}")
def question_bank_resource(topic: str) -> str:
    """Every question in the bank for one topic (raw, no selection)."""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "questions_db.json"
    if not path.exists():
        return (
            "questions_db.json is not built yet — run rag.ipynb once to fetch "
            "the question bank (see README.md)."
        )
    bank = json.loads(path.read_text())
    questions = bank.get(topic)
    if questions is None:
        return f"Unknown topic {topic!r}. Known: {', '.join(bank)}"
    return "\n".join(f"- {q}" for q in questions)


# ── prompts ────────────────────────────────────────────────────────────

@mcp.prompt()
def mock_interview(topic: str = "auto", num_questions: int = 5) -> str:
    """Template: run a full mock interview using this server's tools."""
    ask = 'get_interview_question with mode="auto"' if topic == "auto" else "get_interview_question"
    return (
        f"Act as a Java technical interviewer. Run a {num_questions}-question "
        f"mock interview on the topic '{topic}'.\n\n"
        "1. Call start_session first.\n"
        f"2. For each question: call {ask}, present it, wait for my answer, then "
        "call evaluate_answer with the topic and session_id so it counts toward "
        "my progress.\n"
        "3. Only call get_hint if I explicitly ask for one.\n"
        "4. After the last question, call get_progress and summarize how I did "
        "and which topics to focus on.\n"
        "5. Offer to rate_question any questions I want scheduled for review."
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="mcp_server", description=__doc__)
    parser.add_argument(
        "--http",
        action="store_true",
        help="serve over streamable-HTTP instead of stdio",
    )
    args = parser.parse_args()
    mcp.run(transport="streamable-http" if args.http else "stdio")


if __name__ == "__main__":
    main()
