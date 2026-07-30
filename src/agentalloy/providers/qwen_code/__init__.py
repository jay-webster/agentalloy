"""Qwen Code provider — HarnessSpec registration for Qwen Code CLI.

Registers the ``qwen-code`` harness in REGISTRY with:
- Protocol: OPENAI (Qwen Code speaks the OpenAI Chat Completions API)
- Capabilities: PROXY (proxy wiring via a repo-local settings.json)
- env_builder: sets QWEN_HOME so Qwen Code picks up the repo-local
  ``.qwen/settings.json`` (which already carries the per-repo
  ``/proj/<token>`` base URL) instead of the global config
- install_writer: repo-local ``.qwen/settings.json`` + QWEN_HOME activation
  carriers (delegates to the live wire_harness path)
"""

from __future__ import annotations

import os
from pathlib import Path

from agentalloy.providers import REGISTRY
from agentalloy.providers.base import (
    Capability,
    HarnessSpec,
    Protocol,
    WireRecord,
)

from . import install


def _env_builder(port: int) -> dict[str, str]:
    """Build environment dict for the qwen-code subprocess.

    Qwen Code ignores env-var base-url overrides for its custom provider
    config, so — like codex's CODEX_HOME — the only routing vector is the
    repo-local ``.qwen/settings.json`` the install_writer wrote (it already
    carries the per-repo ``/proj/<token>`` base URL). This just points
    QWEN_HOME at that repo-local directory.
    """
    _ = port
    return {"QWEN_HOME": os.path.join(os.getcwd(), ".qwen")}


def _install_writer(port: int, root: Path, force: bool = False) -> list[WireRecord]:
    """Install persistent wiring for qwen-code.

    Writes the repo-local ``.qwen/settings.json`` + ``QWEN_HOME`` activation
    carriers (via the shared live path).
    """
    return install.apply_persistent_config(port, root, force)


# Register the harness in the global REGISTRY.
REGISTRY["qwen-code"] = HarnessSpec(
    name="qwen-code",
    binary="qwen",
    capabilities=(Capability.PROXY,),
    protocol=Protocol.OPENAI,
    env_builder=_env_builder,
    install_writer=_install_writer,
    upstream_extractor=install.extract_upstream,
)
