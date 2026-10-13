from storage import questions_inbox as inbox


def test_add_and_list_open_question(tmp_path):
    db_path = str(tmp_path / "inbox.db")

    qid = inbox.add_question("thread-1", "מה ההשתתפות של העובד ברכב החדש?", db_path)
    open_questions = inbox.list_open_questions(db_path)

    assert len(open_questions) == 1
    assert open_questions[0].id == qid
    assert open_questions[0].status == "open"
    assert inbox.has_open_question_for_thread("thread-1", db_path) is True


def test_answer_question_resolves_it_and_records_answer(tmp_path):
    db_path = str(tmp_path / "inbox.db")

    qid = inbox.add_question("thread-2", "מה ההשתתפות?", db_path)
    inbox.answer_question(qid, "350 ₪ בתוקף מ-1/1", db_path)

    assert inbox.list_open_questions(db_path) == []
    assert inbox.has_open_question_for_thread("thread-2", db_path) is False

    latest = inbox.get_latest_answer_for_thread("thread-2", db_path)
    assert latest is not None
    assert latest.answer == "350 ₪ בתוקף מ-1/1"
    assert latest.status == "answered"


def test_get_latest_answer_returns_none_when_no_answer_yet(tmp_path):
    db_path = str(tmp_path / "inbox.db")
    inbox.add_question("thread-3", "שאלה כלשהי", db_path)
    assert inbox.get_latest_answer_for_thread("thread-3", db_path) is None


def test_answered_unresumed_flow(tmp_path):
    db_path = str(tmp_path / "inbox.db")

    qid = inbox.add_question("thread-4", "מה ההשתתפות?", db_path)
    # לפני מענה - אין עדיין מה לחדש
    assert inbox.get_answered_unresumed_for_thread("thread-4", db_path) is None

    inbox.answer_question(qid, "350 ₪", db_path)
    pending_resume = inbox.get_answered_unresumed_for_thread("thread-4", db_path)
    assert pending_resume is not None
    assert pending_resume.id == qid

    inbox.mark_resumed(qid, db_path)
    assert inbox.get_answered_unresumed_for_thread("thread-4", db_path) is None


def test_multiple_threads_are_isolated(tmp_path):
    db_path = str(tmp_path / "inbox.db")
    inbox.add_question("thread-a", "שאלה א", db_path)
    inbox.add_question("thread-b", "שאלה ב", db_path)

    assert len(inbox.list_open_questions(db_path)) == 2
    assert inbox.has_open_question_for_thread("thread-a", db_path) is True
    assert inbox.has_open_question_for_thread("thread-c", db_path) is False
