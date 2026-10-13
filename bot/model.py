"""
Factory לבחירת מודל השפה (Claude/OpenAI) לפי משתני סביבה, כדי שהקוד מעל זה
(bot/graph.py) יעבוד באותה צורה בלי קשר לספק. קריאה לפונקציה הזו דורשת
שה-.env נטען כבר (python-dotenv, נעשה בכניסת האפליקציה).
"""

from __future__ import annotations

import os


class MissingAPIKey(Exception):
    pass


def get_chat_model():
    provider = os.environ.get("LLM_PROVIDER", "anthropic").strip().lower()

    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise MissingAPIKey("ANTHROPIC_API_KEY חסר ב-.env")
        from langchain_anthropic import ChatAnthropic

        model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
        return ChatAnthropic(model=model, api_key=api_key, temperature=0)

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise MissingAPIKey("OPENAI_API_KEY חסר ב-.env")
        from langchain_openai import ChatOpenAI

        model = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
        return ChatOpenAI(model=model, api_key=api_key, temperature=0)

    raise ValueError(f"LLM_PROVIDER לא מוכר: {provider} (אפשרויות: anthropic / openai)")
