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
        assert "0.1.0" in result.stdout

    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Extract" in result.stdout or "extract" in result.stdout

    def test_extract_stdout(self, tmp_repo: Path):
        """Default format (markdown) should print to stdout."""
        result = runner.invoke(app, [str(tmp_repo)])
        assert result.exit_code == 0
        assert "Codebase DNA" in result.stdout

    def test_extract_claude_format(self, tmp_repo: Path, tmp_path: Path):
        """--format claude should write CLAUDE.md."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        result = runner.invoke(app, [str(tmp_repo), "--format", "claude", "-o", str(output_dir)])
        assert result.exit_code == 0
        assert (output_dir / "CLAUDE.md").exists()

    def test_extract_cursorrules_format(self, tmp_repo: Path, tmp_path: Path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        result = runner.invoke(app, [str(tmp_repo), "--format", "cursorrules", "-o", str(output_dir)])
        assert result.exit_code == 0
        assert (output_dir / ".cursorrules").exists()

    def test_extract_copilot_format(self, tmp_repo: Path, tmp_path: Path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        result = runner.invoke(app, [str(tmp_repo), "--format", "copilot", "-o", str(output_dir)])
        assert result.exit_code == 0
        assert (output_dir / ".github" / "copilot-instructions.md").exists()

    def test_extract_all_formats(self, tmp_repo: Path, tmp_path: Path):
        """--format all should write all three config files."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        result = runner.invoke(app, [str(tmp_repo), "--format", "all", "-o", str(output_dir)])
        assert result.exit_code == 0
        assert (output_dir / "CLAUDE.md").exists()
        assert (output_dir / ".cursorrules").exists()
        assert (output_dir / ".github" / "copilot-instructions.md").exists()

    def test_invalid_path_fails(self):
        result = runner.invoke(app, ["/nonexistent/path"])
        assert result.exit_code != 0

    def test_verbose_flag(self, tmp_repo: Path):
        result = runner.invoke(app, [str(tmp_repo), "--verbose"])
        assert result.exit_code == 0

    def test_skips_existing_without_force(self, tmp_repo: Path):
        """Should not overwrite existing CLAUDE.md without --force."""
        existing = tmp_repo / "CLAUDE.md"
        original = existing.read_text()
        result = runner.invoke(app, [str(tmp_repo), "--format", "claude"])
        assert result.exit_code == 0
        assert "skipped" in result.stdout
        assert existing.read_text() == original

    def test_force_overwrites(self, tmp_repo: Path):
        """--force should overwrite existing files."""
        result = runner.invoke(app, [str(tmp_repo), "--format", "claude", "--force"])
        assert result.exit_code == 0
        assert "wrote" in result.stdout
