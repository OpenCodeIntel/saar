"""Tests for the guided interview engine.

Interview is non-interactive by design in tests -- all paths that
touch questionary are gated behind is_interactive(), which returns
False in CI (no TTY). We test everything except the live prompt flow.
"""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from saar.interview import (
    is_interactive,
    load_cached,
    save_cache,
    run_interview,
    _build_detection_summary,
    _CACHE_FILENAME,
)
from saar.models import CodebaseDNA, InterviewAnswers, NamingConventions, TestPattern


# -- fixtures --------------------------------------------------------------

@pytest.fixture
def minimal_dna() -> CodebaseDNA:
    return CodebaseDNA(
        repo_name="test-project",
        language_distribution={"python": 5},
        detected_framework="fastapi",
        total_functions=42,
        naming_conventions=NamingConventions(function_style="snake_case"),
        test_patterns=TestPattern(framework="pytest"),
    )


@pytest.fixture
def sample_answers() -> InterviewAnswers:
    return InterviewAnswers(
        project_purpose="Supply chain API",
        never_do="Never modify billing/, never use sync in async endpoints",
        domain_terms="Workspace = tenant, not directory",
        verify_workflow="pytest -x, then docker compose up",
        auth_gotchas="JWT expires in 15min",
        off_limits="core/auth.py",
        extra_context="Always use the repo logger, never print()",
    )


# -- is_interactive --------------------------------------------------------

class TestIsInteractive:

    def test_no_interview_flag_disables(self):
        assert is_interactive(no_interview=True) is False

    def test_ci_env_var_disables(self):
        with patch.dict(os.environ, {"CI": "true"}):
            assert is_interactive(no_interview=False) is False

    def test_github_actions_disables(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            assert is_interactive() is False

    def test_non_tty_stdin_disables(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            assert is_interactive() is False

    def test_non_tty_stdout_disables(self):
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = False
            assert is_interactive() is False

    def test_clean_env_and_tty_enables(self):
        # remove CI vars, fake TTY
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("CI", "GITHUB_ACTIONS", "GITLAB_CI",
                                  "JENKINS_URL", "CIRCLECI", "TRAVIS",
                                  "BUILDKITE", "TF_BUILD")}
        with patch.dict(os.environ, clean_env, clear=True):
            with patch("sys.stdin") as mock_stdin, patch("sys.stdout") as mock_stdout:
                mock_stdin.isatty.return_value = True
                mock_stdout.isatty.return_value = True
                assert is_interactive(no_interview=False) is True


# -- cache -----------------------------------------------------------------

class TestInterviewCache:

    def test_save_and_load_roundtrip(self, tmp_path: Path, sample_answers: InterviewAnswers):
        save_cache(tmp_path, sample_answers)
        loaded = load_cached(tmp_path)
        assert loaded is not None
        assert loaded.project_purpose == sample_answers.project_purpose
        assert loaded.never_do == sample_answers.never_do
        assert loaded.domain_terms == sample_answers.domain_terms
        assert loaded.verify_workflow == sample_answers.verify_workflow
        assert loaded.auth_gotchas == sample_answers.auth_gotchas
        assert loaded.off_limits == sample_answers.off_limits
        assert loaded.extra_context == sample_answers.extra_context

    def test_cache_file_location(self, tmp_path: Path, sample_answers: InterviewAnswers):
        save_cache(tmp_path, sample_answers)
        cache_file = tmp_path / _CACHE_FILENAME
        assert cache_file.exists()

    def test_cache_creates_gitignore(self, tmp_path: Path, sample_answers: InterviewAnswers):
        save_cache(tmp_path, sample_answers)
        gitignore = tmp_path / ".saar" / ".gitignore"
        assert gitignore.exists()
        assert "config.json" in gitignore.read_text()

    def test_cache_has_version(self, tmp_path: Path, sample_answers: InterviewAnswers):
        save_cache(tmp_path, sample_answers)
        data = json.loads((tmp_path / _CACHE_FILENAME).read_text())
        assert data["version"] == 1

    def test_load_missing_returns_none(self, tmp_path: Path):
        result = load_cached(tmp_path)
        assert result is None

    def test_load_wrong_version_returns_none(self, tmp_path: Path):
        cache_dir = tmp_path / ".saar"
        cache_dir.mkdir()
        (tmp_path / _CACHE_FILENAME).write_text(
            json.dumps({"version": 99, "answers": {"project_purpose": "test"}}),
            encoding="utf-8",
        )
        result = load_cached(tmp_path)
        assert result is None

    def test_load_corrupt_file_returns_none(self, tmp_path: Path):
        cache_dir = tmp_path / ".saar"
        cache_dir.mkdir()
        (tmp_path / _CACHE_FILENAME).write_text("not json {{{{", encoding="utf-8")
        result = load_cached(tmp_path)
        assert result is None

    def test_partial_answers_preserved(self, tmp_path: Path):
        """Only some fields filled -- others should load as None."""
        partial = InterviewAnswers(project_purpose="Just the purpose")
        save_cache(tmp_path, partial)
        loaded = load_cached(tmp_path)
        assert loaded is not None
        assert loaded.project_purpose == "Just the purpose"
        assert loaded.never_do is None
        assert loaded.domain_terms is None


# -- detection summary -----------------------------------------------------

class TestDetectionSummary:

    def test_includes_language(self, minimal_dna: CodebaseDNA):
        summary = _build_detection_summary(minimal_dna)
        assert "python" in summary

    def test_includes_framework(self, minimal_dna: CodebaseDNA):
        summary = _build_detection_summary(minimal_dna)
        assert "fastapi" in summary

    def test_includes_test_framework(self, minimal_dna: CodebaseDNA):
        summary = _build_detection_summary(minimal_dna)
        assert "pytest" in summary

    def test_empty_dna_no_crash(self):
        dna = CodebaseDNA(repo_name="empty")
        summary = _build_detection_summary(dna)
        assert isinstance(summary, str)


# -- run_interview non-interactive paths -----------------------------------

class TestRunInterviewNonInteractive:

    def test_no_interview_flag_returns_cache(
        self, tmp_path: Path, minimal_dna: CodebaseDNA, sample_answers: InterviewAnswers
    ):
        save_cache(tmp_path, sample_answers)
        result = run_interview(minimal_dna, tmp_path, no_interview=True)
        assert result is not None
        assert result.project_purpose == sample_answers.project_purpose

    def test_no_interview_flag_no_cache_returns_none(
        self, tmp_path: Path, minimal_dna: CodebaseDNA
    ):
        result = run_interview(minimal_dna, tmp_path, no_interview=True)
        assert result is None

    def test_ci_env_returns_cache(
        self, tmp_path: Path, minimal_dna: CodebaseDNA, sample_answers: InterviewAnswers
    ):
        save_cache(tmp_path, sample_answers)
        with patch.dict(os.environ, {"CI": "true"}):
            result = run_interview(minimal_dna, tmp_path)
        assert result is not None
        assert result.project_purpose == sample_answers.project_purpose

    def test_ci_env_no_cache_returns_none(
        self, tmp_path: Path, minimal_dna: CodebaseDNA
    ):
        with patch.dict(os.environ, {"CI": "true"}):
            result = run_interview(minimal_dna, tmp_path)
        assert result is None


# -- tribal knowledge in formatters ----------------------------------------

class TestTribalKnowledgeInFormatters:

    def test_agents_md_includes_tribal_knowledge(self, minimal_dna: CodebaseDNA):
        from saar.formatters.agents_md import render_agents_md
        minimal_dna.interview = InterviewAnswers(
            project_purpose="Supply chain API",
            never_do="Never touch billing/",
            domain_terms="Workspace = tenant",
        )
        out = render_agents_md(minimal_dna)
        assert "Tribal Knowledge" in out
        assert "Supply chain API" in out
        assert "Never touch billing/" in out
        assert "Workspace = tenant" in out

    def test_claude_md_includes_tribal_knowledge(self, minimal_dna: CodebaseDNA):
        from saar.formatters.claude_md import render_claude_md
        minimal_dna.interview = InterviewAnswers(
            project_purpose="Internal tooling",
            never_do="Never use global state",
        )
        out = render_claude_md(minimal_dna)
        assert "Tribal Knowledge" in out
        assert "Internal tooling" in out
        assert "Never use global state" in out

    def test_no_interview_no_tribal_section(self, minimal_dna: CodebaseDNA):
        from saar.formatters.agents_md import render_agents_md
        minimal_dna.interview = None
        out = render_agents_md(minimal_dna)
        assert "Tribal Knowledge" not in out

    def test_empty_interview_no_tribal_section(self, minimal_dna: CodebaseDNA):
        from saar.formatters.agents_md import render_agents_md
        minimal_dna.interview = InterviewAnswers()  # all None
        out = render_agents_md(minimal_dna)
        assert "Tribal Knowledge" not in out

    def test_off_limits_rendered_with_code_formatting(self, minimal_dna: CodebaseDNA):
        from saar.formatters._tribal import render_tribal_knowledge
        answers = InterviewAnswers(off_limits="core/auth.py")
        out = render_tribal_knowledge(answers)
        assert "`core/auth.py`" in out

    def test_verify_workflow_rendered(self, minimal_dna: CodebaseDNA):
        from saar.formatters._tribal import render_tribal_knowledge
        answers = InterviewAnswers(verify_workflow="pytest -x && docker compose up")
        out = render_tribal_knowledge(answers)
        assert "Verification Workflow" in out
        assert "pytest -x" in out


# -- append_to_cache (saar add) --------------------------------------------

class TestAppendToCache:

    def test_append_creates_cache_if_missing(self, tmp_path: Path):
        from saar.interview import append_to_cache
        result = append_to_cache(tmp_path, "never_do", "Never use print()")
        assert result.never_do is not None
        assert "Never use print()" in result.never_do

    def test_append_to_empty_field(self, tmp_path: Path):
        from saar.interview import append_to_cache
        result = append_to_cache(tmp_path, "domain_terms", "Workspace = tenant")
        assert "Workspace = tenant" in result.domain_terms

    def test_append_to_existing_field_merges(self, tmp_path: Path):
        from saar.interview import append_to_cache
        append_to_cache(tmp_path, "never_do", "Never use print()")
        result = append_to_cache(tmp_path, "never_do", "Never modify billing/")
        assert "Never use print()" in result.never_do
        assert "Never modify billing/" in result.never_do

    def test_multiple_appends_are_bullet_list(self, tmp_path: Path):
        from saar.interview import append_to_cache
        append_to_cache(tmp_path, "never_do", "Rule one")
        append_to_cache(tmp_path, "never_do", "Rule two")
        result = append_to_cache(tmp_path, "never_do", "Rule three")
        lines = [ln.strip() for ln in result.never_do.splitlines() if ln.strip()]
        assert len(lines) == 3
        assert all(ln.startswith("- ") for ln in lines)

    def test_append_persists_to_disk(self, tmp_path: Path):
        from saar.interview import append_to_cache, load_cached
        append_to_cache(tmp_path, "off_limits", "core/auth.py")
        loaded = load_cached(tmp_path)
        assert loaded is not None
        assert "core/auth.py" in loaded.off_limits

    def test_append_does_not_touch_other_fields(self, tmp_path: Path, sample_answers: InterviewAnswers):
        from saar.interview import append_to_cache, save_cache
        save_cache(tmp_path, sample_answers)
        result = append_to_cache(tmp_path, "never_do", "New rule")
        # other fields should be unchanged
        assert result.project_purpose == sample_answers.project_purpose
        assert result.domain_terms == sample_answers.domain_terms
        assert result.verify_workflow == sample_answers.verify_workflow


# -- saar add CLI command --------------------------------------------------

class TestSaarAddCommand:

    def test_add_default_goes_to_never_do(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app
        from saar.interview import load_cached
        runner = CliRunner()
        result = runner.invoke(app, ["add", "Never modify billing/", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert "Added" in result.stdout or "added" in result.stdout
        cached = load_cached(tmp_path)
        assert cached is not None
        assert "Never modify billing/" in cached.never_do

    def test_add_domain_flag(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app
        from saar.interview import load_cached
        runner = CliRunner()
        result = runner.invoke(app, ["add", "Workspace = tenant", "--domain", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        cached = load_cached(tmp_path)
        assert cached.domain_terms is not None
        assert "Workspace = tenant" in cached.domain_terms

    def test_add_off_limits_flag(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app
        from saar.interview import load_cached
        runner = CliRunner()
        result = runner.invoke(app, ["add", "core/auth.py", "--off-limits", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        cached = load_cached(tmp_path)
        assert "core/auth.py" in cached.off_limits

    def test_add_multiple_corrections_stack(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app
        from saar.interview import load_cached
        runner = CliRunner()
        runner.invoke(app, ["add", "Rule one", "--repo", str(tmp_path)])
        runner.invoke(app, ["add", "Rule two", "--repo", str(tmp_path)])
        cached = load_cached(tmp_path)
        assert "Rule one" in cached.never_do
        assert "Rule two" in cached.never_do

    def test_add_shows_confirmation(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app
        runner = CliRunner()
        result = runner.invoke(app, ["add", "Never use sync with boto3", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert "Never use sync with boto3" in result.stdout


class TestInterviewUX:
    """UX invariants -- things that must never regress."""

    def test_no_multiline_prompts_in_interview(self):
        """multiline=True in questionary requires Alt+Enter to submit.

        This is a UX trap -- developers type their answer, press Enter,
        and the prompt appears frozen. Every multiline prompt is a bug.
        Single-line prompts with semicolons as separators are the right pattern.

        This test reads the source file directly so it catches the regression
        even if the prompt is added inside a conditional branch.
        """
        import ast
        from pathlib import Path

        source = (Path(__file__).parent.parent / "saar" / "interview.py").read_text()
        tree = ast.parse(source)

        violations = []
        for node in ast.walk(tree):
            # look for keyword arguments named 'multiline' with value True
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if (
                        keyword.arg == "multiline"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                    ):
                        violations.append(f"line {node.lineno}: multiline=True found")

        assert not violations, (
            "multiline=True detected in interview.py -- this breaks UX. "
            "Use single-line prompts with semicolons as separators instead.\n"
            + "\n".join(violations)
        )

    def test_all_questions_have_instructions(self):
        """Every questionary.text() call should have an instruction kwarg.

        Instructions show the user what format to use. Without them,
        developers don't know how to answer and leave fields blank.
        """
        import ast
        from pathlib import Path

        source = (Path(__file__).parent.parent / "saar" / "interview.py").read_text()
        tree = ast.parse(source)

        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # check if this is a questionary.text() call
                is_q_text = (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "text"
                )
                if is_q_text:
                    kwarg_names = {kw.arg for kw in node.keywords}
                    if "instruction" not in kwarg_names:
                        violations.append(f"line {node.lineno}: questionary.text() missing instruction=")

        assert not violations, (
            "questionary.text() calls without instruction= kwarg found:\n"
            + "\n".join(violations)
        )
