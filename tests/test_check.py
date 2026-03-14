"""Tests for saar check command (OPE-190).

saar check exits 0 if AGENTS.md is fresh and covers required sections.
exits 1 with specific message if not. Designed for CI.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _write_good_agents_md(path: Path) -> None:
    """Write a passing AGENTS.md -- has all required sections."""
    path.write_text(
        "pytest tests/ -v\n"           # verify
        "never use npm -- use bun\n"   # never_do
        "require_auth pattern\n"       # auth
        "AuthError, LimitCheckError\n" # exceptions
        "Workspace = tenant\n"         # tribal
        "FastAPI Python bun\n"         # stack
    )


class TestCheckPassesOnGoodFile:
    def test_exits_zero_when_good(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app

        _write_good_agents_md(tmp_path / "AGENTS.md")
        runner = CliRunner()
        result = runner.invoke(app, ["check", str(tmp_path)])
        # no snapshot = freshness unknown, but sections present should pass
        assert result.exit_code == 0

    def test_outputs_ok_message(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app

        _write_good_agents_md(tmp_path / "AGENTS.md")
        runner = CliRunner()
        result = runner.invoke(app, ["check", str(tmp_path)])
        clean = _strip_ansi(result.output)
        assert "ok" in clean.lower() or "up to date" in clean.lower() or "passed" in clean.lower()


class TestCheckFailsNoFile:
    def test_exits_one_when_no_agents_md(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["check", str(tmp_path)])
        assert result.exit_code == 1

    def test_output_suggests_extract(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["check", str(tmp_path)])
        clean = _strip_ansi(result.output)
        assert "saar extract" in clean


class TestCheckFailsMissingSections:
    def test_exits_one_when_missing_verify(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app

        # AGENTS.md without verification workflow
        (tmp_path / "AGENTS.md").write_text(
            "never use npm\nrequire_auth\nAuthError\nWorkspace=tenant\nFastAPI"
        )
        runner = CliRunner()
        result = runner.invoke(app, ["check", str(tmp_path)])
        assert result.exit_code == 1

    def test_message_names_missing_section(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app

        (tmp_path / "AGENTS.md").write_text("never use npm\nrequire_auth")
        runner = CliRunner()
        result = runner.invoke(app, ["check", str(tmp_path)])
        clean = _strip_ansi(result.output)
        # should mention what's missing
        assert "missing" in clean.lower() or "section" in clean.lower()


class TestCheckMaxAgeFlag:
    def test_default_max_age_passes_without_snapshot(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app

        # no snapshot = freshness_days is None = no staleness failure
        _write_good_agents_md(tmp_path / "AGENTS.md")
        runner = CliRunner()
        result = runner.invoke(app, ["check", str(tmp_path), "--max-age", "14"])
        assert result.exit_code == 0

    def test_max_age_zero_never_fails_on_freshness(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app

        _write_good_agents_md(tmp_path / "AGENTS.md")
        runner = CliRunner()
        result = runner.invoke(app, ["check", str(tmp_path), "--max-age", "0"])
        assert result.exit_code == 0


class TestCheckFileFlag:
    def test_checks_specific_file_with_flag(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app

        custom = tmp_path / "CLAUDE.md"
        _write_good_agents_md(custom)
        runner = CliRunner()
        result = runner.invoke(app, ["check", str(tmp_path), "--file", str(custom)])
        assert result.exit_code == 0

    def test_nonexistent_file_flag_exits_one(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app

        runner = CliRunner()
        result = runner.invoke(app, [
            "check", str(tmp_path), "--file", str(tmp_path / "NOPE.md")
        ])
        assert result.exit_code == 1


class TestCheckJsonFlag:
    def test_json_output_is_valid_json(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app

        _write_good_agents_md(tmp_path / "AGENTS.md")
        runner = CliRunner()
        result = runner.invoke(app, ["check", str(tmp_path), "--json"])
        clean = _strip_ansi(result.output).strip()
        data = json.loads(clean)
        assert "ok" in data
        assert "issues" in data

    def test_json_ok_true_when_passing(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app

        _write_good_agents_md(tmp_path / "AGENTS.md")
        runner = CliRunner()
        result = runner.invoke(app, ["check", str(tmp_path), "--json"])
        data = json.loads(_strip_ansi(result.output).strip())
        assert data["ok"] is True
        assert data["issues"] == []

    def test_json_ok_false_when_failing(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["check", str(tmp_path), "--json"])
        data = json.loads(_strip_ansi(result.output).strip())
        assert data["ok"] is False
        assert len(data["issues"]) > 0

    def test_json_contains_score(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app

        _write_good_agents_md(tmp_path / "AGENTS.md")
        runner = CliRunner()
        result = runner.invoke(app, ["check", str(tmp_path), "--json"])
        data = json.loads(_strip_ansi(result.output).strip())
        assert "score" in data
        assert isinstance(data["score"], int)


class TestCheckHelp:
    def test_help_available(self):
        from typer.testing import CliRunner
        from saar.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["check", "--help"])
        assert result.exit_code == 0
        clean = _strip_ansi(result.output)
        assert "check" in clean.lower()

    def test_help_mentions_ci(self):
        from typer.testing import CliRunner
        from saar.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["check", "--help"])
        clean = _strip_ansi(result.output).lower()
        assert "ci" in clean or "exit" in clean
