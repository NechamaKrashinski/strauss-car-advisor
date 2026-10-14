"""
Factory לבחירת מודל השפה (Claude/OpenAI) לפי משתני סביבה, כדי שהקוד מעל זה
(bot/graph.py) יעבוד באותה צורה בלי קשר לספק. קריאה לפונקציה הזו דורשת
שה-.env נטען כבר (python-dotenv, נעשה בכניסת האפליקציה).
"""

from __future__ import annotations

import os

try:
    # חלק ממחשבים (בעיקר Windows) עם גרסת OpenSSL מסוימת נכשלים באימות
    # שרשרת ה-TLS האמיתית של ספקי LLM עם שגיאת "CA cert does not include
    # key usage extension", אף שהחיבור עצמו תקין (אומת עם curl דרך schannel
    # של Windows). truststore מאציל את האימות למנגנון המובנה של מערכת
    # ההפעלה במקום ל-OpenSSL הפנימי של Python, ופותר את זה.
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass


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
        return ChatAnthropic(model=model, api_key=api_key)

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise MissingAPIKey("OPENAI_API_KEY חסר ב-.env")
        from langchain_openai import ChatOpenAI

        model = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
        return ChatOpenAI(model=model, api_key=api_key)

    raise ValueError(f"LLM_PROVIDER לא מוכר: {provider} (אפשרויות: anthropic / openai)")
