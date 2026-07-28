"""Tests for offline tutor lane."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from tutor_local import (  # noqa: E402
    get_lesson_payload,
    handle_tutor_message,
    is_tutor_intent,
    list_lessons_payload,
    quiz_payload,
)


def test_list_lessons():
    out = list_lessons_payload()
    assert out["status"] == "success"
    assert out["count"] >= 5


def test_get_lesson():
    out = get_lesson_payload("01-hello-playbook")
    assert out["status"] == "success"
    assert "on_start" in out["content"]


def test_quiz_datapaths():
    out = quiz_payload("datapaths")
    assert out["status"] == "success"
    assert "sourceAddress" in out["content"]


def test_is_tutor_intent():
    assert is_tutor_intent("lesson 01-hello-playbook")
    assert is_tutor_intent("quiz datapaths")
    assert not is_tutor_intent("build a playbook for okta")


def test_handle_explain():
    out = handle_tutor_message("explain artifact:*.cef.sourceAddress")
    assert out["status"] == "success"
    assert "sourceAddress" in out["content"]


if __name__ == "__main__":
    test_list_lessons()
    test_get_lesson()
    test_quiz_datapaths()
    test_is_tutor_intent()
    test_handle_explain()
    print("ok")
