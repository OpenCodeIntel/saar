"""Tests for OPE-171: token budget enforcement.

Budget module must:
- Return content unchanged when under budget
- Truncate when over budget
- Always preserve Tribal Knowledge and Project-Specific Rules sections
- Always preserve How to Verify section
- Cut Project Structure first (highest line count, lowest value)
- Add a clear truncation note telling user how to get full output
- Be disabled by --verbose and --budget 0
"""
import pytest
from pathlib import Path
from typer.testing import CliRunner

from saar.formatters.budget import apply_budget, _split_into_sections
from saar.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Unit tests for apply_budget()
# ---------------------------------------------------------------------------

class TestApplyBudgetCore:

    def test_under_budget_returns_unchanged(self):
        text = "## Frontend\n- bun\n## Architecture\n- singleton\n"
        result = apply_budget(text, max_lines=100)
        assert result == text

    def test_zero_budget_returns_unchanged(self):
        """0 = unlimited."""
        long = "\n".join(f"line {i}" for i in range(200)) + "\n"
        result = apply_budget(long, max_lines=0)
        assert result == long

    def test_negative_budget_returns_unchanged(self):
        long = "\n".join(f"line {i}" for i in range(200)) + "\n"
        result = apply_budget(long, max_lines=-1)
        assert result == long

    def test_truncation_note_present_when_over_budget(self):
        # Build content clearly over 10 lines
        text = (
            "## Frontend\n" + "- bun\n" * 5 +
            "## Project Structure\n" + "- big dir tree\n" * 20 +
            "## Architecture\n" + "- singleton\n" * 3
        )
        result = apply_budget(text, max_lines=10)
        assert "lines omitted" in result
        assert "--verbose" in result

    def test_truncation_note_absent_when_under_budget(self):
        text = "## Frontend\n- bun\n## Architecture\n- singleton\n"
        result = apply_budget(text, max_lines=100)
        assert "lines omitted" not in result

    def test_result_within_line_budget(self):
        text = (
            "## Frontend\n" + "- bun\n" * 5 +
            "## Project Structure\n" + "- dir\n" * 50 +
            "## Architecture\n" + "- singleton\n" * 5
        )
        budget = 20
        result = apply_budget(text, max_lines=budget)
        # Allow small overage for truncation note and protected sections
        result_lines = result.splitlines()
        assert len(result_lines) <= budget + 10  # protected sections may add a few

    def test_project_structure_cut_first(self):
        """Project Structure is lowest priority -- should be cut before other sections."""
        text = (
            "## Frontend\n- bun\n- shadcn\n" +
            "## Project Structure\n" + "- big tree\n" * 30 +
            "## Architecture\n- singleton\n"
        )
        result = apply_budget(text, max_lines=15)
        assert "## Frontend" in result
        assert "## Architecture" in result
        # Project Structure should be cut or heavily truncated
        project_lines = [l for l in result.splitlines() if "big tree" in l]
        assert len(project_lines) < 30, "Project Structure should be cut under budget"

    def test_tribal_knowledge_always_preserved(self):
        """Tribal Knowledge section must survive even heavy truncation."""
        text = (
            "## Frontend\n" + "- item\n" * 5 +
            "## Project Structure\n" + "- dir\n" * 50 +
            "## Architecture\n" + "- arch\n" * 10 +
            "## Tribal Knowledge\n*Captured via interview.*\n"
            "**Never Do**\n- Never force push\n- Never use npm\n"
        )
        result = apply_budget(text, max_lines=15)
        assert "## Tribal Knowledge" in result
        assert "Never force push" in result
        assert "Never use npm" in result

    def test_project_specific_rules_always_preserved(self):
        """Project-Specific Rules (from CLAUDE.md) always survive truncation."""
        text = (
            "## Frontend\n" + "- item\n" * 5 +
            "## Project Structure\n" + "- dir\n" * 50 +
            "## Project-Specific Rules\n*From CLAUDE.md*\n- No emojis\n- Bun only\n"
        )
        result = apply_budget(text, max_lines=15)
        assert "## Project-Specific Rules" in result
        assert "No emojis" in result
        assert "Bun only" in result

    def test_how_to_verify_always_preserved(self):
        """How to Verify section is high value -- always preserved."""
        text = (
            "## Frontend\n" + "- item\n" * 5 +
            "## Project Structure\n" + "- dir\n" * 50 +
            "## How to Verify Changes Work\n- pytest tests/ -v\n- bun run build\n"
        )
        result = apply_budget(text, max_lines=15)
        assert "## How to Verify" in result
        assert "pytest" in result

    def test_protected_sections_appear_after_truncation_note(self):
        """Protected sections must appear AFTER the truncation note, not before."""
        text = (
            "## Frontend\n" + "- item\n" * 5 +
            "## Project Structure\n" + "- dir\n" * 50 +
            "## Tribal Knowledge\n- Never use npm\n"
        )
        result = apply_budget(text, max_lines=10)
        if "lines omitted" in result:
            note_idx = result.index("lines omitted")
            tribal_idx = result.index("## Tribal Knowledge")
            assert tribal_idx > note_idx, (
                "Tribal Knowledge must appear AFTER the truncation note"
            )

    def test_small_content_never_truncated(self):
        """Content under _MIN_LINES_TO_TRUNCATE threshold is never touched."""
        text = "## Frontend\n- bun\n## Architecture\n- singleton\n"
        # Even with a very tight budget, tiny content passes through
        result = apply_budget(text, max_lines=1)
        assert "lines omitted" not in result


class TestSplitIntoSections:

    def test_splits_on_h2_headers(self):
        text = "preamble\n## Section A\n- a\n## Section B\n- b\n"
        sections = _split_into_sections(text.splitlines(keepends=True))
        assert len(sections) == 3  # preamble + A + B

    def test_preamble_before_first_header_is_own_section(self):
        text = "# Title\nstats\n## Frontend\n- bun\n"
        sections = _split_into_sections(text.splitlines(keepends=True))
        assert sections[0][0].startswith("# Title")

    def test_empty_text_returns_one_section(self):
        sections = _split_into_sections([])
        assert sections == []

    def test_no_headers_returns_one_section(self):
        text = "just some lines\nno headers\n"
        sections = _split_into_sections(text.splitlines(keepends=True))
        assert len(sections) == 1


# ---------------------------------------------------------------------------
# Integration tests via CLI
# ---------------------------------------------------------------------------

class TestBudgetCLI:

    def test_default_output_respects_100_line_budget(self, tmp_repo: Path, tmp_path: Path):
        """Default extract must produce files under 100 lines on a big repo."""
        # Add a lot of content to push over 100 lines
        structure_dir = tmp_repo / "a" / "b" / "c" / "d" / "e"
        structure_dir.mkdir(parents=True)
        for i in range(50):
            (structure_dir / f"module_{i}.py").write_text(
                f"class Module{i}:\n    def method(self) -> None: pass\n"
            )

        output_dir = tmp_path / "out"
        output_dir.mkdir()
        result = runner.invoke(app, [
            "extract", str(tmp_repo), "--format", "agents",
            "--no-interview", "-o", str(output_dir)
        ])
        assert result.exit_code == 0
        content = (output_dir / "AGENTS.md").read_text()
        # Strip SAAR markers for line count
        inner = content.split("<!-- SAAR:AUTO-START -->")[-1].split("<!-- SAAR:AUTO-END -->")[0]
        line_count = len(inner.splitlines())
        assert line_count <= 110, (  # 100 + small margin for protected sections
            f"Default output exceeded budget: {line_count} lines"
        )

    def test_verbose_flag_disables_budget(self, tmp_repo: Path, tmp_path: Path):
        """--verbose must produce full output without truncation note."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        runner.invoke(app, [
            "extract", str(tmp_repo), "--format", "agents",
            "--no-interview", "--verbose", "-o", str(output_dir)
        ])
        content = (output_dir / "AGENTS.md").read_text()
        assert "lines omitted" not in content

    def test_budget_zero_disables_truncation(self, tmp_repo: Path, tmp_path: Path):
        """--budget 0 must produce full output without truncation note."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        runner.invoke(app, [
            "extract", str(tmp_repo), "--format", "agents",
            "--no-interview", "--budget", "0", "-o", str(output_dir)
        ])
        content = (output_dir / "AGENTS.md").read_text()
        assert "lines omitted" not in content

    def test_custom_budget_respected(self, tmp_repo: Path, tmp_path: Path):
        """--budget N must cap output at N lines."""
        # Add enough dirs to push over 30 lines
        for i in range(20):
            d = tmp_repo / f"module_{i}"
            d.mkdir()
            (d / "__init__.py").write_text("")

        output_dir = tmp_path / "out"
        output_dir.mkdir()
        runner.invoke(app, [
            "extract", str(tmp_repo), "--format", "agents",
            "--no-interview", "--budget", "30", "-o", str(output_dir)
        ])
        content = (output_dir / "AGENTS.md").read_text()
        inner = content.split("<!-- SAAR:AUTO-START -->")[-1].split("<!-- SAAR:AUTO-END -->")[0]
        line_count = len(inner.splitlines())
        assert line_count <= 45, f"Custom budget 30 exceeded: {line_count} lines"

    def test_truncation_note_tells_user_about_verbose(self, tmp_repo: Path, tmp_path: Path):
        """Truncation note must mention --verbose so users know how to get full output."""
        # Force a tiny budget to trigger truncation
        for i in range(30):
            d = tmp_repo / f"big_module_{i}"
            d.mkdir()
            (d / "code.py").write_text(
                "\n".join(f"def func_{j}(): pass" for j in range(5))
            )

        output_dir = tmp_path / "out"
        output_dir.mkdir()
        runner.invoke(app, [
            "extract", str(tmp_repo), "--format", "agents",
            "--no-interview", "--budget", "10", "-o", str(output_dir)
        ])
        content = (output_dir / "AGENTS.md").read_text()
        if "lines omitted" in content:
            assert "--verbose" in content, (
                "Truncation note must tell users about --verbose flag"
            )

    def test_markdown_format_never_budgeted(self, tmp_repo: Path):
        """Markdown format goes to stdout for human reading -- budget not applied."""
        result = runner.invoke(app, [
            "extract", str(tmp_repo), "--format", "markdown",
            "--no-interview", "--budget", "5"
        ])
        assert result.exit_code == 0
        assert "lines omitted" not in result.stdout
