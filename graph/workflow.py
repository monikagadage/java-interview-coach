"""LangGraph workflow: RAG retrieval -> answer -> evaluate -> hint/next/end.

This formalizes what was previously only sketched in
``graph/workflow.ipynb`` into an importable module, and wires the "get
question" node up to the same ChromaDB collection ``app.py`` already builds
(RAG retrieval) plus the difficulty-adaptive ranking layer in
``graph/selection.py``, and records every evaluated answer to the
persistent store in ``memory/store.py``.

Node functions are produced by small factories (``make_*_node``) that close
over the ChromaDB collection / LLM instance instead of relying on module
globals. That keeps ``ask_question_node`` testable with no LLM/API key at
all — it only needs a Chroma collection — while ``evaluate_node`` and
``hint_node`` need a live ``llm``.

Streamlit drives this turn-by-turn (one button click = one node call), the
same way the notebook's ``run_interview()`` CLI loop calls nodes directly.
``build_graph`` additionally compiles the full LangGraph graph so the
ask -> evaluate -> (hint | ask | end) wiring exists as a real, runnable
graph for CLI-style or programmatic use.
"""
from __future__ import annotations

from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from graph.selection import select_question
from graph.state import InterviewState
from memory import store
from prompts import EVAL_PROMPT, HINT_PROMPT

# RAG candidates fetched per question before the adaptive layer ranks them.
QUESTION_POOL_SIZE = 12

eval_prompt = ChatPromptTemplate.from_template(EVAL_PROMPT)
hint_prompt = ChatPromptTemplate.from_template(HINT_PROMPT)


def retrieve_candidates(collection, topic: str, n_results: int = QUESTION_POOL_SIZE) -> list[str]:
    """Pure RAG step, unchanged: semantic search against ChromaDB."""
    results = collection.query(query_texts=[topic], n_results=n_results)
    documents = results.get("documents") or [[]]
    return documents[0]


def make_ask_question_node(collection, db_path: str | Path | None = None):
    """'Get question' node: RAG retrieval + adaptive selection on top of it."""

    def ask_question_node(state: InterviewState) -> dict:
        candidates = retrieve_candidates(collection, state["topic"])
        if not candidates:
            question = f"No questions found in the question bank for topic '{state['topic']}'."
        else:
            question = select_question(candidates, state["topic"], db_path=db_path)
        return {
            "current_question": question,
            "total_questions": state.get("total_questions", 0) + 1,
            "needs_hint": False,
            "hint": "",
        }

    return ask_question_node


def make_evaluate_node(llm, db_path: str | Path | None = None):
    eval_chain = eval_prompt | llm

    def evaluate_node(state: InterviewState) -> dict:
        response = eval_chain.invoke(
            {"question": state["current_question"], "answer": state["user_answer"]}
        )
        feedback = response.content
        is_correct = feedback.strip().upper().startswith("CORRECT")

        score = state.get("score", 0) + (1 if is_correct else 0)
        weak_topics = state.get("weak_topics", [])
        if not is_correct:
            weak_topics = weak_topics + [state["topic"]]

        if state.get("session_id"):
            store.record_attempt(
                session_id=state["session_id"],
                topic=state["topic"],
                question=state["current_question"],
                answer=state["user_answer"],
                feedback=feedback,
                is_correct=is_correct,
                db_path=db_path,
            )

        return {"feedback": feedback, "score": score, "weak_topics": weak_topics}

    return evaluate_node


def make_hint_node(llm):
    hint_chain = hint_prompt | llm

    def hint_node(state: InterviewState) -> dict:
        response = hint_chain.invoke({"question": state["current_question"]})
        return {"hint": response.content}

    return hint_node


def end_node(state: InterviewState) -> dict:
    return {"next_action": "end"}


def router(state: InterviewState) -> str:
    action = state.get("next_action", "ask")
    if action == "end":
        return "end"
    if action == "hint":
        return "hint"
    if action == "evaluate":
        return "evaluate"
    return "ask"


def build_nodes(collection, llm, db_path: str | Path | None = None) -> dict:
    """Individual node callables for turn-by-turn driving (e.g. from Streamlit)."""
    return {
        "ask": make_ask_question_node(collection, db_path=db_path),
        "evaluate": make_evaluate_node(llm, db_path=db_path),
        "hint": make_hint_node(llm),
        "end": end_node,
    }


def build_graph(collection, llm, db_path: str | Path | None = None):
    """Compile the full interview LangGraph: ask -> evaluate -> (hint | ask | end)."""
    nodes = build_nodes(collection, llm, db_path=db_path)

    graph = StateGraph(InterviewState)
    graph.add_node("ask", nodes["ask"])
    graph.add_node("evaluate", nodes["evaluate"])
    graph.add_node("hint", nodes["hint"])
    graph.add_node("end", nodes["end"])

    graph.set_entry_point("ask")
    graph.add_edge("ask", "evaluate")
    graph.add_conditional_edges(
        "evaluate", router, {"ask": "ask", "hint": "hint", "end": END}
    )
    graph.add_edge("hint", "evaluate")

    return graph.compile()
