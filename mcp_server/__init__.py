"""MCP server for Java Interview Coach.

Exposes the same retrieval + adaptive-selection + grading + spaced-repetition
core that the Streamlit app and the CLI drive, as Model Context Protocol
tools/resources/prompts — so any MCP client (Claude Desktop, Claude Code,
Cursor, VS Code) can run mock interviews against it.

``mcp_server.tools`` holds the logic as plain functions (dependency-injected,
unit-testable). ``mcp_server.server`` wires them to FastMCP and owns the
lazily-built ChromaDB collection and Groq client.
"""
