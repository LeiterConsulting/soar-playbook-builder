"""Tests for soar_playbook_list pagination helpers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "soar_playbook_builder"
sys.path.insert(0, str(ROOT))

from soar_playbook_list import (  # noqa: E402
    _dedupe_playbooks,
    _fetch_with_strategies,
    playbooks_from_rest,
    rest_total_count,
)


def test_playbooks_from_rest_list():
    assert len(playbooks_from_rest([{"id": 1}, {"id": 2}])) == 2


def test_playbooks_from_rest_data_wrapper():
    assert playbooks_from_rest({"data": [{"id": 3}], "count": 1})[0]["id"] == 3


def test_rest_total_count():
    assert rest_total_count({"data": [], "count": 42}) == 42


def test_dedupe():
    rows = _dedupe_playbooks([{"id": 1}, {"id": 1}, {"id": 2}])
    assert len(rows) == 2


def test_fetch_page_size_zero():
    calls: list[dict] = []

    def fake_get(params):
        calls.append(params)
        if params.get("page_size") == 0:
            return True, {"data": [{"id": i} for i in range(15)], "count": 15}
        return True, {"data": [{"id": i} for i in range(10)]}

    rows, strategy = _fetch_with_strategies(fake_get, None)
    assert len(rows) == 15
    assert strategy == "page_size=0"


if __name__ == "__main__":
    test_playbooks_from_rest_list()
    test_playbooks_from_rest_data_wrapper()
    test_rest_total_count()
    test_dedupe()
    test_fetch_page_size_zero()
    print("ok")
