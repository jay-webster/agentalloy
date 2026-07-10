"""CLI for the candidate store: `python -m automation.cli ingest ...`."""

from __future__ import annotations

import argparse
import sys

from automation.store import (
    VALID_VERDICTS,
    Candidate,
    CandidateNotFoundError,
    CandidateStore,
    FlaggedCandidateError,
    NotAcceptedError,
)


def _cmd_add(args: argparse.Namespace, store: CandidateStore) -> int:
    candidate = Candidate(
        message_id=args.message_id,
        thread_id=args.thread_id,
        source=args.source,
        subject=args.subject,
        received_at=args.received_at,
        snippet=args.snippet,
        ingested_at=args.ingested_at,
    )
    inserted = store.add(candidate)
    if inserted:
        print(f"added {candidate.message_id}")
    else:
        print(f"already present: {candidate.message_id}")
    return 0


def _cmd_list(args: argparse.Namespace, store: CandidateStore) -> int:
    rows = store.list(status=args.status)
    if not rows:
        print("no candidates")
        return 0
    for row in rows:
        line = f"{row.message_id}\t{row.status}\t{row.source}\t{row.subject}"
        if row.verdict is not None:
            line += f"\t[{row.verdict}] {row.rationale}"
        if row.flagged:
            line = f"[FLAGGED: {row.flag_reasons}] " + line
        print(line)
    return 0


def _cmd_mark(args: argparse.Namespace, store: CandidateStore) -> int:
    updated = store.mark(args.message_id, args.status)
    if not updated:
        print(f"no candidate with message_id {args.message_id}", file=sys.stderr)
        return 1
    print(f"marked {args.message_id} as {args.status}")
    return 0


def _cmd_evaluate(args: argparse.Namespace, store: CandidateStore) -> int:
    try:
        updated = store.evaluate(args.message_id, args.verdict, args.rationale)
    except FlaggedCandidateError as exc:
        print(
            f"refused: {exc.message_id} is flagged ({exc.flag_reasons}) — "
            "accept is blocked, use reject or needs_review",
            file=sys.stderr,
        )
        return 1
    if not updated:
        print(f"no candidate with message_id {args.message_id}", file=sys.stderr)
        return 1
    print(f"evaluated {args.message_id}: {args.verdict}")
    return 0


def _cmd_integrate(args: argparse.Namespace, store: CandidateStore) -> int:
    try:
        result = store.integrate(args.message_id)
    except CandidateNotFoundError:
        print(f"no candidate with message_id {args.message_id}", file=sys.stderr)
        return 1
    except NotAcceptedError as exc:
        print(
            f"cannot integrate: {exc.message_id} has verdict {exc.verdict!r}, "
            "only accept candidates can be integrated",
            file=sys.stderr,
        )
        return 1
    if result.already_existed:
        print(f"already integrated, draft unchanged: {result.draft_path}")
    else:
        print(f"integrated {args.message_id}: draft written to {result.draft_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="automation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="Manage the candidate backlog")
    ingest_sub = ingest.add_subparsers(dest="ingest_command", required=True)

    add_parser = ingest_sub.add_parser("add", help="Record a candidate")
    add_parser.add_argument("--message-id", required=True)
    add_parser.add_argument("--thread-id", required=True)
    add_parser.add_argument("--source", required=True)
    add_parser.add_argument("--subject", required=True)
    add_parser.add_argument("--received-at", required=True)
    add_parser.add_argument("--snippet", required=True)
    add_parser.add_argument("--ingested-at", required=True)
    add_parser.set_defaults(func=_cmd_add)

    list_parser = ingest_sub.add_parser("list", help="List candidates")
    list_parser.add_argument("--status", default=None)
    list_parser.set_defaults(func=_cmd_list)

    mark_parser = ingest_sub.add_parser("mark", help="Update a candidate's status")
    mark_parser.add_argument("message_id")
    mark_parser.add_argument("status")
    mark_parser.set_defaults(func=_cmd_mark)

    evaluate_parser = ingest_sub.add_parser("evaluate", help="Record a verdict")
    evaluate_parser.add_argument("message_id")
    evaluate_parser.add_argument("--verdict", required=True, choices=sorted(VALID_VERDICTS))
    evaluate_parser.add_argument("--rationale", required=True)
    evaluate_parser.set_defaults(func=_cmd_evaluate)

    integrate_parser = ingest_sub.add_parser("integrate", help="Generate a draft SDD intake")
    integrate_parser.add_argument("message_id")
    integrate_parser.set_defaults(func=_cmd_integrate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = CandidateStore()
    try:
        return args.func(args, store)
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
