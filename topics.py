"""The fixed topic list, shared by every front-end (Streamlit, CLI, MCP).

Kept in one module so adding a topic is a one-line change and the CLI, the
MCP server, and auto-mode weighting can't drift out of sync.
"""
from __future__ import annotations

AUTO = "auto"

TOPICS: list[str] = [
    "OOP",
    "Java Core",
    "Java Collections",
    "Spring",
    "JVM",
    "Multithreading",
    "Databases",
    "Java 8",
    "Patterns",
    "Testing",
]
