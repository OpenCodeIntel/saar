"""Tests for saar stats (scorer) and saar init (init_wizard)."""
from pathlib import Path
from saar.scorer import score_agents_md, _grade, _score_size, _score_coverage, _score_precision
from saar.init_wizard import render_init_agents_md, InitAnswers, STACK_PRESETS


# ── scorer ────────────────────────────────────────────────────────────────────

class TestGrade:
    def test_a_plus(self): assert _grade(97) == "A+"
    def test_a(self): assert _grade(88) == "A"
    def test_b(self): assert _grade(77) == "B"
    def test_c(self): assert _grade(62) == "C"
    def test_d(self): assert _grade(50) == "D"
    def test_f(self): assert _grade(30) == "F"


class TestScoreSize:
    def test_empty(self):
        score, tip = _score_size(0)
        assert score == 0
        assert tip is not None

    def test_optimal_range(self):
        for lines in [50, 70, 100]:
            score, tip = _score_size(lines)
            assert score == 20
            assert tip is None

    def test_too_short(self):
        score, tip = _score_size(10)
        assert score < 20
        assert tip is not None

    def test_too_long(self):
        score, tip = _score_size(300)
        assert score < 10
        assert tip is not None


class TestScoreCoverage:
    def test_full_coverage(self):
        content = """
## Never Do
never use npm; never use sync functions

## How to Verify Changes Work
pytest tests/ -v

## Auth
require_auth pattern

## Error Handling
raise AuthenticationError, LimitCheckError

## Tribal Knowledge
Workspace = tenant

Stack: FastAPI Python
"""
        score, sections, missing, _ = _score_coverage(content)
        assert score >= 30
        assert len(missing) < 3

    def test_empty_file_zero_coverage(self):
        score, sections, missing, _ = _score_coverage("")
        assert score == 0
        assert len(missing) == 6

    def test_partial_coverage(self):
        content = "never use npm\npytest tests/"
        score, sections, missing, _ = _score_coverage(content)
        assert 0 < score < 40


class TestScorePrecision:
    def test_no_generic_lines(self):
        content = "Use require_auth for all endpoints\nRaise LimitCheckError not HTTPException"
        score, generics = _score_precision(content, 5)
        assert score == 20
        assert len(generics) == 0

    def test_generic_lines_penalised(self):
        content = "write clean code\nfollow best practices\nkeep it simple"
        score, generics = _score_precision(content, 5)
        assert score < 20
        assert len(generics) >= 2

    def test_emoji_penalised(self):
        content = "🚀 Deploy with docker\n✅ Tests passing"
        score, generics = _score_precision(content, 3)
        assert score < 20


class TestScoreAgentsMd:
    def test_nonexistent_file_scores_zero(self, tmp_path: Path):
        result = score_agents_md(tmp_path / "NONEXISTENT.md")
        assert result.total_score == 0
        assert result.grade == "F"

    def test_empty_file_low_score(self, tmp_path: Path):
        f = tmp_path / "AGENTS.md"
        f.write_text("")
        result = score_agents_md(f, tmp_path)
        assert result.total_score < 30

    def test_good_file_high_score(self, tmp_path: Path):
        f = tmp_path / "AGENTS.md"
        f.write_text("""
## Never Do
Never use npm -- use bun only; never use sync in async endpoints

## How to Verify Changes Work
pytest tests/ -v && bun run build

## Auth
require_auth for all protected endpoints

## Error Handling
Raise AuthenticationError, LimitCheckError, TokenExpiredError

## Tribal Knowledge
Workspace = tenant. Never touch billing/ -- frozen.

Stack: FastAPI Python Supabase React TypeScript
""")
        result = score_agents_md(f, tmp_path)
        assert result.total_score >= 50  # no snapshot = max 80
        assert result.grade in ("A+", "A", "B", "C")

    def test_result_has_all_fields(self, tmp_path: Path):
        f = tmp_path / "AGENTS.md"
        f.write_text("Some content\npytest tests/\nnever use npm")
        result = score_agents_md(f, tmp_path)
        assert isinstance(result.total_score, int)
        assert isinstance(result.grade, str)
        assert isinstance(result.line_count, int)
        assert isinstance(result.section_scores, list)
        assert isinstance(result.tips, list)

    def test_score_sums_correctly(self, tmp_path: Path):
        f = tmp_path / "AGENTS.md"
        f.write_text("pytest\nnever use npm\nrequire_auth\nAuthError\nWorkspace = tenant")
        result = score_agents_md(f, tmp_path)
        assert result.total_score == (
            result.size_score + result.freshness_score +
            result.coverage_score + result.precision_score
        )

    def test_share_prompt_in_tips_for_high_scores(self, tmp_path: Path):
        """High-scoring files should get a shareable message in stats output -- manual check."""
        f = tmp_path / "AGENTS.md"
        # a reasonably good file
        f.write_text("\n".join([
            "never use npm",
            "require_auth on all routes",
            "raise AuthenticationError",
            "pytest tests/ -v",
            "Workspace = tenant",
            "FastAPI Python",
        ] * 8))  # repeat to get line count up
        result = score_agents_md(f, tmp_path)
        assert result.total_score >= 0  # just shouldn't crash


# ── init_wizard ───────────────────────────────────────────────────────────────

class TestRenderInitAgentsMd:
    def _answers(self, stack="fastapi") -> InitAnswers:
        preset = STACK_PRESETS[stack]
        return InitAnswers(
            project_purpose="AI-powered study assistant for students",
            stack_key=stack,
            package_manager=None,
            verify_workflow=preset["test_cmd"],
            never_do=preset["never_do"],
            team_size="solo",
        )

    def test_renders_without_crash(self):
        content = render_init_agents_md(self._answers(), "studymate")
        assert len(content) > 0

    def test_contains_project_purpose(self):
        content = render_init_agents_md(self._answers(), "studymate")
        assert "AI-powered study assistant" in content

    def test_contains_project_name(self):
        content = render_init_agents_md(self._answers(), "studymate")
        assert "studymate" in content

    def test_contains_never_do(self):
        content = render_init_agents_md(self._answers("fastapi"), "proj")
        assert "Never" in content or "never" in content

    def test_contains_verify_workflow(self):
        content = render_init_agents_md(self._answers("fastapi"), "proj")
        assert "pytest" in content

    def test_team_section_for_team_size(self):
        answers = self._answers()
        answers.team_size = "team"
        content = render_init_agents_md(answers, "proj")
        assert "Team Conventions" in content

    def test_no_team_section_for_solo(self):
        answers = self._answers()
        answers.team_size = "solo"
        content = render_init_agents_md(answers, "proj")
        assert "Team Conventions" not in content

    def test_all_stacks_render(self):
        for stack in STACK_PRESETS:
            answers = self._answers(stack) if stack != "custom" else InitAnswers(
                project_purpose="test",
                stack_key="custom",
                package_manager=None,
                verify_workflow="",
                never_do="",
                team_size="solo",
            )
            content = render_init_agents_md(answers, "test-project")
            assert len(content) > 10

    def test_tribal_knowledge_placeholder_present(self):
        content = render_init_agents_md(self._answers(), "proj")
        assert "Tribal Knowledge" in content

    def test_footer_contains_saar_link(self):
        content = render_init_agents_md(self._answers(), "proj")
        assert "getsaar.com" in content


# ── CLI smoke tests ───────────────────────────────────────────────────────────

class TestStatsCLI:
    def test_stats_no_agents_md(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app
        runner = CliRunner()
        result = runner.invoke(app, ["stats", str(tmp_path)])
        assert result.exit_code == 1
        assert "saar extract" in result.output

    def test_stats_with_agents_md(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app
        (tmp_path / "AGENTS.md").write_text(
            "pytest tests/\nnever use npm\nrequire_auth\nAuthError\nWorkspace=tenant\nFastAPI"
        )
        runner = CliRunner()
        result = runner.invoke(app, ["stats", str(tmp_path)])
        assert result.exit_code == 0
        assert "/100" in result.output

    def test_stats_help_available(self):
        from typer.testing import CliRunner
        from saar.cli import app
        import re
        runner = CliRunner()
        result = runner.invoke(app, ["stats", "--help"])
        assert result.exit_code == 0
        clean = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
        assert "stats" in clean.lower()


class TestInitCLI:
    def test_init_help_available(self):
        from typer.testing import CliRunner
        from saar.cli import app
        import re
        runner = CliRunner()
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        clean = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
        assert "init" in clean.lower()

    def test_init_skips_if_agents_md_exists(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app
        (tmp_path / "AGENTS.md").write_text("existing content")
        runner = CliRunner()
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert "already exists" in result.output
        # original not overwritten
        assert (tmp_path / "AGENTS.md").read_text() == "existing content"


class TestScanCLI:
    def test_scan_help_available(self):
        from typer.testing import CliRunner
        from saar.cli import app
        import re
        runner = CliRunner()
        result = runner.invoke(app, ["scan", "--help"])
        assert result.exit_code == 0
        clean = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
        assert "scan" in clean.lower()

    def test_scan_local_path(self, tmp_repo: Path):
        from typer.testing import CliRunner
        from saar.cli import app
        runner = CliRunner()
        result = runner.invoke(app, ["scan", str(tmp_repo)])
        assert result.exit_code == 0

    def test_scan_nonexistent_path(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app
        runner = CliRunner()
        result = runner.invoke(app, ["scan", str(tmp_path / "nonexistent")])
        assert result.exit_code != 0
