"""Tests for cli.py's pure stdin-parsing helper.

``cli.main()`` itself does real I/O (ChromaDB embedding, a live Groq call)
so it isn't unit tested here — see DESIGN.md for how it was verified by
hand. ``_prompt_answer`` is the one piece of cli.py with no I/O side
effects beyond reading stdin, so it's covered directly by feeding it a
fake stdin via monkeypatching ``builtins.input``.
"""
from __future__ import annotations

import builtins

import pytest

# cli.py imports the full app stack (corpus -> chromadb, graph.workflow ->
# langchain) at module load, even though _prompt_answer itself needs none of
# it. Skip cleanly when those deps aren't installed (e.g. a lint-only CI job).
cli = pytest.importorskip("cli", reason="cli.py needs the full app dependencies")


def _fake_input(lines: list[str]):
    it = iter(lines)

    def _input():
        try:
            return next(it)
        except StopIteration:
            raise EOFError

    return _input


def test_prompt_answer_single_line(monkeypatch):
    monkeypatch.setattr(builtins, "input", _fake_input(["Encapsulation hides state.", ""]))
    assert cli._prompt_answer() == "Encapsulation hides state."


def test_prompt_answer_multi_line_joined_with_newline(monkeypatch):
    monkeypatch.setattr(
        builtins, "input", _fake_input(["Line one.", "Line two.", ""])
    )
    assert cli._prompt_answer() == "Line one.\nLine two."


def test_prompt_answer_quit_sentinel_passthrough(monkeypatch):
    # 'quit' is treated like any other line by _prompt_answer itself --
    # the caller (run_session) is what special-cases it.
    monkeypatch.setattr(builtins, "input", _fake_input(["quit", ""]))
    assert cli._prompt_answer() == "quit"


def test_prompt_answer_returns_none_on_immediate_eof(monkeypatch):
    """Piped stdin that's already exhausted must stop the session cleanly,
    not be treated as a deliberately blank answer."""
    monkeypatch.setattr(builtins, "input", _fake_input([]))
    assert cli._prompt_answer() is None


def test_prompt_answer_eof_after_some_lines_still_returns_them(monkeypatch):
    """EOF mid-answer (no trailing blank line) still submits what was typed."""
    monkeypatch.setattr(builtins, "input", _fake_input(["Partial answer"]))
    assert cli._prompt_answer() == "Partial answer"
