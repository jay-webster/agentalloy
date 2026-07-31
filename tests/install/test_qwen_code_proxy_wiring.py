"""Tests for Qwen Code proxy wiring (per-repo QWEN_HOME interception)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentalloy.api.proxy_context import decode_proj_token, encode_proj_token
from agentalloy.install.subcommands import wire_harness
from agentalloy.providers.qwen_code.install import extract_upstream
from tests._wire_compat import wire_compat


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    return tmp_path


def _read_repo_settings(root: Path) -> dict[str, object]:
    data = json.loads((root / ".qwen" / "settings.json").read_text())
    assert isinstance(data, dict)
    return data


class TestQwenCodeProxyWiring:
    """qwen-code is inherently per-repo: it wires the repo-local carrier at
    *root* regardless of the requested scope (like claude-code/hermes-agent),
    never touching the user's global ~/.qwen/settings.json."""

    @pytest.fixture(autouse=True)
    def both_managers_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Pin activation-manager detection so tests don't depend on the host PATH."""
        monkeypatch.setattr(wire_harness, "_activation_managers", lambda: {"direnv", "mise"})

    @pytest.fixture(autouse=True)
    def stub_mise_trust(self, monkeypatch: pytest.MonkeyPatch) -> list[Path]:
        """Never touch the real mise trust database; record trust calls."""
        calls: list[Path] = []
        monkeypatch.setattr(wire_harness, "_mise_trust", lambda path: calls.append(path) or True)
        return calls

    def test_scope_is_ignored_always_repo_local(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """User scope still wires the repo-local carrier and never the global config."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        result = wire_compat("qwen-code", port=5555, root=tmp_path, scope="user")

        assert result["integration_vector"] == "proxy"
        assert (tmp_path / ".qwen" / "settings.json").exists()
        assert not (fake_home / ".qwen" / "settings.json").exists()

    def test_repo_scope_writes_proxy_model_block(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Repo scope redirects ``model.baseUrl`` at the proxy's per-repo /proj/<token> URL."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        result = wire_compat("qwen-code", port=6666, root=tmp_path, scope="repo")
        assert result["integration_vector"] == "proxy"

        token = encode_proj_token(tmp_path)
        settings = _read_repo_settings(tmp_path)
        model = settings["model"]
        assert isinstance(model, dict)
        assert model["baseUrl"] == f"http://localhost:6666/proj/{token}/v1"

        # The token round-trips to this repo (how the proxy resolves per-repo state).
        assert decode_proj_token(token) == Path(tmp_path).resolve()

        # Auth-by-adoption: selectedType is openai, no dummy custom_providers block.
        security = settings["security"]
        assert isinstance(security, dict)
        assert security["auth"]["selectedType"] == "openai"

    def test_repo_scope_writes_qwen_home_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Repo scope writes a sourceable env file pinning QWEN_HOME to the repo dir."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        wire_compat("qwen-code", port=6666, root=tmp_path, scope="repo")

        env = tmp_path / ".qwen" / ".agentalloy-env"
        assert env.exists()
        assert 'QWEN_HOME="$PWD/.qwen"' in env.read_text()

    def test_repo_scope_preserves_global_settings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The repo-local settings keep the user's other providers/tuning, only
        redirecting the top-level model.baseUrl and adding a proxy provider entry —
        existing modelProviders.openai[] entries are never overwritten."""
        fake_home = tmp_path / "home"
        (fake_home / ".qwen").mkdir(parents=True)
        (fake_home / ".qwen" / "settings.json").write_text(
            json.dumps(
                {
                    "model": {
                        "name": "qwen3-coder-plus",
                        "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    },
                    "modelProviders": {
                        "openai": [
                            {
                                "id": "dashscope",
                                "name": "DashScope",
                                "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                            }
                        ]
                    },
                    "someOtherSetting": True,
                }
            )
        )
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        wire_compat("qwen-code", port=6666, root=tmp_path, scope="repo")

        settings = _read_repo_settings(tmp_path)
        # Untouched user tuning survives...
        assert settings["someOtherSetting"] is True
        providers = settings["modelProviders"]["openai"]  # type: ignore[index]
        assert {p["id"] for p in providers} == {"dashscope", "agentalloy-proxy"}
        dashscope_entry = next(p for p in providers if p["id"] == "dashscope")
        assert dashscope_entry["baseUrl"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        # ...but the top-level model is redirected at the proxy.
        model = settings["model"]
        assert isinstance(model, dict)
        assert model["baseUrl"].startswith("http://localhost:6666/proj/")
        assert model["name"] == "qwen3-coder-plus"

    def test_repo_scope_inherits_env_key_context_window_and_repoints_default_model(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The proxy provider entry must carry an ``envKey`` (Qwen Code refuses to
        switch models without one) and inherit ``generationConfig.contextWindowSize``
        from the previously active default provider; ``defaultModel.modelId`` must be
        repointed at the proxy or Qwen Code keeps using the old default."""
        fake_home = tmp_path / "home"
        (fake_home / ".qwen").mkdir(parents=True)
        (fake_home / ".qwen" / "settings.json").write_text(
            json.dumps(
                {
                    "model": {
                        "name": "dashscope",
                        "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    },
                    "modelProviders": {
                        "openai": [
                            {
                                "id": "dashscope",
                                "name": "DashScope",
                                "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                                "envKey": "DASHSCOPE_API_KEY",
                                "generationConfig": {"contextWindowSize": 131072},
                            }
                        ]
                    },
                    "defaultModel": {"authType": "openai", "modelId": "dashscope"},
                }
            )
        )
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        wire_compat("qwen-code", port=6666, root=tmp_path, scope="repo")

        settings = _read_repo_settings(tmp_path)
        providers = settings["modelProviders"]["openai"]  # type: ignore[index]
        proxy_entry = next(p for p in providers if p["id"] == "agentalloy-proxy")
        assert proxy_entry["envKey"] == "DASHSCOPE_API_KEY"
        assert proxy_entry["generationConfig"]["contextWindowSize"] == 131072

        default_model = settings["defaultModel"]
        assert isinstance(default_model, dict)
        assert default_model == {"authType": "openai", "modelId": "agentalloy-proxy"}

    def test_repo_scope_defaults_env_key_when_no_matching_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no matching prior provider entry, envKey falls back to
        ``OPENAI_API_KEY`` and defaultModel still gets repointed at the proxy."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        wire_compat("qwen-code", port=6666, root=tmp_path, scope="repo")

        settings = _read_repo_settings(tmp_path)
        providers = settings["modelProviders"]["openai"]  # type: ignore[index]
        proxy_entry = next(p for p in providers if p["id"] == "agentalloy-proxy")
        assert proxy_entry["envKey"] == "OPENAI_API_KEY"
        assert "generationConfig" not in proxy_entry

        default_model = settings["defaultModel"]
        assert isinstance(default_model, dict)
        assert default_model == {"authType": "openai", "modelId": "agentalloy-proxy"}

    def test_repo_scope_idempotent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Re-wiring the same repo does not duplicate the proxy provider entry."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        wire_compat("qwen-code", port=6666, root=tmp_path, scope="repo")
        wire_compat("qwen-code", port=6666, root=tmp_path, scope="repo")

        settings = _read_repo_settings(tmp_path)
        providers = settings["modelProviders"]["openai"]  # type: ignore[index]
        proxy_entries = [p for p in providers if "/proj/" in p.get("baseUrl", "")]
        assert len(proxy_entries) == 1


class TestQwenCodeExtractUpstream:
    def test_returns_none_when_no_global_config(self, tmp_path: Path) -> None:
        assert extract_upstream(tmp_path) is None

    def test_reads_model_block_from_global_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_home = tmp_path / "home"
        (fake_home / ".qwen").mkdir(parents=True)
        (fake_home / ".qwen" / "settings.json").write_text(
            json.dumps(
                {
                    "model": {
                        "name": "qwen3-coder-plus",
                        "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    }
                }
            )
        )
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        up = extract_upstream(tmp_path)
        assert up is not None
        assert up.model == "qwen3-coder-plus"
        assert up.url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        assert up.key_env == "OPENAI_API_KEY"

    def test_skips_proxy_baseurl_to_avoid_self_adoption(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If the global config's model.baseUrl already points at our proxy
        (e.g. re-running extraction after wiring), don't adopt ourselves as
        the upstream."""
        fake_home = tmp_path / "home"
        (fake_home / ".qwen").mkdir(parents=True)
        (fake_home / ".qwen" / "settings.json").write_text(
            json.dumps(
                {
                    "model": {
                        "name": "agentalloy-proxy",
                        "baseUrl": "http://localhost:6666/proj/abc123/v1",
                    }
                }
            )
        )
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        assert extract_upstream(tmp_path) is None

    def test_returns_none_on_malformed_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_home = tmp_path / "home"
        (fake_home / ".qwen").mkdir(parents=True)
        (fake_home / ".qwen" / "settings.json").write_text("not json{")
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        assert extract_upstream(tmp_path) is None


class TestQwenCodeMiseCarrier:
    def test_mise_toml_env_block_is_valid_toml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        (tmp_path / "mise.toml").write_text("")

        wire_compat("qwen-code", port=6666, root=tmp_path, scope="repo")

        import tomllib

        mise_content = (tmp_path / "mise.toml").read_text()
        assert "BEGIN agentalloy install" in mise_content
        parsed = tomllib.loads(mise_content)
        assert parsed["env"]["QWEN_HOME"] == "{{config_root}}/.qwen"
