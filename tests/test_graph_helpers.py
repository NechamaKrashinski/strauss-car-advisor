"""
בדיקות לפונקציות הטהורות ב-bot/graph.py בלבד (extract_interrupt_question,
extract_last_ai_message). שאר הקובץ (get_agent, run_turn וכו') דורש מפתח
API אמיתי ולא נבדק כאן - ייבדק ידנית מול שיחה אמיתית כשה-.env יהיה מוכן.
"""

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Interrupt

from bot.graph import extract_interrupt_question, extract_last_ai_message


def test_extract_interrupt_question_from_dict_payload():
    result = {"__interrupt__": (Interrupt(value={"question": "מה ההשתתפות?"}),)}
    assert extract_interrupt_question(result) == "מה ההשתתפות?"


def test_extract_interrupt_question_returns_none_when_no_interrupt():
    result = {"messages": [AIMessage(content="הנה התשובה")]}
    assert extract_interrupt_question(result) is None


def test_extract_last_ai_message_returns_latest_ai_content():
    result = {
        "messages": [
            HumanMessage(content="שאלה"),
            AIMessage(content="תשובה ראשונה"),
            HumanMessage(content="עוד שאלה"),
            AIMessage(content="תשובה אחרונה"),
        ]
    }
    assert extract_last_ai_message(result) == "תשובה אחרונה"


def test_extract_last_ai_message_empty_when_no_ai_message():
    result = {"messages": [HumanMessage(content="שאלה בלבד")]}
    assert extract_last_ai_message(result) == ""
