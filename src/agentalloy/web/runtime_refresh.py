"""Reload the in-memory RuntimeCache after an in-process corpus write.

The service loads its RuntimeCache once at boot; a corpus write made from a
web endpoint (POST /api/reembed, the wizard's pack install) would otherwise
serve stale skills until the next restart. Call this after the write completes
and the store handle has reconnected (see ``DuckDBSkillStore.released``).

The CLI writer path doesn't need this: ``agentalloy reembed`` restarts the
service it stopped, and the restart reloads the cache.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def refresh_runtime_cache() -> bool:
    """Best-effort cache reload + swap into the live orchestrators."""
    from agentalloy.api.deps import get_app_resources
    from agentalloy.runtime_state import load_runtime_cache

    try:
        resources = get_app_resources()
    except RuntimeError:
        return False
    if resources.store is None:
        return False
    try:
        runtime = load_runtime_cache(resources.store)
    except Exception as exc:  # noqa: BLE001 — stale cache beats a dead service
        logger.warning("runtime cache refresh failed — serving the previous cache: %s", exc)
        return False
    resources.runtime = runtime
    for orch in (resources.compose_orchestrator, resources.retrieve_orchestrator):
        if orch is not None:
            orch.rebind_source(runtime)
    logger.info("runtime cache refreshed after in-process corpus write")
    return True
