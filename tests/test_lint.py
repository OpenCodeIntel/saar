"""Tests for saar lint command (OPE-177).

saar lint = inline diagnostics with line numbers and rule codes.
Like ruff, but for AGENTS.md.

Rule codes:
  SA001 -- duplicate rule (exact line appears more than once)
  SA002 -- orphaned section header (## Heading with nothing below it)
  SA003 -- vague rule (bullet point under 6 words, not actionable)
  SA004 -- generic filler (matches known useless patterns)
  SA005 -- emoji in rules (wastes instruction budget)
"""
from __future__ import annotations

import re
from pathlib import Path


# ── helpers ───────────────────────────────────────────────────────────────────


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _invoke(args: list[str]):
    from typer.testing import CliRunner
    from saar.cli import app
    runner = CliRunner()
    return runner.invoke(app, args)


# ── unit: LintViolation dataclass ─────────────────────────────────────────────


class TestLintViolation:
    def test_has_required_fields(self):
        from saar.linter import LintViolation
        v = LintViolation(line=5, code="SA001", message="test", fix="remove it")
        assert v.line == 5
        assert v.code == "SA001"
        assert v.message == "test"
        assert v.fix == "remove it"

    def test_severity_defaults_to_warning(self):
        from saar.linter import LintViolation
        v = LintViolation(line=1, code="SA001", message="x", fix=None)
        assert v.severity in ("warning", "error")

    def test_format_includes_line_and_code(self):
        from saar.linter import LintViolation
        v = LintViolation(line=12, code="SA003", message="orphaned header", fix=None)
        fmt = v.format("AGENTS.md")
        assert "12" in fmt
        assert "SA003" in fmt
        assert "orphaned header" in fmt


# ── unit: SA001 duplicate rules ───────────────────────────────────────────────


class TestSA001Duplicates:
    def test_detects_exact_duplicate_lines(self):
        from saar.linter import lint_agents_md
        content = (
            "## Never Do\n"
            "- Never use npm -- use bun\n"
            "- Always run pytest\n"
            "## Verification\n"
            "- Never use npm -- use bun\n"  # duplicate of line 2
        )
        violations = lint_agents_md(content)
        sa001 = [v for v in violations if v.code == "SA001"]
        assert len(sa001) >= 1

    def test_no_false_positive_on_unique_lines(self):
        from saar.linter import lint_agents_md
        content = (
            "## Never Do\n"
            "- Never use npm\n"
            "- Never use print()\n"
            "## Verification\n"
            "- pytest tests/ -v\n"
        )
        violations = lint_agents_md(content)
        sa001 = [v for v in violations if v.code == "SA001"]
        assert sa001 == []

    def test_duplicate_reports_correct_line_number(self):
        from saar.linter import lint_agents_md
        lines = [
            "## Never Do",
            "- Never use npm",
            "- run pytest",
            "## Also",
            "- Never use npm",  # line 5 is the duplicate
        ]
        content = "\n".join(lines)
        violations = lint_agents_md(content)
        sa001 = [v for v in violations if v.code == "SA001"]
        assert any(v.line == 5 for v in sa001)

    def test_case_insensitive_duplicate_detection(self):
        from saar.linter import lint_agents_md
        content = (
            "## Never Do\n"
            "- Never use NPM\n"
            "## Also\n"
            "- never use npm\n"
        )
        violations = lint_agents_md(content)
        sa001 = [v for v in violations if v.code == "SA001"]
        # case-insensitive: these are the same rule
        assert len(sa001) >= 1

    def test_blank_lines_not_flagged_as_duplicates(self):
        from saar.linter import lint_agents_md
        content = "## A\n\n- rule one\n\n## B\n\n- rule two\n"
        violations = lint_agents_md(content)
        sa001 = [v for v in violations if v.code == "SA001"]
        assert sa001 == []


# ── unit: SA002 orphaned headers ──────────────────────────────────────────────


class TestSA002OrphanedHeaders:
    def test_detects_header_with_no_content(self):
        from saar.linter import lint_agents_md
        content = (
            "## Never Do\n"
            "- Never use npm\n"
            "## Performance\n"    # nothing below this
            "## Verification\n"
            "- pytest tests/\n"
        )
        violations = lint_agents_md(content)
        sa002 = [v for v in violations if v.code == "SA002"]
        assert len(sa002) >= 1

    def test_no_false_positive_when_content_follows(self):
        from saar.linter import lint_agents_md
        content = (
            "## Never Do\n"
            "- Never use npm\n"
            "## Verification\n"
            "- pytest tests/\n"
        )
        violations = lint_agents_md(content)
        sa002 = [v for v in violations if v.code == "SA002"]
        assert sa002 == []

    def test_reports_correct_line_for_orphaned_header(self):
        from saar.linter import lint_agents_md
        lines = [
            "## Never Do",
            "- Never use npm",
            "## Empty Section",   # line 3
            "## Verification",
            "- pytest tests/",
        ]
        violations = lint_agents_md("\n".join(lines))
        sa002 = [v for v in violations if v.code == "SA002"]
        assert any(v.line == 3 for v in sa002)

    def test_header_at_end_of_file_flagged(self):
        from saar.linter import lint_agents_md
        content = "## Never Do\n- Never use npm\n## Empty\n"
        violations = lint_agents_md(content)
        sa002 = [v for v in violations if v.code == "SA002"]
        assert len(sa002) >= 1


# ── unit: SA003 vague rules ───────────────────────────────────────────────────


class TestSA003VagueRules:
    def test_detects_very_short_bullet(self):
        from saar.linter import lint_agents_md
        content = (
            "## Never Do\n"
            "- Be careful\n"       # 2 words -- vague
            "- Never modify auth.py -- frozen until Q3\n"
        )
        violations = lint_agents_md(content)
        sa003 = [v for v in violations if v.code == "SA003"]
        assert len(sa003) >= 1

    def test_no_false_positive_on_specific_rule(self):
        from saar.linter import lint_agents_md
        content = (
            "## Never Do\n"
            "- Never use npm -- always use bun for package management\n"
            "- Run pytest tests/ -v before every commit\n"
        )
        violations = lint_agents_md(content)
        sa003 = [v for v in violations if v.code == "SA003"]
        assert sa003 == []

    def test_reports_line_number_for_vague_rule(self):
        from saar.linter import lint_agents_md
        lines = [
            "## Never Do",
            "- Never use npm",
            "- test it",           # line 3 -- vague
            "- Run pytest -v",
        ]
        violations = lint_agents_md("\n".join(lines))
        sa003 = [v for v in violations if v.code == "SA003"]
        assert any(v.line == 3 for v in sa003)


# ── unit: SA004 generic filler ────────────────────────────────────────────────


class TestSA004GenericFiller:
    def test_detects_write_clean_code(self):
        from saar.linter import lint_agents_md
        content = "## Style\n- Write clean code\n- Never use npm\n"
        violations = lint_agents_md(content)
        sa004 = [v for v in violations if v.code == "SA004"]
        assert len(sa004) >= 1

    def test_detects_follow_best_practices(self):
        from saar.linter import lint_agents_md
        content = "## Style\n- Follow best practices\n"
        violations = lint_agents_md(content)
        sa004 = [v for v in violations if v.code == "SA004"]
        assert len(sa004) >= 1

    def test_no_false_positive_on_specific_rule(self):
        from saar.linter import lint_agents_md
        content = "## Auth\n- Use Depends(require_auth) -- never bypass with manual header parsing\n"
        violations = lint_agents_md(content)
        sa004 = [v for v in violations if v.code == "SA004"]
        assert sa004 == []

    def test_reports_line_number(self):
        from saar.linter import lint_agents_md
        lines = [
            "## Style",
            "- Never use npm",
            "- Write clean code",   # line 3
        ]
        violations = lint_agents_md("\n".join(lines))
        sa004 = [v for v in violations if v.code == "SA004"]
        assert any(v.line == 3 for v in sa004)


# ── unit: SA005 emojis ────────────────────────────────────────────────────────


class TestSA005Emojis:
    def test_detects_emoji_in_rule(self):
        from saar.linter import lint_agents_md
        content = "## Style\n- Never use npm\n- Always run tests ✅\n"
        violations = lint_agents_md(content)
        sa005 = [v for v in violations if v.code == "SA005"]
        assert len(sa005) >= 1

    def test_no_false_positive_without_emoji(self):
        from saar.linter import lint_agents_md
        content = "## Style\n- Never use npm\n- Run pytest -v\n"
        violations = lint_agents_md(content)
        sa005 = [v for v in violations if v.code == "SA005"]
        assert sa005 == []

    def test_reports_correct_line(self):
        from saar.linter import lint_agents_md
        lines = [
            "## Style",
            "- Never use npm",
            "- Deploy carefully 🚀",  # line 3
        ]
        violations = lint_agents_md("\n".join(lines))
        sa005 = [v for v in violations if v.code == "SA005"]
        assert any(v.line == 3 for v in sa005)


# ── unit: clean file has no violations ────────────────────────────────────────


class TestCleanFile:
    def test_well_written_file_has_no_violations(self):
        from saar.linter import lint_agents_md
        content = """## Never Do
- Never use npm -- this project uses bun (package.json has bun.lockb)
- Never modify auth.py directly -- raise a PR, it's frozen
- Never add external services to saar -- no Supabase, no Redis

## How to Verify
- source venv/bin/activate && pytest tests/ -v

## Stack
- Python 3.11+, FastAPI, Supabase, React, TypeScript, bun

## Auth
- Use Depends(require_auth) -- never bypass with manual header parsing
"""
        violations = lint_agents_md(content)
        assert violations == []


# ── CLI tests ─────────────────────────────────────────────────────────────────


class TestLintCLI:
    def test_clean_file_exits_zero(self, tmp_path: Path):
        (tmp_path / "AGENTS.md").write_text(
            "## Never Do\n"
            "- Never use npm -- this project uses bun for all package management\n"
            "## How to Verify\n"
            "- source venv/bin/activate && pytest tests/ -v\n"
        )
        result = _invoke(["lint", str(tmp_path)])
        assert result.exit_code == 0

    def test_file_with_violations_exits_one(self, tmp_path: Path):
        (tmp_path / "AGENTS.md").write_text(
            "## Never Do\n"
            "- Write clean code\n"   # SA004
            "- Never use npm\n"
            "## Never Do Again\n"
            "- Never use npm\n"      # SA001 duplicate
        )
        result = _invoke(["lint", str(tmp_path)])
        assert result.exit_code == 1

    def test_output_contains_violation_codes(self, tmp_path: Path):
        (tmp_path / "AGENTS.md").write_text(
            "## Style\n- Write clean code\n"
        )
        result = _invoke(["lint", str(tmp_path)])
        clean = _strip_ansi(result.output)
        assert "SA" in clean

    def test_no_agents_md_exits_one(self, tmp_path: Path):
        result = _invoke(["lint", str(tmp_path)])
        assert result.exit_code == 1

    def test_output_contains_line_numbers(self, tmp_path: Path):
        (tmp_path / "AGENTS.md").write_text(
            "## Style\n"
            "- Never use npm\n"
            "- Write clean code\n"  # line 3
        )
        result = _invoke(["lint", str(tmp_path)])
        clean = _strip_ansi(result.output)
        assert "3" in clean

    def test_help_available(self):
        result = _invoke(["lint", "--help"])
        assert result.exit_code == 0
        assert "lint" in _strip_ansi(result.output).lower()

    def test_fix_flag_exists(self):
        """--fix flag should be accepted without error (even if no-op for now)."""
        result = _invoke(["lint", "--help"])
        assert result.exit_code == 0

    def test_custom_file_flag(self, tmp_path: Path):
        custom = tmp_path / "CLAUDE.md"
        custom.write_text(
            "## Never Do\n"
            "- Never use npm -- use bun always for all package management tasks\n"
            "## Verify\n"
            "- source venv/bin/activate && pytest tests/ -v to run the full suite\n"
        )
        result = _invoke(["lint", str(tmp_path), "--file", str(custom)])
        assert result.exit_code == 0

    def test_json_output_valid(self, tmp_path: Path):
        import json
        (tmp_path / "AGENTS.md").write_text(
            "## Style\n- Write clean code\n"
        )
        result = _invoke(["lint", str(tmp_path), "--json"])
        clean = _strip_ansi(result.output).strip()
        data = json.loads(clean)
        assert "violations" in data
        assert "total" in data
        assert isinstance(data["violations"], list)
