"""Tests for the CLI interface."""
from pathlib import Path
from typer.testing import CliRunner

from saar.cli import app

runner = CliRunner()


class TestCLI:
    """CLI integration tests."""

    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.3.0" in result.stdout

    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "extract" in result.stdout.lower() or "Extract" in result.stdout

    def test_extract_stdout(self, tmp_repo: Path, tmp_path: Path):
        """Default format (agents) writes AGENTS.md to the repo."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        result = runner.invoke(app, ["extract", str(tmp_repo), "-o", str(output_dir)])
        assert result.exit_code == 0
        assert (output_dir / "AGENTS.md").exists()

    def test_extract_markdown_stdout(self, tmp_repo: Path):
        """--format markdown still prints to stdout."""
        result = runner.invoke(app, ["extract", str(tmp_repo), "--format", "markdown"])
        assert result.exit_code == 0
        assert "Codebase DNA" in result.stdout

    def test_extract_agents_format(self, tmp_repo: Path, tmp_path: Path):
        """--format agents writes AGENTS.md."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        result = runner.invoke(app, ["extract", str(tmp_repo), "--format", "agents", "-o", str(output_dir)])
        assert result.exit_code == 0
        assert (output_dir / "AGENTS.md").exists()

    def test_extract_claude_format(self, tmp_repo: Path, tmp_path: Path):
        """--format claude should write CLAUDE.md."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        result = runner.invoke(app, ["extract", str(tmp_repo), "--format", "claude", "-o", str(output_dir)])
        assert result.exit_code == 0
        assert (output_dir / "CLAUDE.md").exists()

    def test_extract_cursorrules_format(self, tmp_repo: Path, tmp_path: Path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        result = runner.invoke(app, ["extract", str(tmp_repo), "--format", "cursorrules", "-o", str(output_dir)])
        assert result.exit_code == 0
        assert (output_dir / ".cursorrules").exists()

    def test_extract_copilot_format(self, tmp_repo: Path, tmp_path: Path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        result = runner.invoke(app, ["extract", str(tmp_repo), "--format", "copilot", "-o", str(output_dir)])
        assert result.exit_code == 0
        assert (output_dir / ".github" / "copilot-instructions.md").exists()

    def test_extract_all_formats(self, tmp_repo: Path, tmp_path: Path):
        """--format all should write all config files."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        result = runner.invoke(app, ["extract", str(tmp_repo), "--format", "all", "-o", str(output_dir)])
        assert result.exit_code == 0
        assert (output_dir / "AGENTS.md").exists()
        assert (output_dir / "CLAUDE.md").exists()
        assert (output_dir / ".cursorrules").exists()
        assert (output_dir / ".github" / "copilot-instructions.md").exists()

    def test_invalid_path_fails(self):
        result = runner.invoke(app, ["extract", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_verbose_flag(self, tmp_repo: Path):
        result = runner.invoke(app, ["extract", str(tmp_repo), "--verbose"])
        assert result.exit_code == 0

    def test_no_interview_flag(self, tmp_repo: Path, tmp_path: Path):
        """--no-interview should skip interview silently."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        result = runner.invoke(app, ["extract", str(tmp_repo), "--no-interview", "-o", str(output_dir)])
        assert result.exit_code == 0

    def test_skips_existing_without_force(self, tmp_repo: Path, tmp_path: Path):
        """File with markers: re-run updates auto block."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        runner.invoke(app, ["extract", str(tmp_repo), "--format", "claude", "-o", str(output_dir)])
        result = runner.invoke(app, ["extract", str(tmp_repo), "--format", "claude", "-o", str(output_dir)])
        assert result.exit_code == 0
        assert "updated" in result.stdout or "wrote" in result.stdout

    def test_force_overwrites(self, tmp_repo: Path, tmp_path: Path):
        """--force does a clean overwrite."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        runner.invoke(app, ["extract", str(tmp_repo), "--format", "claude", "-o", str(output_dir)])
        result = runner.invoke(app, ["extract", str(tmp_repo), "--format", "claude", "--force", "-o", str(output_dir)])
        assert result.exit_code == 0
        assert "overwrote" in result.stdout or "wrote" in result.stdout


class TestPreservationMarkers:
    """SAAR:AUTO-START/END markers preserve manual edits on re-run."""

    def test_first_write_adds_markers(self, tmp_repo: Path, tmp_path: Path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        runner.invoke(app, ["extract", str(tmp_repo), "--format", "claude", "-o", str(output_dir)])
        content = (output_dir / "CLAUDE.md").read_text()
        assert "<!-- SAAR:AUTO-START -->" in content
        assert "<!-- SAAR:AUTO-END -->" in content

    def test_rerun_preserves_manual_edits(self, tmp_repo: Path, tmp_path: Path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        runner.invoke(app, ["extract", str(tmp_repo), "--format", "claude", "-o", str(output_dir)])
        target = output_dir / "CLAUDE.md"
        target.write_text(target.read_text() + "\n## My Custom Notes\n- Never touch auth.py\n")
        runner.invoke(app, ["extract", str(tmp_repo), "--format", "claude", "-o", str(output_dir)])
        content = target.read_text()
        assert "My Custom Notes" in content
        assert "Never touch auth.py" in content

    def test_force_discards_manual_edits(self, tmp_repo: Path, tmp_path: Path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        runner.invoke(app, ["extract", str(tmp_repo), "--format", "claude", "-o", str(output_dir)])
        target = output_dir / "CLAUDE.md"
        target.write_text(target.read_text() + "\n## My Custom Notes\n- Secret rule\n")
        runner.invoke(app, ["extract", str(tmp_repo), "--format", "claude", "--force", "-o", str(output_dir)])
        content = target.read_text()
        assert "Secret rule" not in content
