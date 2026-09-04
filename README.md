# Java Interview Coach

[![CI](https://github.com/monikagadage/java-interview-coach/actions/workflows/ci.yml/badge.svg)](https://github.com/monikagadage/java-interview-coach/actions/workflows/ci.yml)

A Java interview-practice tool built around a **retrieval + adaptive-selection
pipeline**: semantic search over 1,715 real interview questions finds a
relevant pool, then a difficulty- and history-aware ranker decides which one
to actually ask. An LLM grades each answer against an ideal answer. Every
attempt is persisted, so weak-topic weighting and a spaced-repetition
schedule accumulate across sessions.

Three front-ends drive the identical core: a **Streamlit UI**, a **headless
CLI**, and an **MCP server** ([Model Context Protocol](https://modelcontextprotocol.io))
that exposes the whole coach as tools any MCP client — Claude Desktop, Claude
Code, Cursor, VS Code — can run mock interviews against.

## The pipeline

```
topic ─▶ ChromaDB semantic search ─▶ candidate pool ─▶ selection.py ─▶ question
                                                          │
        history (SQLite) ────────────────────────────────┤  difficulty re-rank,
                                                          │  recency filter,
        answer ─▶ LangGraph evaluate node (LLM) ─▶ score ─┘  weak-topic weighting
                        │
                        ▼
        attempt persisted ─▶ cumulative stats + spaced-repetition schedule
```

## Design decisions

| Decision | Why |
|---|---|
| **Selection layered on top of RAG, not replacing it** | Vector search is good at "relevant to this topic," bad at "the right difficulty for this user right now." `graph/selection.py` takes the retrieved pool and re-ranks it against persisted per-topic accuracy, so retrieval stays simple and the adaptivity is testable in isolation (no vector store needed). |
| **Difficulty is an explicit heuristic, labelled as a proxy** | The 1,715-question bank has no difficulty labels. `_estimate_difficulty` approximates it from question length and phrasing ("why"/"how does X work"/internals vs. "what is"/"define"). Called out in code and docs so it isn't mistaken for ground truth. |
| **Persistence is stdlib `sqlite3`, no ORM** | `st.session_state` dies with the process. `memory/store.py` writes every attempt (topic, question, correctness, timestamp, session id) so stats survive restarts. One small module, one file, fully unit-tested against temp DBs. |
| **One core, three front-ends** | `app.py` (Streamlit), `cli.py`, and `mcp_server/` all drive the same `graph/` + `memory/` modules — no business logic behind a Streamlit import. `mcp_server/tools.py` holds the tool logic as dependency-injected plain functions (kept off the LangChain/ChromaDB import chain), so it's unit-tested with just `pytest`; `mcp_server/server.py` is the only file that touches the MCP wire protocol. |
| **Spaced repetition on the same file** | A post-answer confidence rating (Again/Hard/Good/Easy) schedules that exact question 1/3/7/14 days out; "Due for Review" mode resurfaces what's due instead of pulling from RAG. |

See [DESIGN.md](DESIGN.md) for the full architecture and data model.

## Quick start

**Prerequisites:** Python 3.11+, [`uv`](https://github.com/astral-sh/uv), a
[Groq API key](https://console.groq.com) (free tier).

```bash
uv sync
echo "GROQ_API_KEY=your_key_here" > .env

# Build the question bank (fetches 1,715 questions -> questions_db.json)
jupyter execute rag.ipynb

uv run streamlit run app.py     # http://localhost:8501
```

**Auto** mode weights toward weaker topics; **Due for Review** pulls from the
spaced-repetition schedule.

## CLI practice mode

```bash
uv run python cli.py                        # auto topic, until you type 'quit'
uv run python cli.py --topic OOP --questions 3
echo "my answer\n\nquit" | uv run python cli.py --questions 5   # scripted
```

Same prerequisites and same persistence as the Streamlit app — CLI and UI
sessions share stats.

## MCP server

Exposes the coach over the [Model Context Protocol](https://modelcontextprotocol.io)
so any MCP client can use it as a tool.

```bash
uv run python -m mcp_server          # stdio (for Claude Desktop / Cursor / VS Code)
uv run python -m mcp_server --http   # streamable-HTTP on 127.0.0.1:8000/mcp
```

**Tools:** `list_topics`, `start_session`, `get_interview_question` (RAG +
adaptive selection), `evaluate_answer`, `get_hint`, `record_attempt`,
`rate_question`, `get_due_reviews`, `get_progress`.
**Resources:** `interview://topics`, `interview://progress`,
`interview://question-bank/{topic}`.
**Prompt:** `mock_interview(topic, num_questions)` — a template that drives a
full session through the tools.

The ChromaDB collection and the Groq client are built lazily, so `list_tools`
and the store-backed tools respond instantly. `evaluate_answer` / `get_hint`
need `GROQ_API_KEY`; without it they return a clear message and everything
else still works.

<details>
<summary>Claude Desktop / Cursor config</summary>

`claude_desktop_config.json` (or `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "java-interview-coach": {
      "command": "uv",
      "args": ["--directory", "/ABS/PATH/TO/java-interview-coach", "run", "python", "-m", "mcp_server"],
      "env": { "GROQ_API_KEY": "your_key_here" }
    }
  }
}
```

Claude Code: `claude mcp add java-interview-coach -- uv --directory /ABS/PATH run python -m mcp_server`
</details>

## Tests

```bash
uv run pytest tests/            # 61 tests
```

- `test_store.py` — session/attempt CRUD, cumulative stats, recent-question
  filtering, spaced-repetition interval math, upsert-on-rerate, due-question
  ordering (all against temp SQLite files).
- `test_selection.py` — difficulty heuristic, difficulty re-ranking,
  recently-asked filtering, auto-topic weighting.
- `test_mcp_tools.py` — every MCP tool via a fake collection / fake LLM and a
  temp DB.
- `test_mcp_server.py` — the FastMCP wiring: all tools/resources/prompt
  registered, graceful error without `GROQ_API_KEY`.
- `test_cli.py` — `cli.py`'s stdin-parsing helper.

Everything except `test_cli.py` runs with just `pytest` + the (lightweight)
`mcp` SDK — no ChromaDB, Groq key, or network — which is what CI runs on 3.11
and 3.12. `test_cli.py` self-skips unless the full app stack is installed.

## Tech stack

| Layer | Tech |
|---|---|
| LLM | `llama-3.3-70b` via Groq |
| Agent framework | LangChain + LangGraph |
| Vector store | ChromaDB |
| Persistence | SQLite (stdlib `sqlite3`) |
| Front-ends | Streamlit · CLI · MCP server (`mcp` SDK, FastMCP) |
| Env / packaging | Python 3.11, `uv` |

## Project structure

```
app.py            Streamlit UI, wires graph nodes to session state
cli.py            headless practice loop: ask -> answer -> evaluate -> score
topics.py         the fixed topic list, shared by every front-end
prompts.py        evaluate / hint prompt text, shared by workflow.py and mcp_server
corpus.py         shared ChromaDB collection loader
report.py         exportable Markdown session report
rag.ipynb         fetches + parses the question corpus into questions_db.json
graph/
  state.py        shared LangGraph state (TypedDict)
  workflow.py     node factories + compiled graph (ask / evaluate / hint)
  selection.py    difficulty-adaptive re-ranking on top of RAG retrieval
memory/
  store.py        SQLite persistence for sessions / attempts / reviews + stats
mcp_server/
  tools.py        tool logic as dependency-injected plain functions
  server.py       FastMCP wiring (tools / resources / prompt) + lazy deps
  __main__.py     `python -m mcp_server [--http]`
tests/            pytest suite (see above)
```

## Author

**Monika Gadage** — [GitHub](https://github.com/monikagadage)
