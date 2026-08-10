"""Centralized Dependency Injection for AgentAlloy.

Instead of dumping services onto `app.state` and having routers reach into
`request.app.state`, we expose pure Python functions that return the required
services. The `lifespan` context manager in `app.py` builds the `AppResources`
container at startup and binds it here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # type-only; avoids runtime import cycles
    import httpx

    from agentalloy.api.anthropic_passthrough import AnthropicPassthroughClient
    from agentalloy.api.diagnostics_router import DiagnosticsChecker
    from agentalloy.api.health_router import HealthChecker, ReadinessChecker
    from agentalloy.api.telemetry_router import TelemetryQuerier
    from agentalloy.code_index.api.state import CodeIndexState
    from agentalloy.config import Settings
    from agentalloy.embed_provider import EmbedClient
    from agentalloy.orchestration.compose import ComposeOrchestrator
    from agentalloy.orchestration.retrieve import RetrieveOrchestrator
    from agentalloy.runtime_state import RuntimeCache
    from agentalloy.storage.protocols import FragmentStore, SkillStore, TelemetryStore
    from agentalloy.telemetry import DuckDBTelemetryWriter


@dataclass
class AppResources:
    """Container for all lifespan-scoped application services and clients."""

    settings: Settings
    store: SkillStore | None = None
    vector_store: FragmentStore | None = None
    telemetry_store: TelemetryStore | None = None
    embed_client: EmbedClient | None = None
    telemetry: DuckDBTelemetryWriter | None = None

    runtime: RuntimeCache | None = None
    runtime_load_error: str | None = None

    compose_orchestrator: ComposeOrchestrator | None = None
    retrieve_orchestrator: RetrieveOrchestrator | None = None

    health_checker: HealthChecker | None = None
    readiness_checker: ReadinessChecker | None = None
    diagnostics_checker: DiagnosticsChecker | None = None
    telemetry_querier: TelemetryQuerier | None = None

    embed_async_client: httpx.AsyncClient | None = None
    upstream_client: httpx.AsyncClient | None = None

    anthropic_passthrough_client: AnthropicPassthroughClient | None = None
    responses_passthrough_client: AnthropicPassthroughClient | None = None

    upstream_client_cache: dict[str, httpx.AsyncClient] = field(default_factory=dict)
    code_index_state: CodeIndexState | None = None


_resources: AppResources | None = None


def set_app_resources(resources: AppResources | None) -> None:
    """Bind (or clear) the initialized resources during app lifespan."""
    global _resources
    _resources = resources


def get_app_resources() -> AppResources:
    """Fetch the bound resources. Raises if called before lifespan starts."""
    if _resources is None:
        raise RuntimeError(
            "AppResources are not initialized. Ensure this is called within a "
            "FastAPI request/lifespan after app startup."
        )
    return _resources


# --- Dependency Providers (use via Depends(...)) ---
def get_settings() -> Settings:
    if _resources is not None:
        return _resources.settings
    from agentalloy.config import get_settings as _get_settings

    return _get_settings()


def get_skill_store() -> SkillStore | None:
    return _resources.store if _resources is not None else None


def get_vector_store() -> FragmentStore | None:
    """The Lance fragment store (vector + BM25) — app.state.vector_store."""
    return _resources.vector_store if _resources is not None else None


def get_telemetry_store() -> TelemetryStore | None:
    """The service-owned telemetry.duck — app.state.telemetry_store."""
    return _resources.telemetry_store if _resources is not None else None


def get_embed_client() -> EmbedClient | None:
    return _resources.embed_client if _resources is not None else None


def get_runtime_cache() -> RuntimeCache | None:
    return _resources.runtime if _resources is not None else None


def get_runtime_load_error() -> str | None:
    """Startup cache load error string, if any."""
    return _resources.runtime_load_error if _resources is not None else None


def get_compose_orchestrator() -> ComposeOrchestrator | None:
    return _resources.compose_orchestrator if _resources is not None else None


def get_retrieve_orchestrator() -> RetrieveOrchestrator | None:
    return _resources.retrieve_orchestrator if _resources is not None else None


def get_health_checker() -> HealthChecker | None:
    return _resources.health_checker if _resources is not None else None


def get_readiness_checker() -> ReadinessChecker | None:
    return _resources.readiness_checker if _resources is not None else None


def get_diagnostics_checker() -> DiagnosticsChecker | None:
    return _resources.diagnostics_checker if _resources is not None else None


def get_telemetry_querier() -> TelemetryQuerier | None:
    return _resources.telemetry_querier if _resources is not None else None


def get_embed_async_client() -> httpx.AsyncClient | None:
    return _resources.embed_async_client if _resources is not None else None


def get_upstream_client() -> httpx.AsyncClient | None:
    return _resources.upstream_client if _resources is not None else None


def get_anthropic_passthrough_client() -> AnthropicPassthroughClient | None:
    return _resources.anthropic_passthrough_client if _resources is not None else None


def get_responses_passthrough_client() -> AnthropicPassthroughClient | None:
    return _resources.responses_passthrough_client if _resources is not None else None


def get_code_index_state() -> CodeIndexState | None:
    return _resources.code_index_state if _resources is not None else None
