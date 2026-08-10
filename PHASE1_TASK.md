# AgentAlloy — Phase 1 Refactor Task (State Management & Dependency Injection)

## Ground rules (read first, do not violate)
1. `pyright` is used. Keep type hints valid. Run `pyright` on touched files after each step.
2. **Do NOT regress naming:**
   - `get_vector_store()` → the **Lance FragmentStore** (`app.state.vector_store`).
   - `get_telemetry_store()` → the **DuckDB telemetry store** (`app.state.telemetry_store`).
   - `proxy_router.py`'s OLD `get_vector_store()` returned the **telemetry** store. Every proxy call site that used it must now use `get_telemetry_store()`, **not** `get_vector_store()`.
3. Keep `app.state.module_status` and `app.state.release_check_task`. Remove all other `app.state.<service>` writes.
4. This is a DI refactor only — do not change business logic inside compose/retrieve/proxy internals.
5. Work incrementally; run `python -m pytest -x -q` and `pyright` after each step.

## Step 0 — Prerequisites
Confirm these exist (they were added as part of this task):
- `src/agentalloy/api/deps.py`
- `scripts/migrate_phase1_tests.py`

## Step 1 — Validate `deps.py` import paths
`deps.py` uses `TYPE_CHECKING` imports. Run `pyright src/agentalloy/api/deps.py`. Fix any import path that doesn't resolve against the real layout (keep them under `TYPE_CHECKING`). Pay attention to: `storage.protocols.FragmentStore`, `code_index.api.state.CodeIndexState`, `config.Settings`, `embed_provider.EmbedClient`, `runtime_state.RuntimeCache`, `telemetry.DuckDBTelemetryWriter`.

## Step 2 — Clean routers (mechanical)
For each file: delete the local dummy provider that raises `RuntimeError`, add the deps import, and repoint `Depends(...)`.

- **`api/compose_router.py`**: delete `get_orchestrator()`; add `from agentalloy.api.deps import get_compose_orchestrator`; replace `Depends(get_orchestrator)` → `Depends(get_compose_orchestrator)` (both endpoints). Preserve the `FromContractRequest` import.
- **`api/retrieve_router.py`**: delete `get_retrieve_orchestrator()` dummy; add `from agentalloy.api.deps import get_retrieve_orchestrator`. `Depends(get_retrieve_orchestrator)` stays.
- **`api/skill_router.py`**: delete `get_skill_store()` dummy; add `from agentalloy.api.deps import get_skill_store`. `Depends(get_skill_store)` stays.

## Step 3 — Routers reading `request.app.state` directly → convert to `Depends`
- **`api/diagnostics_router.py`**: add `from agentalloy.api.deps import get_diagnostics_checker, get_skill_store, get_vector_store`.
  - `runtime_diagnostics(checker: DiagnosticsChecker | None = Depends(get_diagnostics_checker))` — drop `request`, drop the `getattr(..., "diagnostics_checker")` line, keep the `if checker is None` stub.
  - `corpus_diagnostics(store: SkillStore | None = Depends(get_skill_store), vector_store: FragmentStore | None = Depends(get_vector_store))` — drop `request` and the `app.state` gets; use the injected params. Import `FragmentStore` for the hint if needed.
- **`api/telemetry_router.py`**: add `from agentalloy.api.deps import get_telemetry_querier`. In `list_traces`, `get_savings`, `get_coverage`: drop `request`, add `querier: TelemetryQuerier | None = Depends(get_telemetry_querier)`, delete the `getattr(..., "telemetry_querier")` lines, keep None-fallbacks.
- **`api/health_router.py`**: add `from agentalloy.api.deps import get_health_checker, get_readiness_checker, get_runtime_load_error`.
  - `health(request: Request, checker: HealthChecker | None = Depends(get_health_checker))` — keep `request` ONLY to read `module_status` via `getattr(request.app.state, "module_status", None)`; delete the health_checker get.
  - `readiness(checker: ReadinessChecker | None = Depends(get_readiness_checker), runtime_load_error: str | None = Depends(get_runtime_load_error))` — drop `request`; use injected params; keep the 503 JSONResponse branch.

## Step 4 — `api/proxy_router.py` (surgical — read the file first)
- Delete every ad-hoc provider reading `request.app.state`: `get_upstream_client`, `get_embed_client`, `get_embed_async_client`, `get_vector_store`, `get_orchestrator_for_proxy`, `get_settings_for_proxy`.
- Add `from agentalloy.api.deps import get_upstream_client, get_embed_client, get_embed_async_client, get_compose_orchestrator, get_settings, get_telemetry_store, get_app_resources`.
- Handler signatures use `Depends(...)` for the above. **Where the old code called its local `get_vector_store()` (telemetry store), use `get_telemetry_store()`.**
- Refactor `_get_or_create_upstream_client(app, base_url, api_key)` → `_get_or_create_upstream_client(base_url, api_key)`; replace `app.state.upstream_client_cache` with `get_app_resources().upstream_client_cache`; update call sites (e.g. `_resolve_upstream`) to drop the `app` arg.
- Leave streaming/telemetry internals otherwise unchanged; re-check against the real file.

## Step 5 — Passthrough routers (repoint imports from proxy_router → deps)
- **`api/proxy_passthrough_router.py`**: remove `from agentalloy.api.proxy_router import (get_embed_client, get_orchestrator_for_proxy, get_vector_store)`; delete `get_passthrough_client(request)`; add `from agentalloy.api.deps import get_anthropic_passthrough_client, get_compose_orchestrator, get_embed_client, get_telemetry_store`. Endpoint uses `Depends(get_anthropic_passthrough_client)`, `Depends(get_compose_orchestrator)`, `vector_store: TelemetryStore | None = Depends(get_telemetry_store)` (GOTCHA), `Depends(get_embed_client)`.
- **`api/proxy_responses_router.py`**: remove the proxy_router import block; delete `get_responses_client(request)`; add `from agentalloy.api.deps import get_compose_orchestrator, get_embed_client, get_responses_passthrough_client, get_telemetry_store`. Endpoint uses `Depends(get_responses_passthrough_client)`, `Depends(get_compose_orchestrator)`, `vector_store: TelemetryStore | None = Depends(get_telemetry_store)` (GOTCHA), `Depends(get_embed_client)`.

## Step 6 — `web/runtime_refresh.py`
Replace the file so `refresh_runtime_cache()` takes **no** `app` arg and uses `get_app_resources()` (see AFTER version below). Then grep the repo for `refresh_runtime_cache(` and update every call site to drop the `app` argument.

```python
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
```

## Step 7 — `app.py` (read the file first; reconcile real variable names)
**Remove:**
- Imports of the dummy providers from compose_router / retrieve_router / skill_router.
- Every `app.dependency_overrides[...] = ...` in lifespan (incl. the code-index `get_code_index_state` override).
- Every `app.state.<service> = ...` **except** keep `module_status` and `release_check_task`.
- Every `app.dependency_overrides.pop(...)` in `finally`.

**Change:** the readiness checker to a local `readiness_checker = ReadinessChecker(app_dir=app_dir) if Path("/app").is_dir() else None` (same `is_dir` guard).

**Add** (end of lifespan setup, just before `try: yield`) — match the real local var names:
```python
    from agentalloy.api.deps import AppResources, set_app_resources

    resources = AppResources(
        settings=settings,
        store=store,
        vector_store=vector_store,
        telemetry_store=telemetry_store,
        embed_client=embed_client,
        telemetry=telemetry,
        runtime=runtime,
        runtime_load_error=runtime_load_error,
        compose_orchestrator=orchestrator,
        retrieve_orchestrator=retrieve_orch,
        health_checker=health_checker,
        readiness_checker=readiness_checker,
        diagnostics_checker=diagnostics_checker,
        telemetry_querier=telemetry_querier,
        embed_async_client=embed_async_client,
        upstream_client=upstream_client,
        anthropic_passthrough_client=anthropic_passthrough_client,
        responses_passthrough_client=responses_passthrough_client,
        code_index_state=code_index_state,
    )
    set_app_resources(resources)
```

**Update** the `finally` cleanup to close via `resources` (keep existing task cancellation first):
```python
    finally:
        # keep existing task cancellation (release_check_task, code_index tasks)
        if code_index_state is not None:
            with suppress(Exception):
                await code_index_state.aclose()
        cached_upstreams = list(resources.upstream_client_cache.values())
        for aclient in (resources.embed_async_client, resources.upstream_client, *cached_upstreams):
            if aclient is not None:
                with suppress(Exception):
                    await aclient.aclose()
        with suppress(Exception):
            await resources.anthropic_passthrough_client.aclose()
        with suppress(Exception):
            await resources.responses_passthrough_client.aclose()
        for closeable in (resources.telemetry, resources.embed_client,
                          resources.vector_store, resources.store,
                          resources.telemetry_store):
            with suppress(Exception):
                closeable.close()
        set_app_resources(None)
```
Reconcile every name against the actual lifespan. If a service is optional/absent in this build, pass the real object or `None`.

## Step 8 — Migrate tests
1. Run `python scripts/migrate_phase1_tests.py`.
2. Fix resulting import errors: replace imports of the deleted dummy providers with imports from `agentalloy.api.deps`.
3. Grep `tests/` for `app.state.` and update direct pokes to use `set_app_resources(<mock AppResources>)` or `unittest.mock.patch("agentalloy.api.deps.get_app_resources")`.

## Step 9 — Verify (fix until clean)
1. `pyright` (repo's type-check command)
2. `ruff check .` and `ruff format --check .`
3. `python -m pytest -x -q`
Report any failure with file + error.