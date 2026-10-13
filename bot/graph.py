"""
מנהל השיחה בפועל: בונה סוכן LangGraph שמחזיק את כל הכלים מ-bot/tools.py,
עם checkpointer (SQLite) ששומר את מצב כל שיחה לפי thread_id, ותמיכה ב-
interrupt/resume לתבנית "שלח שאלה לנציג -> המתן -> המשך מאותה נקודה".

זהו המקום היחיד בפרויקט שבו מודל השפה "רץ" בפועל - כל השאר (engine/, bot/tools.py)
הוא תשתית טהורה בלי LLM.
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command

from bot.model import get_chat_model
from bot.tools import ALL_TOOLS
from storage import questions_inbox

DEFAULT_CHECKPOINT_DB_PATH = Path(__file__).resolve().parent.parent / "storage" / "conversations.db"

SYSTEM_PROMPT = """\
את/ה יועץ/ת הרכב של שטראוס. עונה בעברית, בקצרה ובבהירות.

חוקי ברזל:
1. אסור לחשב נטו/מס/זכאות בעצמך בשום צורה - לכל מספר חייבת להיות קריאה לכלי מתאים.
2. אם חסר מידע כדי לקרוא לכלי - שואלים את העובד/ת. רק אם זה מידע שרק נציג/ת
   התחבורה יודע/ת (כמו השתתפות מדויקת שטרם נקבעה) - משתמשים בכלי ask_representative.
3. לעולם לא ממציאים זכאות/שווי שימוש/מספרים - "לא יודע/ת, בודק/ת" עדיף על ניחוש.
4. כשמוצגת תוצאה שמבוססת על נתוני-דמה (dummy_data=true בתשובת כלי, למשל טבלת
   עיסוקים לוויתור) - מציינים את זה לעובד/ת במפורש.
5. בסוף השוואה - מציגים את net_diff וההסבר בשתי שורות פשוטות, בלי ז'רגון.
"""


def build_checkpointer(db_path: str = str(DEFAULT_CHECKPOINT_DB_PATH)) -> SqliteSaver:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


@lru_cache(maxsize=1)
def get_agent():
    """בנייה חד-פעמית של הסוכן (דורשת מפתח API תקין ב-.env - נכשלת רק כש-
    קוראים לה בפועל, לא בזמן import, כדי שאפשר יהיה לייבא את המודול בבדיקות
    בלי מפתח)."""
    model = get_chat_model()
    checkpointer = build_checkpointer()
    return create_react_agent(model, ALL_TOOLS, prompt=SYSTEM_PROMPT, checkpointer=checkpointer)


def extract_interrupt_question(result: dict) -> str | None:
    """אם ה-graph נעצר ב-interrupt (ask_representative) - מחזיר את טקסט
    השאלה. אחרת None. פונקציה טהורה - נבדקת בלי שום קריאת LLM."""
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    payload = interrupts[0].value
    if isinstance(payload, dict):
        return payload.get("question", str(payload))
    return str(payload)


def extract_last_ai_message(result: dict) -> str:
    """מוצא את תשובת הטקסט האחרונה של המודל מתוך רשימת ההודעות. פונקציה
    טהורה - נבדקת בלי שום קריאת LLM."""
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return ""


def run_turn(thread_id: str, user_message: str) -> dict:
    """תור אחד בשיחה: שולח הודעת עובד, ומחזיר תשובה או מצב "ממתין לנציג"."""
    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke({"messages": [HumanMessage(user_message)]}, config=config)

    question = extract_interrupt_question(result)
    if question:
        questions_inbox.add_question(thread_id, question)
        return {"status": "waiting_for_representative", "question": question}

    return {"status": "ok", "message": extract_last_ai_message(result)}


def resume_if_representative_answered(thread_id: str) -> dict | None:
    """
    בודקים אם יש תשובת נציג שעוד לא "הוזרמה" לשיחה הזו, וממשיכים אוטומטית
    אם כן. קוראים לזה בתחילת כל טעינה/רענון של מסך העובד - זה מה שנותן את
    "השיחה ממשיכה מאותה נקודה, גם אחרי רענון".
    מחזיר None אם אין שום דבר לחדש (אין צורך לעדכן את המסך).
    """
    pending = questions_inbox.get_answered_unresumed_for_thread(thread_id)
    if pending is None:
        return None

    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke(Command(resume=pending.answer), config=config)
    questions_inbox.mark_resumed(pending.id)

    question = extract_interrupt_question(result)
    if question:
        questions_inbox.add_question(thread_id, question)
        return {"status": "waiting_for_representative", "question": question}

    return {"status": "ok", "message": extract_last_ai_message(result)}
