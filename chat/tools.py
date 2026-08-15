"""
Tool definitions for the AI agent.

Each tool has a JSON schema (OpenAI/Groq function-calling format) and a
Python function that actually executes it. Add new tools by writing a
function + schema and registering it in TOOLS at the bottom.
"""

import re
import uuid
from datetime import datetime, timezone

SAFE_EXPR_RE = re.compile(r"^[0-9+\-*/%().\s]+$")


def calculator(expression: str = ""):
    if not SAFE_EXPR_RE.match(expression or ""):
        return {"error": "Expression contains unsupported characters."}
    try:
        # Restricted eval: only arithmetic characters allowed by the regex above.
        result = eval(expression, {"__builtins__": {}}, {})  # noqa: S307
        return {"expression": expression, "result": result}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Could not evaluate expression: {exc}"}


def get_current_time():
    return {"iso": datetime.now(timezone.utc).isoformat()}


def web_search(query: str = ""):
    # Placeholder so the project runs with zero extra API keys.
    # Swap this out for a real search API (Tavily, Bing, SerpAPI...) for
    # live results.
    return {
        "note": (
            "This is a placeholder search tool. Wire up a real search API "
            "in chat/tools.py to give the agent live web access."
        ),
        "query": query,
        "results": [
            {
                "id": str(uuid.uuid4()),
                "title": f'Example result for "{query}"',
                "snippet": "Connect a real search provider here for live results.",
            }
        ],
    }


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": (
                "Evaluate a basic arithmetic expression (+, -, *, /, %, "
                "parentheses). Use this for any math instead of guessing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "A math expression, e.g. '(12 + 8) * 3 / 4'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current date/time in ISO 8601 format (UTC).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for up-to-date information. Returns mock "
                "results in this demo build — replace with a real search "
                "API for production use."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"}
                },
                "required": ["query"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "calculator": calculator,
    "get_current_time": get_current_time,
    "web_search": web_search,
}


def run_tool(name: str, arguments: dict):
    fn = TOOL_FUNCTIONS.get(name)
    if not fn:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(**arguments)
    except TypeError as exc:
        return {"error": f"Bad arguments for {name}: {exc}"}
