"""Shared LangGraph state for the interview workflow.

Mirrors the state shape explored in ``graph/state.ipynb`` /
``graph/workflow.ipynb``, promoted to a real module so ``graph/workflow.py``
and ``app.py`` can import it directly instead of duplicating the TypedDict.
"""
from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class InterviewState(TypedDict):
    topic: str
    current_question: str
    user_answer: str
    feedback: str
    score: int
    total_questions: int
    needs_hint: bool
    hint: str
    weak_topics: list[str]
    next_action: str
    session_id: str
    messages: Annotated[list, add_messages]
