"""T3 — swept-by-another-session phase confirm (phase-boundary-confirmation).

When an already-oriented session's next turn observes the phase changed since it
last looked, AND the on-disk `transitioned_by` actor recorded for that change is a
different, concrete session key than this turn's own, the signal layer emits a
deterministic confirm directive — the same repo-wide phase file is contended by
concurrent sessions, so "the phase moved and it wasn't me" is worth surfacing
before charging ahead on the new phase as if this session had caused it.

Distinct from T2 (`test_new_session_confirm.py`): T2 covers a session's first turn
on a phase it never saw change (`not phase_changed`); T3 covers a session that WAS
oriented on the prior phase and had it moved out from under it by someone else
(`phase_changed`). The two are mutually exclusive by construction.
"""

from __future__ import annotations

from pathlib import Path

from agentalloy.api.proxy_models import ProxyMessage, ProxyRequest
from agentalloy.api.proxy_signal import evaluate_signal


def _req(text: str = "continue", *, tools: bool = True) -> ProxyRequest:
    return ProxyRequest(
        model="gpt-4",
        messages=[ProxyMessage(role="user", content=text)],
        tools=[{"name": "Read", "description": "read", "input_schema": {}}] if tools else [],
    )


def _set_phase(tmp: Path, phase: str, *, transitioned_by: str | None = None) -> None:
    d = tmp / ".agentalloy"
    d.mkdir(exist_ok=True, parents=True)
    text = f"phase: {phase}\n"
    if transitioned_by:
        text += f"transitioned_by: {transitioned_by}\n"
    (d / "phase").write_text(text)


def _seed_announced(tmp: Path, phase: str, keys: list[str]) -> None:
    d = tmp / ".agentalloy"
    d.mkdir(exist_ok=True, parents=True)
    (d / "announced").write_text(f"{phase}\t{','.join(keys)}")


def _ship_record(tmp: Path, slug: str = "some-feature") -> None:
    d = tmp / "docs" / "ship"
    d.mkdir(exist_ok=True, parents=True)
    (d / f"{slug}.md").write_text("# Ship\n")


async def test_swept_by_other_session_confirms(tmp_path: Path):
    # "me" was oriented on "design"; the file now says "build", moved by "other".
    _set_phase(tmp_path, "build", transitioned_by="other-session")
    _seed_announced(tmp_path, "design", ["me"])
    sig = await evaluate_signal(_req(), tmp_path, session_id="me")
    assert sig.confirm_directives, "a phase swept by a different session must confirm"
    joined = "\n".join(sig.confirm_directives).lower()
    assert "build" in joined and "confirm" in joined and "different" in joined


async def test_self_transitioned_does_not_confirm(tmp_path: Path):
    # The phase changed, but "me" is the recorded actor (this session caused it
    # itself, e.g. via the reranker auto-advance) — not a sweep, no confirm.
    _set_phase(tmp_path, "build", transitioned_by="me")
    _seed_announced(tmp_path, "design", ["me"])
    sig = await evaluate_signal(_req(), tmp_path, session_id="me")
    assert not sig.confirm_directives, "the session that caused its own transition must not confirm"


async def test_unattributed_transition_does_not_confirm(tmp_path: Path):
    # No transitioned_by recorded at all (bare CLI phase set, or pre-existing repo)
    # — ambiguous actor, so silence beats a false positive.
    _set_phase(tmp_path, "build")  # no transitioned_by
    _seed_announced(tmp_path, "design", ["me"])
    sig = await evaluate_signal(_req(), tmp_path, session_id="me")
    assert not sig.confirm_directives


async def test_swept_on_intake_is_silent(tmp_path: Path):
    _set_phase(tmp_path, "intake", transitioned_by="other-session")
    _seed_announced(tmp_path, "build", ["me"])
    sig = await evaluate_signal(_req(), tmp_path, session_id="me")
    assert not sig.confirm_directives, "intake is the happy path — no confirm even when swept"


async def test_swept_takes_priority_over_new_session_wording(tmp_path: Path):
    # "me" has never been oriented for ANY phase — normally new-session territory
    # (T2) — but the phase ALSO changed with a different recorded actor. Because
    # `new_session` requires `not phase_changed` by construction, `phase_changed`
    # forces new_session=False here regardless of last_sessions, so the T3 "swept"
    # wording fires, never the T2 "resuming a NEW session" wording.
    _set_phase(tmp_path, "build", transitioned_by="other-session")
    _seed_announced(tmp_path, "design", ["someone-else"])
    sig = await evaluate_signal(_req(), tmp_path, session_id="me")
    assert sig.confirm_directives
    joined = "\n".join(sig.confirm_directives).lower()
    assert "different" in joined and "concurrent session" in joined
    assert "resuming a new session" not in joined


async def test_precedence_single_directive_on_ship_with_record(tmp_path: Path):
    # Swept onto ship WITH a delivery record → exactly ONE combined directive.
    _set_phase(tmp_path, "ship", transitioned_by="other-session")
    _seed_announced(tmp_path, "build", ["me"])
    _ship_record(tmp_path)
    sig = await evaluate_signal(_req(), tmp_path, session_id="me")
    assert len(sig.confirm_directives) == 1
    joined = sig.confirm_directives[0].lower()
    assert "confirm" in joined and "intake" in joined


async def test_toolless_header_request_does_not_fire(tmp_path: Path):
    _set_phase(tmp_path, "build", transitioned_by="other-session")
    _seed_announced(tmp_path, "design", ["me"])
    sig = await evaluate_signal(_req(tools=False), tmp_path, session_id="me")
    assert not sig.confirm_directives


async def test_swept_confirm_does_not_write_phase(tmp_path: Path):
    _set_phase(tmp_path, "build", transitioned_by="other-session")
    _seed_announced(tmp_path, "design", ["me"])
    await evaluate_signal(_req(), tmp_path, session_id="me")
    assert (tmp_path / ".agentalloy" / "phase").read_text().splitlines()[0] == "phase: build"
