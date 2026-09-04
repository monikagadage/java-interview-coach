"""The FastMCP wiring: every tool/resource/prompt is registered, and the
store-backed tools work end to end through the server layer.

Skips cleanly if the `mcp` SDK isn't installed (the pytest-only CI job).
"""
from __future__ import annotations

import pytest

pytest.importorskip("mcp", reason="the mcp SDK isn't installed")

from mcp_server import server  # noqa: E402


EXPECTED_TOOLS = {
    "list_topics", "start_session", "get_interview_question", "evaluate_answer",
    "get_hint", "record_attempt", "rate_question", "get_due_reviews", "get_progress",
}


def test_all_expected_tools_are_registered():
    names = {t.name for t in server.mcp._tool_manager.list_tools()}
    assert EXPECTED_TOOLS <= names


def test_resources_and_prompt_are_registered():
    templates = {t.uri_template for t in server.mcp._resource_manager.list_templates()}
    fixed = {str(r.uri) for r in server.mcp._resource_manager.list_resources()}
    assert "interview://question-bank/{topic}" in templates
    assert {"interview://topics", "interview://progress"} <= fixed
    assert "mock_interview" in {p.name for p in server.mcp._prompt_manager.list_prompts()}


def test_grading_tool_gives_a_clear_error_without_a_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    server._llm = None
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        server.get_hint("What is a JVM?")


def test_question_bank_resource():
    from pathlib import Path

    real = Path(server.__file__).resolve().parent.parent / "questions_db.json"
    text = server.question_bank_resource("OOP")
    if real.exists():
        assert text.startswith("- ") or "Unknown topic" in text
    else:
        # No bank built here — the resource says so instead of raising.
        assert "not built yet" in text


def test_progress_resource_renders_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr("memory.store.DB_PATH", tmp_path / "h.db")
    out = server.progress_resource()
    assert out.startswith("# Java Interview Coach")
