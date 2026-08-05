"""Tests for automation.review_queue — a local-only, never-synced verdict queue."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from automation import review_queue


def test_append_writes_one_json_line(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.jsonl"
    review_queue.append("m1", "reject", "no lens fires", queue_path=queue_path)
    lines = queue_path.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "message_id": "m1",
        "verdict": "reject",
        "rationale": "no lens fires",
    }


def test_append_invalid_verdict_raises_and_writes_nothing(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.jsonl"
    with pytest.raises(ValueError):
        review_queue.append("m1", "maybe", "unsure", queue_path=queue_path)
    assert not queue_path.exists()


def test_append_same_message_id_twice_keeps_both_lines_in_order(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.jsonl"
    review_queue.append("m1", "needs_review", "first pass", queue_path=queue_path)
    review_queue.append("m1", "reject", "reconsidered", queue_path=queue_path)
    rows = review_queue.list_pending(queue_path=queue_path)
    assert [row["verdict"] for row in rows] == ["needs_review", "reject"]


def test_list_pending_missing_file_returns_empty_list(tmp_path: Path) -> None:
    queue_path = tmp_path / "does-not-exist.jsonl"
    assert review_queue.list_pending(queue_path=queue_path) == []


def test_list_pending_preserves_append_order(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.jsonl"
    review_queue.append("a", "accept", "r1", queue_path=queue_path)
    review_queue.append("b", "reject", "r2", queue_path=queue_path)
    review_queue.append("c", "needs_review", "r3", queue_path=queue_path)
    rows = review_queue.list_pending(queue_path=queue_path)
    assert [row["message_id"] for row in rows] == ["a", "b", "c"]


def test_clear_empties_the_queue(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.jsonl"
    review_queue.append("a", "accept", "r1", queue_path=queue_path)
    review_queue.clear(queue_path=queue_path)
    assert review_queue.list_pending(queue_path=queue_path) == []


def test_clear_on_missing_queue_is_a_noop(tmp_path: Path) -> None:
    queue_path = tmp_path / "does-not-exist.jsonl"
    review_queue.clear(queue_path=queue_path)


def test_no_drive_or_network_call_sites() -> None:
    source = Path("automation/review_queue.py").read_text()
    forbidden_literals = ("googleapis", "requests", "httpx", "curl")
    for literal in forbidden_literals:
        assert literal not in source, f"unexpected {literal!r} reference in review_queue.py"
    assert not re.search(r"google.*drive", source, re.IGNORECASE)
