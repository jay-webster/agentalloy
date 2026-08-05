"""Local-only queue of verdicts pending application to the canonical
`candidates.db`.

Deliberately separate from `store.py`: this is a scratchpad of verdicts Jay
has decided on but that haven't reached Drive yet, created and cleared
entirely on one machine, never itself synced. No Drive or network access
lives here — applying a queued verdict is the job of the
`apply-review-queue` routine, not this module.
"""

from __future__ import annotations

import json
from pathlib import Path

from automation.store import VALID_VERDICTS

DEFAULT_QUEUE_PATH = Path(".automation") / "review-queue.jsonl"


def append(
    message_id: str,
    verdict: str,
    rationale: str,
    queue_path: Path = DEFAULT_QUEUE_PATH,
) -> None:
    if verdict not in VALID_VERDICTS:
        raise ValueError(
            f"invalid verdict {verdict!r}, expected one of {sorted(VALID_VERDICTS)}"
        )
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    row = {"message_id": message_id, "verdict": verdict, "rationale": rationale}
    with queue_path.open("a") as f:
        f.write(json.dumps(row) + "\n")


def list_pending(queue_path: Path = DEFAULT_QUEUE_PATH) -> list[dict]:
    if not queue_path.exists():
        return []
    with queue_path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def clear(queue_path: Path = DEFAULT_QUEUE_PATH) -> None:
    if queue_path.exists():
        queue_path.unlink()
