"""
תור שאלות פתוחות לנציג. זו טבלה קלה ונפרדת מה-checkpointer של LangGraph
(שמחזיק את מצב השיחה המלא) - התפקיד שלה הוא רק לאפשר למסך הנציג (Streamlit,
תהליך נפרד) לדעת אילו שיחות ממתינות למענה, בלי לגעת בפנימיות של LangGraph.

thread_id מקשר שאלה בתור לשיחת LangGraph הספציפית (configurable.thread_id),
כדי שברגע שהנציג עונה אפשר לחדש את אותה שיחה בדיוק (Command(resume=...)).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "storage" / "questions_inbox.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    question TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    answer TEXT,
    created_at TEXT NOT NULL,
    answered_at TEXT
);
"""


@dataclass(frozen=True)
class Question:
    id: int
    thread_id: str
    question: str
    status: str
    answer: str | None
    created_at: str
    answered_at: str | None


@contextmanager
def _connect(db_path: str = str(DEFAULT_DB_PATH)):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str = str(DEFAULT_DB_PATH)) -> None:
    with _connect(db_path) as conn:
        conn.execute(_SCHEMA)


def add_question(thread_id: str, question: str, db_path: str = str(DEFAULT_DB_PATH)) -> int:
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO questions (thread_id, question, status, created_at) VALUES (?, ?, 'open', ?)",
            (thread_id, question, datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid


def _row_to_question(row: sqlite3.Row) -> Question:
    return Question(
        id=row["id"],
        thread_id=row["thread_id"],
        question=row["question"],
        status=row["status"],
        answer=row["answer"],
        created_at=row["created_at"],
        answered_at=row["answered_at"],
    )


def list_open_questions(db_path: str = str(DEFAULT_DB_PATH)) -> list[Question]:
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM questions WHERE status = 'open' ORDER BY created_at ASC"
        ).fetchall()
        return [_row_to_question(r) for r in rows]


def list_all_questions(db_path: str = str(DEFAULT_DB_PATH)) -> list[Question]:
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM questions ORDER BY created_at DESC").fetchall()
        return [_row_to_question(r) for r in rows]


def answer_question(question_id: int, answer: str, db_path: str = str(DEFAULT_DB_PATH)) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE questions SET status = 'answered', answer = ?, answered_at = ? WHERE id = ?",
            (answer, datetime.now(timezone.utc).isoformat(), question_id),
        )


def get_latest_answer_for_thread(thread_id: str, db_path: str = str(DEFAULT_DB_PATH)) -> Question | None:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM questions WHERE thread_id = ? AND status = 'answered' "
            "ORDER BY answered_at DESC LIMIT 1",
            (thread_id,),
        ).fetchone()
        return _row_to_question(row) if row else None


def get_answered_unresumed_for_thread(thread_id: str, db_path: str = str(DEFAULT_DB_PATH)) -> Question | None:
    """
    שאלה שהנציג/ה כבר ענה/תה עליה, אבל שיחת ה-LangGraph עדיין לא חודשה איתה.
    זה מה שצד העובד בודק בכל טעינה/רענון כדי להחליט אם להמשיך את השיחה
    ("המצב נשמר גם אחרי רענון").
    """
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM questions WHERE thread_id = ? AND status = 'answered' "
            "ORDER BY answered_at ASC LIMIT 1",
            (thread_id,),
        ).fetchone()
        return _row_to_question(row) if row else None


def mark_resumed(question_id: int, db_path: str = str(DEFAULT_DB_PATH)) -> None:
    with _connect(db_path) as conn:
        conn.execute("UPDATE questions SET status = 'resumed' WHERE id = ?", (question_id,))


def has_open_question_for_thread(thread_id: str, db_path: str = str(DEFAULT_DB_PATH)) -> bool:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM questions WHERE thread_id = ? AND status = 'open' LIMIT 1",
            (thread_id,),
        ).fetchone()
        return row is not None
