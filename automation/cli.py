"""CLI for the candidate store: `python -m automation.cli ingest ...`."""

from __future__ import annotations

import argparse
import datetime
import json
import sys

from automation.store import (
    VALID_VERDICTS,
    Candidate,
    CandidateNotFoundError,
    CandidateStore,
    FlaggedCandidateError,
    NotAcceptedError,
)

_IMPORT_REQUIRED_FIELDS = (
    "message_id",
    "thread_id",
    "source",
    "subject",
    "received_at",
    "snippet",
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


def _cmd_import_jsonl(args: argparse.Namespace, store: CandidateStore) -> int:
    added = 0
    already_present = 0
    skipped = 0
    with open(args.path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if not isinstance(row, dict) or not all(
                field in row for field in _IMPORT_REQUIRED_FIELDS
            ):
                skipped += 1
                continue
            candidate = Candidate(
                message_id=row["message_id"],
                thread_id=row["thread_id"],
                source=row["source"],
                subject=row["subject"],
                received_at=row["received_at"],
                snippet=row["snippet"],
                ingested_at=datetime.datetime.now(datetime.UTC).isoformat(),
            )
            if store.add(candidate):
                added += 1
            else:
                already_present += 1
    print(
        f"imported {args.path}: {added} added, {already_present} already present, {skipped} skipped"
    )
    return 0


def _format_candidate(c: Candidate) -> str:
    return f"- {c.message_id} | {c.source} | {c.subject}\n  {c.rationale}"


def _cmd_report(args: argparse.Namespace, store: CandidateStore) -> int:
    rows = [c for c in store.list() if c.evaluated_at and c.evaluated_at >= args.since]

    if not rows:
        print(f"Automation run digest — no candidates evaluated since {args.since}.")
        return 0

    accepted = [c for c in rows if c.verdict == "accept"]
    needs_review = [c for c in rows if c.verdict == "needs_review"]
    rejected = [c for c in rows if c.verdict == "reject"]
    flagged = [c for c in rows if c.flagged]

    print(
        f"Automation run digest — {len(rows)} evaluated "
        f"({len(accepted)} accept, {len(needs_review)} needs_review, {len(rejected)} reject)"
    )

    if not accepted and not needs_review:
        print(f"Nothing needs your attention — {len(rejected)} rejected.")
        if flagged:
            print(f"{len(flagged)} candidate(s) flagged by the injection guard this run.")
        return 0

    if accepted:
        print("\nACCEPT:")
        for c in accepted:
            print(_format_candidate(c))

    if needs_review:
        print("\nNEEDS REVIEW:")
        for c in needs_review:
            print(_format_candidate(c))

    if flagged:
        print(f"\n{len(flagged)} candidate(s) flagged by the injection guard this run.")

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

    import_parser = ingest_sub.add_parser(
        "import-jsonl", help="Import candidates from a JSONL file"
    )
    import_parser.add_argument("path")
    import_parser.set_defaults(func=_cmd_import_jsonl)

    report_parser = ingest_sub.add_parser("report", help="Digest of recently evaluated candidates")
    report_parser.add_argument("--since", required=True)
    report_parser.set_defaults(func=_cmd_report)

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
