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
- **Spaced-repetition review** — rate your confidence (Again/Hard/Good/Easy) after each
  answer to schedule that exact question's next review 1/3/7/14 days out; a "Due for
  Review" mode resurfaces whatever has come due instead of pulling from RAG/topic selection

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

Opens at `http://localhost:8501`. Pick a topic (**Auto** weights toward your weaker
topics; **Due for Review** resurfaces questions from your spaced-repetition schedule),
answer, rate your confidence, and check the sidebar for live and all-time progress.

## CLI Practice Mode

The same ask → evaluate → score flow, no Streamlit, no browser — useful for
scripted/automated practice and as proof the business logic doesn't secretly depend on the
UI (`app.py` and `cli.py` both call the exact same `graph`/`memory` modules):

```bash
uv run python cli.py                       # auto topic, runs until you type 'quit'
uv run python cli.py --topic OOP --questions 3
```

Needs the same prerequisites as the Streamlit app (`questions_db.json`, `GROQ_API_KEY`).
Answers are multi-line — type your answer, then a blank line to submit; type `quit` instead
to stop early. Piped/scripted input works the same way (a blank line submits, EOF stops the
session cleanly). Every attempt is persisted through `memory/store.py` exactly like the
Streamlit app, so CLI and Streamlit sessions share the same cross-session stats.

## Tests

```bash
uv run pytest tests/ -v
```

45 tests cover `memory/store.py` (session/attempt CRUD, cumulative stats, recent-question
filtering, and spaced-repetition scheduling — interval math, upsert-on-rerate, due-question
filtering/ordering — all against temp SQLite files), `graph/selection.py` (difficulty
heuristic, difficulty re-ranking, recently-asked filtering, auto-topic weighting), and
`cli.py`'s stdin-parsing helper. No ChromaDB instance, Groq key, or network access is
needed to run them — `selection.py` operates on plain candidate lists, not a live vector
store, and `cli.py`'s tests only exercise its pure stdin parsing.

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
cli.py              # CLI practice mode: ask -> answer -> evaluate -> score, no Streamlit
corpus.py           # Shared ChromaDB collection loader (used by app.py and cli.py)
report.py           # Exportable Markdown session report
rag.ipynb           # Fetches + parses the question corpus into questions_db.json
main.ipynb          # Early notebook exploration of the ask/evaluate chain
graph/
  state.py          # Shared LangGraph state (TypedDict)
  workflow.py        # Node factories + compiled graph (ask/evaluate/hint)
  selection.py       # Difficulty-adaptive re-ranking on top of RAG retrieval
memory/
  store.py           # SQLite persistence for sessions/attempts/reviews + stats
tests/
  test_store.py       # memory/store.py: CRUD, cumulative stats, spaced repetition
  test_selection.py    # graph/selection.py: difficulty ranking, recency filter
  test_cli.py           # cli.py: stdin-parsing helper
```

## Author

**Monika Gadage** — Java/Spring Boot Developer, AI/ML Learner —
[GitHub](https://github.com/monikagadage)
