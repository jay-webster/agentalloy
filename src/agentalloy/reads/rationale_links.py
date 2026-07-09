"""symbol-linked-rationale — (repo_slug, qualified_name) -> promoted-skill queries.

Sibling to :mod:`agentalloy.reads.active`: pure functions over a
``SkillStore``, no ORM. The link table (``symbol_rationale_links``) lives in
``agentalloy.duck`` — see ``storage/skill_store.py``'s schema docstring for why
it is *not* in the code index's ``graph.duck`` (that store's own docstring
reserves writes for the service process and frames its contents as derived,
disposable data; a human-curated link is neither).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentalloy.reads.models import RationaleHit

if TYPE_CHECKING:
    from agentalloy.storage.protocols import SkillStore  # pyright: ignore[reportUnusedImport]

_RATIONALE_JOIN = (
    "FROM symbol_rationale_links srl "
    "JOIN skills s ON s.skill_id = srl.skill_id AND s.deprecated = false "
    "JOIN skill_versions v ON v.version_id = s.current_version_id AND v.status = 'active' "
    "JOIN fragments f ON f.version_id = v.version_id AND f.fragment_type = 'rationale'"
)


def link_symbol(store: SkillStore, *, repo_slug: str, qualified_name: str, skill_id: str) -> None:
    """Idempotently link a code symbol to a promoted skill's rationale.

    Re-linking the same ``(repo_slug, qualified_name, skill_id)`` triple is a
    no-op, not an error — the primary key makes this a plain conflict-skip.
    """
    store.execute(
        "INSERT INTO symbol_rationale_links (repo_slug, qualified_name, skill_id, linked_at) "
        "VALUES ($repo_slug, $qualified_name, $skill_id, CURRENT_TIMESTAMP) "
        "ON CONFLICT (repo_slug, qualified_name, skill_id) DO NOTHING",
        {"repo_slug": repo_slug, "qualified_name": qualified_name, "skill_id": skill_id},
    )


def rationale_for_symbol(
    store: SkillStore, *, repo_slug: str, qualified_name: str
) -> list[RationaleHit]:
    """Every active, non-deprecated skill linked to this symbol, with its rationale text.

    ``[]`` when nothing is linked — never ``None``, never raises. Multiple
    linked skills are all returned, unranked (no policy needed for a first
    slice — see the design's "Design surface" note on multi-skill links).
    """
    rows = store.execute(
        f"SELECT srl.skill_id, f.content {_RATIONALE_JOIN} "
        "WHERE srl.repo_slug = $repo_slug AND srl.qualified_name = $qualified_name "
        "ORDER BY f.sequence",
        {"repo_slug": repo_slug, "qualified_name": qualified_name},
    )
    return [RationaleHit(skill_id=str(r[0]), rationale=str(r[1])) for r in rows]
