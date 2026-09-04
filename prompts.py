"""Prompt text for the evaluate / hint steps, in one place.

``graph/workflow.py`` wraps these in ``ChatPromptTemplate`` for the
LangGraph nodes; ``mcp_server/tools.py`` uses ``str.format`` so it needs no
LangChain import. Same wording either way — the ``{question}`` / ``{answer}``
placeholders are compatible with both.
"""

EVAL_PROMPT = """
You are a Java technical interviewer evaluating an answer.

Question: {question}
Candidate's Answer: {answer}

Respond with:
1. CORRECT or INCORRECT
2. Brief feedback (2-3 sentences)
3. Ideal answer in simple terms

Start your response with either CORRECT or INCORRECT on the first line.
"""

HINT_PROMPT = """
You are a helpful Java tutor.
Give a short hint (2-3 sentences) for this question without giving away the answer.
Question: {question}
"""
