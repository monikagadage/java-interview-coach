import streamlit as st
import chromadb
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# ── Page config ───────────────────────────────────────────
st.set_page_config(page_title="☕ Java Interview Coach", page_icon="☕")
st.title("☕ Java Interview Coach")
st.caption("Practice Java interview questions with AI feedback")

# ── LLM ──────────────────────────────────────────────────
llm = ChatGroq(model="llama-3.3-70b-versatile")

# ── Prompts ───────────────────────────────────────────────
eval_prompt = ChatPromptTemplate.from_template("""
You are a Java technical interviewer evaluating an answer.

Question: {question}
Candidate's Answer: {answer}

Respond with:
1. CORRECT or INCORRECT
2. Brief feedback (2-3 sentences)
3. Ideal answer in simple terms

Start your response with either CORRECT or INCORRECT on the first line.
""")

hint_prompt = ChatPromptTemplate.from_template("""
You are a helpful Java tutor.
Give a short hint (2-3 sentences) for this question without giving away the answer.
Question: {question}
""")

eval_chain = eval_prompt | llm
hint_chain = hint_prompt | llm

# ── ChromaDB setup ────────────────────────────────────────
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

def get_question(topic):
    """Search ChromaDB for a relevant question"""
    results = collection.query(
        query_texts=[topic],
        n_results=10
    )
    questions = results['documents'][0]
    # Pick a random one from top 10 so it's not always the same
    import random
    return random.choice(questions)

# ── Session state ─────────────────────────────────────────
if "question" not in st.session_state:
    st.session_state.question = ""
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
topic = st.selectbox("Choose a topic:", [
    "OOP", "Java Core", "Java Collections", "Spring",
    "JVM", "Multithreading", "Databases", "Java 8",
    "Patterns", "Testing"
])

if st.button("🎯 Generate Question"):
    with st.spinner("Searching question bank..."):
        st.session_state.question = get_question(topic)
        st.session_state.feedback = ""
        st.session_state.hint = ""

if st.session_state.question:
    st.markdown("---")
    st.markdown(f"### 📌 Question:\n{st.session_state.question}")

    answer = st.text_area("Your answer:", height=100)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Submit Answer"):
            if answer.strip():
                with st.spinner("Evaluating..."):
                    result = eval_chain.invoke({
                        "question": st.session_state.question,
                        "answer": answer
                    })
                    st.session_state.feedback = result.content
                    st.session_state.total += 1
                    if result.content.strip().upper().startswith("CORRECT"):
                        st.session_state.score += 1
                    else:
                        st.session_state.weak_topics.append(topic)
            else:
                st.warning("Please type an answer first!")

    with col2:
        if st.button("💡 Get Hint"):
            with st.spinner("Getting hint..."):
                hint = hint_chain.invoke({
                    "question": st.session_state.question
                })
                st.session_state.hint = hint.content

    if st.session_state.hint:
        st.info(f"💡 **Hint:** {st.session_state.hint}")

    if st.session_state.feedback:
        if st.session_state.feedback.strip().upper().startswith("CORRECT"):
            st.success(st.session_state.feedback)
        else:
            st.error(st.session_state.feedback)

        if st.button("➡️ Next Question"):
            with st.spinner("Searching next question..."):
                st.session_state.question = get_question(topic)
                st.session_state.feedback = ""
                st.session_state.hint = ""
                st.rerun()

# ── Sidebar ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 Session Stats")
    st.metric("Score", f"{st.session_state.score}/{st.session_state.total}")

    if st.session_state.weak_topics:
        st.markdown("### 📚 Topics to Review")
        for t in set(st.session_state.weak_topics):
            st.markdown(f"- {t}")

    if st.button("🔄 Reset Session"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()