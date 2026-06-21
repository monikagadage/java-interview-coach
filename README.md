# ☕ Java Interview Coach
### *An AI-powered interview prep agent built with LangChain + LangGraph + Groq*

---

```
  ╔══════════════════════════════════════════════════════╗
  ║   Ask  →  Answer  →  Evaluate  →  Hint  →  Score   ║
  ╚══════════════════════════════════════════════════════╝
```

> **Stop cramming. Start practicing.**
> Get real Java interview questions, instant AI feedback, and personalized weak-spot tracking — all in your terminal.

---

## ✨ Features

- 🎯 **Topic-based questions** — OOP, Collections, JVM, Spring Boot, Multithreading & more
- 🤖 **AI evaluation** — instant feedback + ideal answer after every response
- 💡 **Hint system** — stuck? type `hint` instead of answering
- 📊 **Live scoring** — track correct answers in real time
- 📚 **Weak topic tracker** — see which topics to review at the end of each session
- ⚡ **Powered by Groq** — blazing fast LLM responses (no OpenAI costs!)

---

## 🧠 Architecture

```
┌─────────────────────────────────────────────────────┐
│                   LangGraph Workflow                 │
│                                                     │
│   [START] → [Ask Question] → [Get Answer]           │
│                                   ↓                 │
│                           [Evaluate Answer]         │
│                          ↙        ↓        ↘        │
│                    [Hint]    [Next Q]    [End]       │
│                       ↘        ↑                    │
│                        └───────┘                    │
└─────────────────────────────────────────────────────┘
```

**Stack:**
| Layer | Tech |
|---|---|
| LLM | `llama-3.3-70b` via Groq |
| Agent Framework | LangChain + LangGraph |
| State Management | LangGraph `TypedDict` state |
| Environment | Python 3.11, uv |
| Notebook | Jupyter in VS Code |

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
uv pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the root directory:

```bash
GROQ_API_KEY=your_groq_api_key_here
```

> ⚠️ **Never commit your `.env` file.** It's already in `.gitignore`.

### Run

Open `main.ipynb` in VS Code, select the `.venv` kernel, and run all cells!

---

## 🎮 How to Use

```
🎯 Java Interview Coach

Enter a topic: Spring Boot

📌 Question 1:
What is the purpose of @ComponentScan in Spring Boot?

Your answer (or type 'hint'): hint

💡 Hint:
Think about how Spring Boot knows which classes to register as beans...

Now your answer: It tells Spring where to look for components and beans to register

💬 Feedback:
CORRECT! Great answer. @ComponentScan tells Spring Boot which packages
to scan for @Component, @Service, @Repository annotations...

⭐ Score: 1/1

Next question? (y/n): y
```

---

## 📁 Project Structure

```
java-interview-coach/
│
├── main.ipynb              # Main notebook — run this!
├── requirements.txt        # Python dependencies
├── uv.lock                 # Locked dependency versions
├── .env                    # API keys (never commit!)
├── .gitignore
│
├── graph/
│   ├── state.py            # LangGraph shared state definition
│   └── workflow.py         # Agent nodes + graph wiring
│
├── agents/                 # (Phase 2 — individual agents)
├── tools/                  # (Phase 2 — custom tools)
└── memory/                 # (Phase 2 — session persistence)
```

---

## 🗺️ Roadmap

- [x] Basic question → evaluate chain
- [x] LangGraph state + workflow
- [x] Hint system
- [x] Weak topic tracker
- [ ] Streamlit UI
- [ ] Multi-session memory (persist weak topics across sessions)
- [ ] Deploy to Hugging Face Spaces

---

## 🛠️ Built With

- [LangChain](https://python.langchain.com/) — LLM orchestration
- [LangGraph](https://langchain-ai.github.io/langgraph/) — Agentic workflow graph
- [Groq](https://groq.com/) — Fast, free LLM inference
- [python-dotenv](https://pypi.org/project/python-dotenv/) — Environment management
- [uv](https://github.com/astral-sh/uv) — Fast Python package manager

---


---

<div align="center">


</div>