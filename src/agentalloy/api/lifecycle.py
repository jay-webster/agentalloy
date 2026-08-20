"""Modular lifecycle initialization and teardown for AgentAlloy.

Breaks the monolithic `lifespan` context manager into single-responsibility
setup/teardown functions, each independently testable and composable.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from fastapi import FastAPI

from agentalloy.api.anthropic_passthrough import AnthropicPassthroughClient
from agentalloy.api.deps import AppResources
from agentalloy.api.diagnostics_router import DiagnosticsChecker
from agentalloy.api.health_router import HealthChecker, ReadinessChecker
from agentalloy.api.telemetry_router import TelemetryQuerier
from agentalloy.config import Settings
from agentalloy.embed_provider import EmbedClient, get_embed_client
from agentalloy.orchestration.compose import ComposeOrchestrator
from agentalloy.orchestration.retrieve import RetrieveOrchestrator
from agentalloy.runtime_state import RuntimeCache, load_runtime_cache
from agentalloy.storage.open import open_fragments, open_skills, open_telemetry
from agentalloy.storage.protocols import FragmentStore, SkillStore, TelemetryStore
from agentalloy.telemetry import DuckDBTelemetryWriter

if TYPE_CHECKING:
    from agentalloy.code_index.api.state import CodeIndexState

logger = logging.getLogger(__name__)


def init_storage(settings: Settings) -> tuple[
    SkillStore, FragmentStore, TelemetryStore, EmbedClient, DuckDBTelemetryWriter
]:
    """Initialize storage handles and embedding client.
    
    Returns:
        Tuple of (store, vector_store, telemetry_store, embed_client, telemetry_writer)
    """
    settings.ensure_data_dirs()
    
    # Container data directory (only in deployment contexts)
    if Path("/.dockerenv").exists() or Path("/app").is_dir():
        Path("/app/data").mkdir(parents=True, exist_ok=True)
    
    # Skill store: migrate schema, then serve read-only
    _writer = open_skills(settings, read_only=False)
    try:
        _writer.migrate()
    finally:
        _writer.close()
    
    store = open_skills(settings, read_only=True)
    vector_store = open_fragments(settings)
    telemetry_store = open_telemetry(settings, read_only=False)
    embed_client = get_embed_client(settings)
    telemetry = DuckDBTelemetryWriter(telemetry_store)
    
    return store, vector_store, telemetry_store, embed_client, telemetry


def init_runtime_cache(store: SkillStore) -> tuple[RuntimeCache | None, str | None]:
    """Load the runtime cache from the skill store.
    
    Returns:
        Tuple of (runtime_cache, runtime_load_error)
    """
    runtime: RuntimeCache | None = None
    runtime_load_error: str | None = None
    
    try:
        runtime = load_runtime_cache(store)
    except Exception as exc:
        logger.error("Runtime cache load failed — service will start in degraded mode: %s", exc)
        runtime_load_error = str(exc)
    
    return runtime, runtime_load_error


def init_orchestration(
    runtime: RuntimeCache | None,
    store: SkillStore,
    embed_client: EmbedClient,
    vector_store: FragmentStore,
    telemetry: DuckDBTelemetryWriter,
    settings: Settings,
) -> tuple[ComposeOrchestrator, RetrieveOrchestrator]:
    """Wire compose and retrieve orchestrators.
    
    Prefers runtime cache when available, falls back to store for existing
    store-backed code paths (e.g. skill inspection).
    """
    source = runtime if runtime is not None else store
    
    orchestrator = ComposeOrchestrator(
        source,
        embed_client,
        vector_store,
        telemetry,
        embedding_model=settings.runtime_embedding_model,
    )
    
    retrieve_orch = RetrieveOrchestrator(
        source,
        embed_client,
        vector_store,
        telemetry,
        embedding_model=settings.runtime_embedding_model,
    )
    
    return orchestrator, retrieve_orch


def init_checkers(
    store: SkillStore,
    runtime: RuntimeCache | None,
    embed_client: EmbedClient,
    telemetry_store: TelemetryStore,
    settings: Settings,
    runtime_load_error: str | None,
) -> tuple[HealthChecker, ReadinessChecker | None, DiagnosticsChecker, TelemetryQuerier]:
    """Initialize health, readiness, diagnostics, and telemetry checkers."""
    health_checker = HealthChecker(
        store,
        embed_client,
        telemetry_store,
        settings.runtime_embedding_model,
        runtime_load_error=runtime_load_error,
        upstream_summary=(
            f"url={settings.upstream_url} model={settings.upstream_model}"
            if settings.upstream_configured()
            else None
        ),
    )
    
    # Readiness checker: only when /app exists (container deployment)
    readiness_checker: ReadinessChecker | None = None
    app_dir = Path("/app")
    if app_dir.is_dir():
        readiness_checker = ReadinessChecker(app_dir=app_dir)
    
    diagnostics_checker = DiagnosticsChecker(store, runtime, health_checker)
    telemetry_querier = TelemetryQuerier(telemetry_store)
    
    return health_checker, readiness_checker, diagnostics_checker, telemetry_querier


def init_proxy_clients(settings: Settings) -> tuple[
    httpx.AsyncClient | None,
    httpx.AsyncClient | None,
    AnthropicPassthroughClient,
    AnthropicPassthroughClient,
]:
    """Initialize proxy and passthrough HTTP clients.
    
    Returns:
        Tuple of (embed_async_client, upstream_client, anthropic_passthrough_client, responses_passthrough_client)
    """
    import contextlib as _ctx
    
    # Embed proxy passthrough client
    embed_async_client: httpx.AsyncClient | None = None
    with _ctx.suppress(Exception):
        embed_async_client = httpx.AsyncClient(
            base_url=settings.runtime_embed_base_url.rstrip("/"),
            headers={"Content-Type": "application/json"},
            timeout=httpx.Timeout(connect=5.0, read=30.0),
        )
    
    # Upstream LLM client (for proxy passthrough)
    upstream_client: httpx.AsyncClient | None = None
    if settings.upstream_configured():
        upstream_headers: dict[str, str] = {"Content-Type": "application/json"}
        if settings.upstream_api_key:
            upstream_headers["Authorization"] = f"Bearer {settings.upstream_api_key}"
        upstream_client = httpx.AsyncClient(
            base_url=settings.upstream_url.rstrip("/"),
            headers=upstream_headers,
            timeout=httpx.Timeout(connect=5.0, read=300.0, write=30.0, pool=5.0),
        )
    
    # Native Anthropic passthrough (holds NO credential, forwards verbatim)
    anthropic_passthrough_client = AnthropicPassthroughClient(settings.anthropic_upstream_url)
    
    # Native OpenAI Responses passthrough (same auth-transparent contract)
    responses_passthrough_client = AnthropicPassthroughClient(settings.responses_upstream_url)
    
    return embed_async_client, upstream_client, anthropic_passthrough_client, responses_passthrough_client


def init_code_index(
    app: FastAPI,
    settings: Settings,
    embed_client: EmbedClient,
) -> tuple[CodeIndexState | None, asyncio.Task | None]:
    """Initialize code-index module if enabled and installed.
    
    Returns:
        Tuple of (code_index_state, code_index_refresh_task)
    """
    if getattr(app.state, "module_status", {}).get("code_index") != "enabled":
        return None, None
    
    from agentalloy.code_index.api.state import CodeIndexState
    from agentalloy.code_index.store import open_jobs
    
    ci_jobs = open_jobs(settings)
    code_index_state = CodeIndexState(
        settings=settings,
        embed_client=embed_client,
        jobs=ci_jobs,
    )
    
    # Retire orphaned job rows from previous dead processes
    ci_jobs.sweep_interrupted(code_index_state.worker_token)
    
    if settings.code_index_watch:
        code_index_state.enable_watch(asyncio.get_running_loop())
        code_index_state.start_enrolled_watches()
    
    code_index_state.log_stale_repos()
    
    # Auto-refresh task (opt-in via CODE_INDEX_REFRESH_SECONDS > 0)
    refresh_task: asyncio.Task | None = None
    if settings.code_index_refresh_seconds > 0:
        from agentalloy.app import _code_index_refresh_loop
        refresh_task = asyncio.create_task(
            _code_index_refresh_loop(code_index_state, settings.code_index_refresh_seconds)
        )
    
    return code_index_state, refresh_task


def start_background_tasks(app: FastAPI) -> asyncio.Task:
    """Start background release-check loop.
    
    Returns:
        The release_check_task
    """
    from agentalloy.app import _release_check_loop
    return asyncio.create_task(_release_check_loop())


async def shutdown_all(
    resources: AppResources,
    release_check_task: asyncio.Task | None,
    code_index_refresh_task: asyncio.Task | None,
    code_index_state: CodeIndexState | None,
) -> None:
    """Clean shutdown: cancel tasks, close clients, close stores.
    
    Guards each close independently so a failure in one doesn't skip the rest.
    Uses getattr for close/aclose to satisfy static type checkers on protocols.
    """
    # Cancel background tasks
    for task in (release_check_task, code_index_refresh_task):
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task
    
    # Code-index shutdown
    if code_index_state is not None:
        with suppress(Exception):
            await code_index_state.aclose()
    
    # Close HTTP clients
    cached_upstreams = list(resources.upstream_client_cache.values())
    for aclient in (resources.embed_async_client, resources.upstream_client, *cached_upstreams):
        if aclient is not None:
            with suppress(Exception):
                await aclient.aclose()
    
    # Close passthrough clients
    for client in (resources.anthropic_passthrough_client, resources.responses_passthrough_client):
        if client is not None:
            with suppress(Exception):
                await client.aclose()
    
    # Close storage handles
    for closeable in (resources.telemetry, resources.embed_client,
                      resources.vector_store, resources.store,
                      resources.telemetry_store):
        close_fn = getattr(closeable, "close", None)
        if callable(close_fn):
            with suppress(Exception):
                close_fn()