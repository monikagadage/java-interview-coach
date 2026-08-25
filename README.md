# ☕ Java Interview Coach
### *An AI-powered interview prep agent built with LangChain + LangGraph + Groq + RAG*

---

```
  ╔══════════════════════════════════════════════════════════════════╗
  ║   Search DB  →  Ask  →  Answer  →  Evaluate  →  Hint  →  Score ║
  ╚══════════════════════════════════════════════════════════════════╝
```

> **Stop cramming. Start practicing.**
> Get real Java interview questions from 600+ analyzed interviews, instant AI feedback, and personalized weak-spot tracking — all in a beautiful web UI.

---

## ✨ Features

- 🎯 **RAG-powered questions** — 1,715 real questions sourced from 600 Java interviews on YouTube
- 🔍 **Semantic search** — ChromaDB finds the most relevant question for your chosen topic
- 🤖 **AI evaluation** — instant feedback + ideal answer after every response
- 💡 **Hint system** — stuck? click "Get Hint" for a nudge without giving away the answer
- 📊 **Live scoring** — track correct answers in real time
- 📚 **Weak topic tracker** — see which topics to review at the end of each session
- 🗄️ **Cross-session persistence** — every answer is saved to a local SQLite database, so weak-topic tracking and scoring accumulate across your whole practice history, not just one sitting
- 📈 **Difficulty-adaptive selection** — a ranking layer on top of RAG retrieval that leans toward your weaker topics and raises/lowers question difficulty based on your saved accuracy per topic
- 📄 **Exportable session report** — download a Markdown report of any session (questions, your answers, ideal answers, scores, weak topics) straight from the sidebar
- ⚡ **Powered by Groq** — blazing fast LLM responses (no OpenAI costs!)
- 🌐 **Streamlit UI** — clean, interactive web interface

---

## 🧠 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      RAG Pipeline                           │
│                                                             │
│   1715 Java Questions (GitHub)                              │
│          ↓ embedded via ChromaDB                            │
│   Vector Store (ChromaDB)                                   │
│          ↓ semantic search by topic (~12 candidates)        │
│   Difficulty-Adaptive Selection (graph/selection.py)         │
│          ↓ ranked by saved per-topic accuracy                │
│   Question Selected                                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                   LangGraph Workflow                         │
│                                                             │
│   [START] → [RAG: Get Question] → [User Answers]           │
│                                         ↓                   │
│                               [Evaluate Answer]             │
│                              ↙      ↓        ↘             │
│                        [Hint]  [Next Q]     [End]           │
│                           ↘      ↑                          │
│                            └─────┘                          │
│                     ↓ every evaluated answer                │
│              SQLite (memory/store.py)                        │
│                     ↓                                        │
│          Cumulative Stats + Markdown Report                  │
└─────────────────────────────────────────────────────────────┘
```

**Stack:**
| Layer | Tech |
|---|---|
| LLM | `llama-3.3-70b` via Groq |
| Agent Framework | LangChain + LangGraph |
| Vector Store | ChromaDB |
| Question Bank | 1,715 questions from 600 real interviews |
| State Management | LangGraph `TypedDict` state |
| Persistence | SQLite (stdlib `sqlite3`, no ORM) |
| UI | Streamlit |
| Environment | Python 3.11, uv |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) package manager
- [Groq API key](https://console.groq.com) (free tier)

### Installation

```bash
# Clone the repo
git clone https://github.com/monikagadage/java-interview-coach.git
cd java-interview-coach

# Create virtual environment
uv venv
source .venv/bin/activate  # Mac/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
uv add -r requirements.txt
```

### Configuration

Create a `.env` file in the root directory:

```bash
GROQ_API_KEY=your_groq_api_key_here
```

> ⚠️ **Never commit your `.env` file.** It's already in `.gitignore`.

### Build the Question Bank

Run all cells in `rag.ipynb` once to fetch and store questions in ChromaDB:

```bash
# Open in VS Code and run all cells
code rag.ipynb
```

This fetches 1,715 questions from GitHub and stores them as vector embeddings locally.

### Run the App

```bash
.venv/bin/streamlit run app.py
```

Opens at `http://localhost:8501` 🚀

---

## 🎮 How to Use

```
☕ Java Interview Coach

Choose a topic: Spring

📌 Question:
What is Dependency Injection in Spring?

Your answer: [type here]

[✅ Submit Answer]  [💡 Get Hint]

💡 Hint:
Think about how Spring manages object creation and
how components get their dependencies...

💬 Feedback:
CORRECT! Dependency Injection is a design pattern where
Spring manages object creation and injects dependencies
automatically via @Autowired or constructor injection...

⭐ Score: 3/4        [➡️ Next Question]
```

The sidebar also shows your **all-time progress** ("You've answered 47 questions
across 6 sessions, weakest topics: ...") pulled from the local SQLite history, and
a **📄 Export Session Report** button that downloads a Markdown summary of the
current session (questions, your answers, ideal answers, scores, weak topics).
Pick **🎯 Auto (focus on my weak topics)** as the topic to let the app weight
topic selection toward whatever you've historically gotten wrong.

---

## 📁 Project Structure

```
java-interview-coach/
│
├── app.py                  # Streamlit web UI
├── report.py                # Exportable Markdown session report
├── main.ipynb              # Agent notebook (LangGraph flow)
├── rag.ipynb               # RAG setup — fetch + embed questions
├── pyproject.toml          # Project config
├── uv.lock                 # Locked dependency versions
├── .env                    # API keys (never commit!)
├── interview_history.db     # SQLite practice history (gitignored, auto-created)
├── .gitignore
│
├── graph/
│   ├── state.py             # LangGraph shared state definition
│   ├── workflow.py          # Agent nodes (RAG get-question, evaluate, hint) + graph wiring
│   └── selection.py         # Difficulty-adaptive ranking layer on top of RAG retrieval
│
└── memory/
    └── store.py              # SQLite persistence — questions, correctness, topic, timestamp
```

---

## 🗺️ Roadmap

- [x] Basic question → evaluate chain
- [x] LangGraph state + workflow
- [x] Hint system
- [x] Weak topic tracker
- [x] RAG with ChromaDB — 1,715 real interview questions
- [x] Streamlit web UI
- [x] Multi-session memory (persist weak topics + scores across sessions via SQLite)
- [x] Difficulty-adaptive question selection based on saved per-topic accuracy
- [x] Exportable Markdown session report
- [ ] Deploy to Hugging Face Spaces

---

## 🛠️ Built With

- [LangChain](https://python.langchain.com/) — LLM orchestration
- [LangGraph](https://langchain-ai.github.io/langgraph/) — Agentic workflow graph
- [Groq](https://groq.com/) — Fast, free LLM inference
- [ChromaDB](https://www.trychroma.com/) — Vector store for semantic search
- [Streamlit](https://streamlit.io/) — Web UI framework
- [python-dotenv](https://pypi.org/project/python-dotenv/) — Environment management
- [uv](https://github.com/astral-sh/uv) — Fast Python package manager

---

## 👩‍💻 Author

**Monika Gadage**
Java/Spring Boot Developer | AI/ML Learner
[GitHub](https://github.com/monikagadage)

---

<div align="center">

*Built as part of a hands-on AI/ML learning journey*
*From LangChain basics → LangGraph agents → RAG → Production deployment*

☕ **Practice daily. Land the role.**

</div>