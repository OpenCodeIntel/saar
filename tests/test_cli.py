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
        assert "0.4.1" in result.stdout

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


class TestMarkerEdgeCases:
    """OPE-169: _write_with_markers must never produce double END markers or leak orphans."""

    def _extract(self, tmp_repo: Path, output_dir: Path) -> Path:
        """Run extract and return the CLAUDE.md path."""
        runner.invoke(app, ["extract", str(tmp_repo), "--format", "claude", "--no-interview", "-o", str(output_dir)])
        return output_dir / "CLAUDE.md"

    def _count_markers(self, path: Path) -> tuple[int, int]:
        """Return (start_count, end_count) of SAAR markers in file."""
        content = path.read_text()
        return (
            content.count("<!-- SAAR:AUTO-START -->"),
            content.count("<!-- SAAR:AUTO-END -->"),
        )

    def test_exactly_one_start_and_one_end_on_first_write(self, tmp_repo: Path, tmp_path: Path):
        """First write must produce exactly one START and one END marker."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        target = self._extract(tmp_repo, output_dir)
        starts, ends = self._count_markers(target)
        assert starts == 1, f"Expected 1 SAAR:AUTO-START, got {starts}"
        assert ends == 1, f"Expected 1 SAAR:AUTO-END, got {ends}"

    def test_exactly_one_start_and_one_end_after_rerun(self, tmp_repo: Path, tmp_path: Path):
        """Re-run on clean file must still have exactly one START and one END."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        target = self._extract(tmp_repo, output_dir)
        self._extract(tmp_repo, output_dir)  # second run
        starts, ends = self._count_markers(target)
        assert starts == 1, f"Expected 1 SAAR:AUTO-START after rerun, got {starts}"
        assert ends == 1, f"Expected 1 SAAR:AUTO-END after rerun, got {ends}"

    def test_no_double_end_marker_when_manual_content_follows(self, tmp_repo: Path, tmp_path: Path):
        """Core OPE-169 bug: manual content after AUTO-END must not produce a second END marker.

        Scenario:
        1. First extract -> file has AUTO-START...AUTO-END
        2. Developer appends manual notes after AUTO-END
        3. Second extract -> must still have exactly one AUTO-END
        """
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        target = self._extract(tmp_repo, output_dir)
        target.write_text(target.read_text() + "\n## My Team Rules\n- Never touch auth.py\n")

        # Second extract -- where the double-END bug was triggered
        self._extract(tmp_repo, output_dir)

        content = target.read_text()
        starts, ends = self._count_markers(target)
        assert starts == 1, f"OPE-169: Expected 1 START after rerun with manual content, got {starts}"
        assert ends == 1, f"OPE-169: Expected 1 END after rerun with manual content, got {ends}"
        assert "Never touch auth.py" in content, "Manual content must be preserved"

    def test_orphaned_end_marker_in_manual_section_is_stripped(self, tmp_repo: Path, tmp_path: Path):
        """A stale SAAR:AUTO-END in the manual section must be cleaned up on next run."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        target = self._extract(tmp_repo, output_dir)

        # Inject orphaned END marker directly into manual section
        target.write_text(
            target.read_text()
            + "\n## Manual Section\n- Some rule\n<!-- SAAR:AUTO-END -->\n- Another rule\n"
        )

        self._extract(tmp_repo, output_dir)
        starts, ends = self._count_markers(target)
        content = target.read_text()
        assert ends == 1, f"Orphaned END marker must be stripped, got {ends} END markers"
        assert "Some rule" in content, "Manual content before orphan must be preserved"

    def test_marker_count_stable_across_five_reruns(self, tmp_repo: Path, tmp_path: Path):
        """Five reruns must never accumulate extra markers."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        target = self._extract(tmp_repo, output_dir)
        target.write_text(target.read_text() + "\n## Manual\n- Rule 1\n")
        for i in range(4):
            self._extract(tmp_repo, output_dir)
            starts, ends = self._count_markers(target)
            assert starts == 1, f"Run {i + 2}: got {starts} START markers (accumulation!)"
            assert ends == 1, f"Run {i + 2}: got {ends} END markers (accumulation!)"

    def test_manual_content_before_auto_block_is_preserved(self, tmp_repo: Path, tmp_path: Path):
        """Content placed BEFORE the auto block must survive re-runs."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        target = self._extract(tmp_repo, output_dir)
        original = target.read_text()
        target.write_text("# My Preamble\n- Top-level rule\n\n" + original)
        self._extract(tmp_repo, output_dir)
        content = target.read_text()
        assert "My Preamble" in content, "Content before auto block must be preserved"
        starts, ends = self._count_markers(target)
        assert starts == 1
        assert ends == 1

    def test_write_with_markers_unit_double_end_scenario(self, tmp_path: Path):
        """Unit test _write_with_markers directly: orphaned END in manual section must be cleaned."""
        from rich.console import Console
        from io import StringIO
        from saar.cli import _write_with_markers

        target = tmp_path / "TEST.md"
        console = Console(file=StringIO(), highlight=False)

        # First write -- clean state
        _write_with_markers(target, "# Auto content\n- line 1\n", force=False, console=console)
        assert target.read_text().count("<!-- SAAR:AUTO-END -->") == 1

        # Append manual content with an orphaned END marker -- the exact OPE-169 trigger
        target.write_text(
            target.read_text()
            + "\n## Manual\n- rule\n<!-- SAAR:AUTO-END -->\n- more\n"
        )

        # Second write must produce exactly 1 END marker
        _write_with_markers(target, "# Auto content v2\n- line 2\n", force=False, console=console)
        content = target.read_text()
        end_count = content.count("<!-- SAAR:AUTO-END -->")
        assert end_count == 1, (
            f"OPE-169: _write_with_markers produced {end_count} END markers, expected 1"
        )
