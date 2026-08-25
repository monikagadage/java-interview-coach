import json

import chromadb
import streamlit as st
from dotenv import load_dotenv
from langchain_groq import ChatGroq

from graph.workflow import build_nodes
from graph.selection import pick_topic_for_auto_mode
from memory import store
from report import build_session_report

load_dotenv()

# ── Page config ───────────────────────────────────────────
st.set_page_config(page_title="☕ Java Interview Coach", page_icon="☕")
st.title("☕ Java Interview Coach")
st.caption("Practice Java interview questions with AI feedback")

# ── LLM ──────────────────────────────────────────────────
llm = ChatGroq(model="llama-3.3-70b-versatile")

# ── ChromaDB setup (RAG) ────────────────────────────────────
@st.cache_resource
def load_vector_db():
    client = chromadb.Client()
    collection = client.get_or_create_collection(name="java_questions")

    # Only load if empty
    if collection.count() == 0:
        with open("questions_db.json", "r") as f:
            questions_by_topic = json.load(f)

        documents, metadatas, ids = [], [], []
        idx = 0
        for topic, qs in questions_by_topic.items():
            for question in qs:
                documents.append(question)
                metadatas.append({"topic": topic})
                ids.append(f"q_{idx}")
                idx += 1

        # Store in batches
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            collection.add(
                documents=documents[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size],
                ids=ids[i:i+batch_size]
            )

    return collection


collection = load_vector_db()

# ── LangGraph nodes (RAG retrieval + adaptive selection -> evaluate -> hint) ──
@st.cache_resource
def get_nodes(_collection, _llm):
    return build_nodes(_collection, _llm)


nodes = get_nodes(collection, llm)

AUTO_TOPIC_LABEL = "🎯 Auto (focus on my weak topics)"
TOPICS = [
    "OOP", "Java Core", "Java Collections", "Spring",
    "JVM", "Multithreading", "Databases", "Java 8",
    "Patterns", "Testing"
]

# ── Session state ─────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = store.start_session()
if "question" not in st.session_state:
    st.session_state.question = ""
if "active_topic" not in st.session_state:
    st.session_state.active_topic = ""
if "feedback" not in st.session_state:
    st.session_state.feedback = ""
if "hint" not in st.session_state:
    st.session_state.hint = ""
if "score" not in st.session_state:
    st.session_state.score = 0
if "total" not in st.session_state:
    st.session_state.total = 0
if "weak_topics" not in st.session_state:
    st.session_state.weak_topics = []

# ── UI ────────────────────────────────────────────────────
topic_choice = st.selectbox("Choose a topic:", [AUTO_TOPIC_LABEL] + TOPICS)
st.caption(
    "💡 Question difficulty adapts to your saved accuracy on this topic — "
    "it gets harder as you improve, and eases up while you're still shaky."
)

if st.button("🎯 Generate Question"):
    topic = (
        pick_topic_for_auto_mode(TOPICS, db_path=store.DB_PATH)
        if topic_choice == AUTO_TOPIC_LABEL
        else topic_choice
    )
    with st.spinner("Searching question bank..."):
        state = {"topic": topic, "total_questions": st.session_state.total}
        result = nodes["ask"](state)
        st.session_state.question = result["current_question"]
        st.session_state.active_topic = topic
        st.session_state.feedback = ""
        st.session_state.hint = ""

if st.session_state.question:
    st.markdown("---")
    if st.session_state.active_topic:
        st.caption(f"Topic: {st.session_state.active_topic}")
    st.markdown(f"### 📌 Question:\n{st.session_state.question}")

    answer = st.text_area("Your answer:", height=100)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Submit Answer"):
            if answer.strip():
                with st.spinner("Evaluating..."):
                    state = {
                        "topic": st.session_state.active_topic,
                        "current_question": st.session_state.question,
                        "user_answer": answer,
                        "score": st.session_state.score,
                        "weak_topics": st.session_state.weak_topics,
                        "session_id": st.session_state.session_id,
                    }
                    result = nodes["evaluate"](state)
                    st.session_state.feedback = result["feedback"]
                    st.session_state.score = result["score"]
                    st.session_state.weak_topics = result["weak_topics"]
                    st.session_state.total += 1
            else:
                st.warning("Please type an answer first!")

    with col2:
        if st.button("💡 Get Hint"):
            with st.spinner("Getting hint..."):
                state = {"current_question": st.session_state.question}
                result = nodes["hint"](state)
                st.session_state.hint = result["hint"]

    if st.session_state.hint:
        st.info(f"💡 **Hint:** {st.session_state.hint}")

    if st.session_state.feedback:
        if st.session_state.feedback.strip().upper().startswith("CORRECT"):
            st.success(st.session_state.feedback)
        else:
            st.error(st.session_state.feedback)

        if st.button("➡️ Next Question"):
            topic = (
                pick_topic_for_auto_mode(TOPICS, db_path=store.DB_PATH)
                if topic_choice == AUTO_TOPIC_LABEL
                else topic_choice
            )
            with st.spinner("Searching next question..."):
                state = {"topic": topic, "total_questions": st.session_state.total}
                result = nodes["ask"](state)
                st.session_state.question = result["current_question"]
                st.session_state.active_topic = topic
                st.session_state.feedback = ""
                st.session_state.hint = ""
                st.rerun()

# ── Sidebar ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 This Session")
    st.metric("Score", f"{st.session_state.score}/{st.session_state.total}")

    if st.session_state.weak_topics:
        st.markdown("### 📚 Topics to Review")
        for t in set(st.session_state.weak_topics):
            st.markdown(f"- {t}")

    st.markdown("---")
    st.markdown("## 📈 All-Time Progress")
    cumulative = store.get_cumulative_stats()
    st.caption(
        f"You've answered **{cumulative['total_questions']}** questions "
        f"across **{cumulative['total_sessions']}** session"
        f"{'s' if cumulative['total_sessions'] != 1 else ''}."
    )
    if cumulative["weakest_topics"]:
        st.markdown("**Weakest topics overall:**")
        for t in cumulative["weakest_topics"]:
            s = cumulative["topic_stats"][t]
            st.markdown(f"- {t} — {s['correct']}/{s['total']} correct")

    if cumulative["total_questions"] > 0:
        st.download_button(
            "📄 Export Session Report",
            data=build_session_report(st.session_state.session_id),
            file_name="interview_session_report.md",
            mime="text/markdown",
        )

    st.markdown("---")
    if st.button("🔄 Reset Session"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
