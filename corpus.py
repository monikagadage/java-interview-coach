"""Shared ChromaDB collection loader for both app.py (Streamlit) and cli.py.

Extracted in round 2 so the "load the question corpus into ChromaDB" step
isn't duplicated between the two UIs. ``app.py`` wraps ``load_collection``
in ``@st.cache_resource`` (a Streamlit-only concern); ``cli.py`` calls it
directly. Both end up exercising the exact same retrieval setup.
"""
from __future__ import annotations

import json
from pathlib import Path

import chromadb

QUESTIONS_DB_PATH = Path(__file__).resolve().parent / "questions_db.json"


def load_collection(questions_path: str | Path = QUESTIONS_DB_PATH):
    """Return a ChromaDB collection of the question bank, embedding it on
    first use (in-memory, ephemeral client — see DESIGN.md for why)."""
    client = chromadb.Client()
    collection = client.get_or_create_collection(name="java_questions")

    if collection.count() == 0:
        with open(questions_path, "r") as f:
            questions_by_topic = json.load(f)

        documents, metadatas, ids = [], [], []
        idx = 0
        for topic, qs in questions_by_topic.items():
            for question in qs:
                documents.append(question)
                metadatas.append({"topic": topic})
                ids.append(f"q_{idx}")
                idx += 1

        batch_size = 100
        for i in range(0, len(documents), batch_size):
            collection.add(
                documents=documents[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size],
                ids=ids[i:i + batch_size],
            )

    return collection
