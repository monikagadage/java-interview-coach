import streamlit as st
from dotenv import load_dotenv
from langchain_groq import ChatGroq

from corpus import load_collection
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
# The actual load/embed logic lives in corpus.py (shared with cli.py);
# this just adds Streamlit's process-lifetime caching on top of it.
load_vector_db = st.cache_resource(load_collection)
collection = load_vector_db()

# ── LangGraph nodes (RAG retrieval + adaptive selection -> evaluate -> hint) ──
@st.cache_resource
def get_nodes(_collection, _llm):
    return build_nodes(_collection, _llm)


nodes = get_nodes(collection, llm)

AUTO_TOPIC_LABEL = "🎯 Auto (focus on my weak topics)"
DUE_REVIEW_LABEL = "🔁 Due for Review"
TOPICS = [
    "OOP", "Java Core", "Java Collections", "Spring",
    "JVM", "Multithreading", "Databases", "Java 8",
    "Patterns", "Testing"
]
RATING_LABELS = {
    "Again": "🔴 Again",
    "Hard": "🟠 Hard",
    "Good": "🟢 Good",
    "Easy": "🔵 Easy",
}

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
if "rated" not in st.session_state:
    st.session_state.rated = False
if "next_review_at" not in st.session_state:
    st.session_state.next_review_at = ""


def _next_question(topic_choice: str) -> tuple[str, str] | None:
    """Resolve a (question, topic) pair for the chosen mode.

    Returns ``None`` for 'Due for Review' mode when nothing is due yet —
    callers should show a message instead of clearing the current question.
    """
    if topic_choice == DUE_REVIEW_LABEL:
        due = store.get_due_questions(db_path=store.DB_PATH, limit=1)
        if not due:
            return None
        return due[0]["question"], due[0]["topic"]

    topic = (
        pick_topic_for_auto_mode(TOPICS, db_path=store.DB_PATH)
        if topic_choice == AUTO_TOPIC_LABEL
        else topic_choice
    )
    state = {"topic": topic, "total_questions": st.session_state.total}
    result = nodes["ask"](state)
    return result["current_question"], topic


# ── UI ────────────────────────────────────────────────────
topic_choice = st.selectbox(
    "Choose a topic:", [AUTO_TOPIC_LABEL, DUE_REVIEW_LABEL] + TOPICS
)
if topic_choice == DUE_REVIEW_LABEL:
    st.caption(
        "🔁 Resurfaces questions you've previously rated, once their spaced-repetition "
        "schedule says they're due (Again: 1 day, Hard: 3 days, Good: 7 days, Easy: 14 days)."
    )
else:
    st.caption(
        "💡 Question difficulty adapts to your saved accuracy on this topic — "
        "it gets harder as you improve, and eases up while you're still shaky."
    )

if st.button("🎯 Generate Question"):
    with st.spinner("Searching question bank..."):
        picked = _next_question(topic_choice)
        if picked is None:
            st.session_state.question = ""
            st.session_state.active_topic = ""
            st.info("🎉 No questions are due for review right now — check back later!")
        else:
            st.session_state.question, st.session_state.active_topic = picked
            st.session_state.feedback = ""
            st.session_state.hint = ""
            st.session_state.rated = False

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

        st.markdown("**How well did you know this?** _(schedules it for a future review)_")
        if st.session_state.rated:
            st.caption(f"✅ Rated — next review: {st.session_state.next_review_at[:10]}")
        else:
            rating_cols = st.columns(4)
            for col, (rating, label) in zip(rating_cols, RATING_LABELS.items()):
                with col:
                    if st.button(label, key=f"rate_{rating}"):
                        next_review_at = store.record_review(
                            topic=st.session_state.active_topic,
                            question=st.session_state.question,
                            rating=rating,
                            db_path=store.DB_PATH,
                        )
                        st.session_state.rated = True
                        st.session_state.next_review_at = next_review_at
                        st.rerun()

        if st.button("➡️ Next Question"):
            with st.spinner("Searching next question..."):
                picked = _next_question(topic_choice)
                if picked is None:
                    st.session_state.question = ""
                    st.session_state.active_topic = ""
                    st.info("🎉 No questions are due for review right now — check back later!")
                else:
                    st.session_state.question, st.session_state.active_topic = picked
                    st.session_state.feedback = ""
                    st.session_state.hint = ""
                    st.session_state.rated = False
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
