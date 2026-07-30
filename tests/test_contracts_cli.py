"""CLI-level tests for `agentalloy contracts migrate|archive`.

Tier B item 7 (upstream reconciliation): the tree-layout planners in
`agentalloy.contracts` (`plan_contracts_migration`, `apply_contracts_migration`,
`plan_archive`) already have unit coverage; these tests exercise the CLI
surface — argument wiring, cursor rewriting/clearing, and the human/JSON
render paths — end to end through `subcommands.contracts`.
"""

from __future__ import annotations

import argparse
import json

from agentalloy.install.subcommands import contracts as contracts_cmd


def _parse(*argv: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    contracts_cmd.add_parser(sub)
    return parser.parse_args(["contracts", *argv])


def _seed_legacy(root, phase: str, slug: str) -> None:
    d = root / ".agentalloy" / "contracts" / phase
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text(f"---\nphase: {phase}\ntask_slug: {slug}\n---\n# {slug}\n")


def _seed_active(root, phase: str, slug: str) -> None:
    d = root / ".agentalloy" / "contracts" / "active" / phase
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text(f"---\nphase: {phase}\ntask_slug: {slug}\n---\n# {slug}\n")


class TestMigrateCommand:
    def test_dry_run_reports_without_moving(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        _seed_legacy(tmp_path, "build", "01-legacy")
        args = _parse("migrate", "--dry-run", "--json")
        rc = args.func(args)
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["dry_run"] is True
        assert out["moves"] == [{"from": "build/01-legacy.md", "to": "active/build/01-legacy.md", "archived": False}]
        # nothing actually moved
        assert (tmp_path / ".agentalloy" / "contracts" / "build" / "01-legacy.md").exists()

    def test_migrate_moves_files_and_reports_json(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        _seed_legacy(tmp_path, "build", "01-legacy")
        args = _parse("migrate", "--json")
        rc = args.func(args)
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["migrated"] == 1
        assert not (tmp_path / ".agentalloy" / "contracts" / "build" / "01-legacy.md").exists()
        assert (tmp_path / ".agentalloy" / "contracts" / "active" / "build" / "01-legacy.md").exists()

    def test_migrate_rewrites_cursor_to_follow_move(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        _seed_legacy(tmp_path, "build", "01-legacy")
        (tmp_path / ".agentalloy" / "cursor").write_text("build/01-legacy.md")
        args = _parse("migrate", "--json")
        args.func(args)
        capsys.readouterr()
        assert (tmp_path / ".agentalloy" / "cursor").read_text().strip() == "active/build/01-legacy.md"

    def test_migrate_human_render_no_op_when_already_tree(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        _seed_active(tmp_path, "build", "01-item")
        args = _parse("migrate")
        rc = args.func(args)
        assert rc == 0
        assert "nothing to migrate" in capsys.readouterr().out

    def test_migrate_collision_reports_nonzero_exit(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        _seed_legacy(tmp_path, "build", "01-item")
        _seed_active(tmp_path, "build", "01-item")  # occupies the destination
        args = _parse("migrate", "--json")
        rc = args.func(args)
        out = json.loads(capsys.readouterr().out)
        assert rc == 1
        assert out["collisions"] == [{"from": "build/01-item.md", "to": "active/build/01-item.md"}]
        # left in place, not overwritten
        assert (tmp_path / ".agentalloy" / "contracts" / "build" / "01-item.md").exists()


class TestArchiveCommand:
    def test_archive_moves_active_to_archive(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        _seed_active(tmp_path, "qa", "feat-x")
        args = _parse("archive", "--json")
        rc = args.func(args)
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["archived"] == 1
        assert not (tmp_path / ".agentalloy" / "contracts" / "active" / "qa" / "feat-x.md").exists()
        assert (tmp_path / ".agentalloy" / "contracts" / "archive" / "qa" / "feat-x.md").exists()

    def test_archive_dry_run_does_not_move(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        _seed_active(tmp_path, "qa", "feat-x")
        args = _parse("archive", "--dry-run", "--json")
        args.func(args)
        capsys.readouterr()
        assert (tmp_path / ".agentalloy" / "contracts" / "active" / "qa" / "feat-x.md").exists()

    def test_archive_clears_cursor_pointing_at_archived_item(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        _seed_active(tmp_path, "qa", "feat-x")
        (tmp_path / ".agentalloy" / "cursor").write_text("active/qa/feat-x.md")
        args = _parse("archive", "--json")
        args.func(args)
        capsys.readouterr()
        assert not (tmp_path / ".agentalloy" / "cursor").exists()

    def test_archive_respects_phase_filter(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        _seed_active(tmp_path, "qa", "feat-x")
        _seed_active(tmp_path, "build", "01-item")
        args = _parse("archive", "--phase", "qa", "--json")
        args.func(args)
        capsys.readouterr()
        assert (tmp_path / ".agentalloy" / "contracts" / "archive" / "qa" / "feat-x.md").exists()
        # build contract untouched
        assert (tmp_path / ".agentalloy" / "contracts" / "active" / "build" / "01-item.md").exists()

    def test_archive_human_render_no_op_when_nothing_live(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        args = _parse("archive")
        rc = args.func(args)
        assert rc == 0
        assert "nothing to archive" in capsys.readouterr().out


class TestParserWiring:
    def test_bare_contracts_prints_help_and_exits_zero(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        contracts_cmd.add_parser(sub)
        args = parser.parse_args(["contracts"])
        assert args.func(args) == 0
