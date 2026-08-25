# ☕ Java Interview Coach

An AI-powered Java interview prep tool: practice real interview questions, get instant AI
feedback, and track weak spots across sessions — all in a Streamlit UI.

## Features

- **RAG-powered questions** — semantic search (ChromaDB) over 1,715 real Java interview
  questions, sourced from an analysis of 600 YouTube interviews
- **AI evaluation & hints** — Groq (`llama-3.3-70b`) grades each answer against an ideal
  answer and can give an on-demand hint
- **Difficulty-adaptive selection** — re-ranks the retrieved candidates against your saved
  per-topic accuracy, and skips questions you were asked recently
- **Cross-session persistence** — every attempt is saved to a local SQLite database, so
  scoring and weak-topic tracking accumulate across restarts, not just one sitting
- **Exportable session report** — download a Markdown summary of a session's questions,
  answers, and feedback

See [DESIGN.md](DESIGN.md) for the architecture, workflow, and data model.

## Quick Start

**Prerequisites:** Python 3.11+, [`uv`](https://github.com/astral-sh/uv), a
[Groq API key](https://console.groq.com) (free tier).

```bash
# Install dependencies
uv sync

# Set your API key
echo "GROQ_API_KEY=your_key_here" > .env

# Build the question bank (fetches 1,715 questions, writes questions_db.json)
# — open rag.ipynb and run all cells once
jupyter execute rag.ipynb   # or: run all cells in an editor

# Run the app
uv run streamlit run app.py
```

Opens at `http://localhost:8501`. Pick a topic (or **Auto**, which weights toward your
weaker topics), answer, and check the sidebar for live and all-time progress.

## Tech Stack

| Layer | Tech |
|---|---|
| LLM | `llama-3.3-70b` via Groq |
| Agent framework | LangChain + LangGraph |
| Vector store | ChromaDB |
| Persistence | SQLite (stdlib `sqlite3`) |
| UI | Streamlit |
| Env / packaging | Python 3.11, `uv` |

## Project Structure

```
app.py              # Streamlit UI, wires graph nodes to session state
report.py           # Exportable Markdown session report
rag.ipynb           # Fetches + parses the question corpus into questions_db.json
main.ipynb          # Early notebook exploration of the ask/evaluate chain
graph/
  state.py          # Shared LangGraph state (TypedDict)
  workflow.py        # Node factories + compiled graph (ask/evaluate/hint)
  selection.py       # Difficulty-adaptive re-ranking on top of RAG retrieval
memory/
  store.py           # SQLite persistence for sessions/attempts + stats
```

## Author

**Monika Gadage** — Java/Spring Boot Developer, AI/ML Learner —
[GitHub](https://github.com/monikagadage)
