"""``lessons promote`` subcommand — promote a codified lesson into the corpus.

Compound-engineering bridge, task 04. Reads ``docs/solutions/<slug>.md``, turns
it into a domain-skill pack (via :mod:`agentalloy.install.lesson_pack`), runs a
**pre-ingest dedup probe**, and — only if it clears — installs it through the
existing ``install_local_pack`` rail.

The probe is *prevention, not cleanup*: the install rail writes skill rows and
vectors before its own dedup pass runs and never rolls back, so a hard duplicate
must be caught BEFORE install. The probe embeds the candidate fragments and
compares them against the live corpus with the same classifier the rail uses; a
hard hit (cosine >= ``dedup_hard_threshold``) refuses the promotion unless
``--allow-duplicates`` is passed.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agentalloy.install.lesson_pack import (
    _lesson_symbols,  # pyright: ignore[reportPrivateUsage]
    generate_lesson_pack,
)
from agentalloy.install.output import add_json_flag, print_rich, write_result
from agentalloy.install.subcommands.new_skill_pack import _SKILL_ID_RE

SCHEMA_VERSION = 1

# Injected seams (overridable in tests). A real embed takes a string and returns
# a raw vector; a real store is a FragmentStore; a real install runs the rail.
EmbedFn = Callable[[str], list[float]]
InstallFn = Callable[..., dict[str, Any]]
# symbol-linked-rationale: (repo_slug, qualified_name) -> does it exist in the
# code index? A real resolver degrades to False on any failure (see
# _default_symbol_exists); it never raises.
SymbolResolverFn = Callable[[str, str], bool]


def _default_symbol_exists(repo_slug: str, qualified_name: str) -> bool:
    """Best-effort, read-only: does ``qualified_name`` exist in ``repo_slug``'s
    code index?

    Degrades to False — never raises — when the optional ``[code-index]``
    extra isn't installed, the repo has never been indexed (``graph.duck``
    doesn't exist yet; the store's own docstring says the reader role
    "requires the graph file to already exist"), or any other resolution
    failure occurs. A lesson promotion must never hard-fail because linking
    couldn't happen. ``code_index.*`` is imported lazily here, never at this
    module's top level — the package's own docstring: "nothing in this
    package may be imported unless the [code-index] toggle is on."
    """
    try:
        from agentalloy.code_index.store.open import open_code_index
        from agentalloy.config import get_settings

        handles = open_code_index(get_settings(), repo_slug, role="reader")
    except Exception:
        return False
    try:
        return handles.graph.symbol(qualified_name) is not None
    except Exception:
        return False
    finally:
        handles.close()


def probe_lesson_duplicates(
    fragment_texts: list[str],
    *,
    embed: EmbedFn,
    vector_store: Any,
    hard_similarity: float,
    soft_similarity: float,
) -> list[Any]:
    """Return the hard cross-pack near-duplicate hits for the candidate fragments.

    Embeds each fragment and runs :func:`agentalloy.dedup_gate.dedup_fragment`
    against the live corpus. The candidate is not yet ingested, so there is no
    self-match to exclude and any hit at/above ``hard_similarity`` is a genuine
    cross-pack duplicate. Returns the list of hard ``SimilarityHit``s (empty when
    clear).
    """
    from agentalloy.dedup_gate import dedup_fragment

    hard_hits: list[Any] = []
    for i, text in enumerate(fragment_texts):
        vec = embed(text)
        hard_hit, _soft = dedup_fragment(
            label=f"lesson-f{i}",
            query_vec=vec,
            vector_store=vector_store,
            hard_similarity=hard_similarity,
            soft_similarity=soft_similarity,
        )
        if hard_hit is not None:
            hard_hits.append(hard_hit)
    return hard_hits


def _default_embed() -> EmbedFn:
    from agentalloy.config import get_settings
    from agentalloy.embed_provider import get_embed_client

    settings = get_settings()
    client = get_embed_client(settings)
    model = settings.runtime_embedding_model

    def embed(text: str) -> list[float]:
        # ``search_document:`` is the same document prefix reembed uses, so the
        # probe's vectors live in the same space as the corpus it compares to.
        return client.embed(model=model, texts=[f"search_document: {text}"])[0]

    return embed


def promote_lesson(
    slug: str,
    *,
    root: Path,
    allow_duplicates: bool = False,
    embed: EmbedFn | None = None,
    vector_store: Any | None = None,
    install: InstallFn | None = None,
    symbol_resolver: SymbolResolverFn | None = None,
    skill_store: Any | None = None,
) -> dict[str, Any]:
    """Promote ``docs/solutions/<slug>.md`` into the corpus. Returns a result dict.

    The ``embed`` / ``vector_store`` / ``install`` / ``symbol_resolver`` /
    ``skill_store`` seams are injected in tests; in production they resolve to
    the real embed client, the open fragment store, ``install_local_pack``, a
    read-only code-index symbol lookup, and the skill corpus store.
    """
    from agentalloy.config import get_settings

    # Validate before any path construction — `slug` is user-controlled (a CLI
    # arg) and is used directly to build the lesson-read path below. Mirrors
    # new_skill_pack._SKILL_ID_RE / install_pack._PACK_NAME_RE, whose docstrings
    # are explicit about the same threat: no path traversal (`..`, `/`) or scheme
    # injection via a generated/consumed file path. Without this, a slug like
    # `../../../secret-notes/private` reads and ingests an arbitrary `.md` file
    # from outside docs/solutions/ into the local corpus.
    if not _SKILL_ID_RE.match(slug):
        return {
            "schema_version": SCHEMA_VERSION,
            "action": "invalid_slug",
            "slug": slug,
            "error": (
                f"slug '{slug}' contains disallowed characters. Must match "
                "[a-zA-Z0-9][a-zA-Z0-9_-]{0,63} (no slashes, dots, or path traversal)."
            ),
        }

    lesson_path = root / "docs" / "solutions" / f"{slug}.md"
    if not lesson_path.is_file():
        return {
            "schema_version": SCHEMA_VERSION,
            "action": "lesson_not_found",
            "slug": slug,
            "error": f"no lesson at docs/solutions/{slug}.md — nothing to promote.",
        }

    gen = generate_lesson_pack(lesson_path, root / ".agentalloy" / "custom-skills")
    if gen.get("action") != "generated":
        return gen
    pack_dir = Path(gen["pack_dir"])
    fragment_texts: list[str] = gen["fragment_contents"]

    settings = get_settings()

    # --- pre-ingest dedup probe -------------------------------------------
    store = vector_store
    store_opened_here = False
    if store is None:
        try:
            from agentalloy.storage.open import open_fragments

            store = open_fragments(settings)
            store_opened_here = True
        except Exception:
            # No corpus yet (fresh install) → nothing to duplicate against.
            store = None

    hard_hits: list[Any] = []
    probe_error: str | None = None
    if store is not None:
        try:
            embed_fn = embed or _default_embed()
            hard_hits = probe_lesson_duplicates(
                fragment_texts,
                embed=embed_fn,
                vector_store=store,
                hard_similarity=settings.dedup_hard_threshold,
                soft_similarity=settings.dedup_soft_threshold,
            )
        except Exception as exc:  # embed server down, dim mismatch, corrupt store, ...
            probe_error = str(exc)
        finally:
            if store_opened_here:
                close = getattr(store, "close", None)
                if callable(close):
                    close()

    # Fail closed: if we could not run the dedup check, do NOT install (the rail
    # doesn't roll back, so an unchecked install could bloat the corpus). The user
    # can bypass the check explicitly with --allow-duplicates.
    if probe_error and not allow_duplicates:
        return {
            "schema_version": SCHEMA_VERSION,
            "action": "dedup_probe_failed",
            "slug": slug,
            "skill_id": gen["skill_id"],
            "pack_dir": str(pack_dir),
            "error": (
                f"could not check '{slug}' for duplicates ({probe_error}). Not installed. "
                "Re-run with --allow-duplicates to skip the dedup check."
            ),
        }

    if hard_hits and not allow_duplicates:
        dups = sorted({getattr(h, "skill_id", "?") for h in hard_hits})
        return {
            "schema_version": SCHEMA_VERSION,
            "action": "duplicate_refused",
            "slug": slug,
            "skill_id": gen["skill_id"],
            "pack_dir": str(pack_dir),
            "duplicates": dups,
            "error": (
                f"lesson '{slug}' duplicates existing corpus skill(s) {dups} "
                f"(cosine >= {settings.dedup_hard_threshold}). Not installed. "
                "Re-run with --allow-duplicates to install anyway."
            ),
        }

    # --- install through the existing rail --------------------------------
    install_fn = install
    if install_fn is None:
        from agentalloy.install.subcommands.install_pack import install_local_pack

        install_fn = install_local_pack
    install_result = install_fn(pack_dir, root=root, strict=True, allow_duplicates=allow_duplicates)

    # --- symbol-linked-rationale: resolve + link named symbols -------------
    # Additive only — a resolution/linking failure must never turn a
    # successful promotion into a failed one (see design §4).
    unresolved_symbols: list[str] = []
    lesson_text = lesson_path.read_text(encoding="utf-8")
    symbol_names = _lesson_symbols(lesson_text)
    if symbol_names:
        try:
            from agentalloy.code_index.slug import repo_slug as derive_repo_slug

            repo: str | None = derive_repo_slug(root)
        except Exception:
            repo = None

        if repo is None:
            unresolved_symbols = list(symbol_names)
        else:
            resolver = symbol_resolver or _default_symbol_exists
            resolved: list[str] = []
            for name in symbol_names:
                (resolved if resolver(repo, name) else unresolved_symbols).append(name)

            if resolved:
                from agentalloy.reads.rationale_links import link_symbol

                store_provided = skill_store is not None
                store = skill_store
                if store is None:
                    from agentalloy.storage.open import open_skills

                    store = open_skills(get_settings(), read_only=False)
                try:
                    for name in resolved:
                        link_symbol(
                            store, repo_slug=repo, qualified_name=name, skill_id=gen["skill_id"]
                        )
                finally:
                    if not store_provided:
                        store.close()

    return {
        "schema_version": SCHEMA_VERSION,
        "action": "promoted",
        "slug": slug,
        "skill_id": gen["skill_id"],
        "pack_dir": str(pack_dir),
        "domain_tags": gen.get("domain_tags"),
        "soft_or_forced_duplicates": sorted({getattr(h, "skill_id", "?") for h in hard_hits})
        or None,
        "install": install_result,
        "unresolved_symbols": unresolved_symbols,
    }


# ---------------------------------------------------------------------------
# Subcommand interface
# ---------------------------------------------------------------------------


def add_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],  # pyright: ignore[reportPrivateUsage]
) -> None:
    p = subparsers.add_parser(
        "lessons",
        help="Promote codified compound-engineering lessons (docs/solutions/*.md) into the corpus.",
    )
    sub = p.add_subparsers(dest="lessons_cmd")
    pr = sub.add_parser(
        "promote",
        help="Turn docs/solutions/<slug>.md into a domain-skill pack and install it (dedup-gated).",
    )
    pr.add_argument("slug", help="Lesson slug — the basename of docs/solutions/<slug>.md.")
    pr.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Install even if a hard cross-pack near-duplicate (cosine >= 0.92) is found.",
    )
    add_json_flag(pr)
    pr.set_defaults(func=_run_promote)
    p.set_defaults(func=lambda _args: p.print_help() or 1)


def _render_human(result: dict[str, Any]) -> None:
    action = result.get("action")
    print_rich("\n  [bold]lessons promote[/bold]\n")
    if action == "promoted":
        print_rich(f"  [green]promoted[/green] {result.get('slug')} -> {result.get('skill_id')}")
        print_rich(f"  pack: {result.get('pack_dir')}")
        print_rich(f"  tags: {', '.join(result.get('domain_tags') or [])}")
        forced = result.get("soft_or_forced_duplicates")
        if forced:
            print_rich(f"  [yellow]note[/yellow]: installed over near-duplicate(s) {forced}")
    elif action == "duplicate_refused":
        print_rich(f"  [red]refused[/red]: {result.get('error')}")
    else:
        print_rich(f"  [red]FAILED[/red]: {result.get('error', action)}")
    print_rich()


def _run_promote(args: argparse.Namespace) -> int:
    from agentalloy.install.state import _repo_root  # pyright: ignore[reportPrivateUsage]

    result = promote_lesson(
        args.slug,
        root=_repo_root(),
        allow_duplicates=getattr(args, "allow_duplicates", False),
    )
    write_result(result, args, human_fn=_render_human)
    return 0 if result.get("action") == "promoted" else 1
