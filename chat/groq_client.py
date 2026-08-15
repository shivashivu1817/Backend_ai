import os

from groq import Groq
from openai import OpenAI

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

MODEL = os.environ.get("MODEL") or (
    DEFAULT_GROQ_MODEL if GROQ_API_KEY else DEFAULT_OPENAI_MODEL
)

SYSTEM_PROMPT = (
    "You are a helpful, concise AI agent. You have access to tools "
    "(calculator, get_current_time, web_search). Use a tool whenever it "
    "would make your answer more accurate instead of guessing. After using "
    "tools, give the user a clear, direct final answer. Format code with "
    "markdown code fences."
)


def get_client():
    """Return an OpenAI-compatible client — Groq if GROQ_API_KEY is set,
    otherwise plain OpenAI. Both SDKs share the same chat.completions
    interface, so the rest of the app doesn't need to know which one it's
    talking to."""
    if GROQ_API_KEY:
        return Groq(api_key=GROQ_API_KEY)
    return OpenAI(api_key=OPENAI_API_KEY)
