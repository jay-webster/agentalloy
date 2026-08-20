# AgentAlloy — Phase 2 Refactor Task (Decouple Lifespan & App Factory)

## Ground rules (read first, do not violate)
1. `pyright` is used. Keep type hints valid. Run `pyright` on touched files after each step.
2. This is a refactor only — do not change business logic or observable behavior.
3. Work incrementally; run `python -m pytest -x -q` and `pyright` after each step.
4. The goal is to break the monolithic `lifespan` context manager into modular, single-responsibility functions.
5. Remove the redundant test override block in `create_app` — tests should use `deps.set_app_resources()` instead.

## Step 0 — Prerequisites
Confirm this exists (created as part of this task):
- `src/agentalloy/api/lifecycle.py`

## Step 1 — Validate `lifecycle.py`
Run `pyright src/agentalloy/api/lifecycle.py`. Fix any import path that doesn't resolve. Pay attention to:
- `agentalloy.code_index.api.state.CodeIndexState` (only under `TYPE_CHECKING`)
- Return type annotations (some use `object` as placeholders for storage protocols)

## Step 2 — Refactor `app.py` lifespan (surgical — read the file first)
Replace the entire monolithic `lifespan` function with a short orchestrator that calls the modular functions from `lifecycle.py`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the runtime store + embedding client for the app lifetime."""
    from agentalloy.api.lifecycle import (
        init_storage,
        init_runtime_cache,
        init_orchestration,
        init_checkers,
        init_proxy_clients,
        init_code_index,
        start_background_tasks,
        shutdown_all,
    )
    from agentalloy.api.deps import AppResources, set_app_resources
    
    settings = get_settings()
    
    # Initialize storage
    store, vector_store, telemetry_store, embed_client, telemetry = init_storage(settings)
    
    # Load runtime cache
    runtime, runtime_load_error = init_runtime_cache(store)
    
    # Wire orchestrators
    orchestrator, retrieve_orch = init_orchestration(
        runtime, store, embed_client, vector_store, telemetry, settings
    )
    
    # Initialize checkers
    health_checker, readiness_checker, diagnostics_checker, telemetry_querier = init_checkers(
        store, runtime, embed_client, telemetry_store, settings, runtime_load_error
    )
    
    # Initialize proxy clients
    embed_async_client, upstream_client, anthropic_passthrough_client, responses_passthrough_client = init_proxy_clients(settings)
    
    # Initialize code-index module (if enabled)
    code_index_state, code_index_refresh_task = init_code_index(app, settings, embed_client)
    
    # Build and bind AppResources
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
    
    # Start background tasks
    release_check_task = start_background_tasks(app)
    
    try:
        yield
    finally:
        await shutdown_all(resources, release_check_task, code_index_refresh_task, code_index_state)
        set_app_resources(None)
```

## Step 3 — Remove redundant test override block from `create_app`
Delete the entire `if not use_default_lifespan:` block (~80 lines) that manually wires `app.dependency_overrides`. This is now redundant with `deps.set_app_resources()`. Tests should use that instead.

Keep the rest of `create_app` unchanged.

## Step 4 — Move background loop functions
Move `_release_check_loop` and `_code_index_refresh_loop` from the top of `app.py` to `lifecycle.py` (they're already referenced there via imports). Delete them from `app.py`.

## Step 5 — Verify (fix until clean)
1. `pyright` (repo's type-check command)
2. `ruff check .` and `ruff format --check .`
3. `python -m pytest -x -q`
Report any failure with file + error.