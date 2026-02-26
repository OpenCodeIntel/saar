"""Tests for output formatters.

Formatters are pure functions: (CodebaseDNA) -> str.
No disk I/O needed -- pass the fixture directly.
"""
import pytest

from saar.formatters import render
from saar.formatters.markdown import render_markdown
from saar.formatters.claude_md import render_claude_md
from saar.formatters.cursorrules import render_cursorrules
from saar.formatters.copilot import render_copilot
from saar.models import CodebaseDNA


class TestRenderDispatch:
    """Test the render() dispatcher."""

    def test_dispatch_markdown(self, sample_dna: CodebaseDNA):
        out = render(sample_dna, "markdown")
        assert "Codebase DNA" in out

    def test_dispatch_claude(self, sample_dna: CodebaseDNA):
        out = render(sample_dna, "claude")
        assert "CLAUDE.md" in out

    def test_dispatch_cursorrules(self, sample_dna: CodebaseDNA):
        out = render(sample_dna, "cursorrules")
        assert "Project:" in out

    def test_dispatch_copilot(self, sample_dna: CodebaseDNA):
        out = render(sample_dna, "copilot")
        assert "Copilot Instructions" in out

    def test_unknown_format_raises(self, sample_dna: CodebaseDNA):
        with pytest.raises(KeyError, match="Unknown format"):
            render(sample_dna, "nonexistent")


class TestMarkdownFormatter:
    """Tests for generic markdown output."""

    def test_includes_repo_name(self, sample_dna: CodebaseDNA):
        out = render_markdown(sample_dna)
        assert "my-project" in out

    def test_includes_framework(self, sample_dna: CodebaseDNA):
        out = render_markdown(sample_dna)
        assert "fastapi" in out

    def test_includes_languages(self, sample_dna: CodebaseDNA):
        out = render_markdown(sample_dna)
        assert "python: 45" in out
        assert "typescript: 20" in out

    def test_includes_auth(self, sample_dna: CodebaseDNA):
        out = render_markdown(sample_dna)
        assert "require_auth" in out
        assert "AuthContext" in out

    def test_includes_database(self, sample_dna: CodebaseDNA):
        out = render_markdown(sample_dna)
        assert "Supabase" in out
        assert "UUID" in out
        assert "Row Level Security" in out

    def test_includes_team_rules(self, sample_dna: CodebaseDNA):
        out = render_markdown(sample_dna)
        assert "No emojis" in out
        assert "CLAUDE.md" in out

    def test_includes_codebase_stats(self, sample_dna: CodebaseDNA):
        out = render_markdown(sample_dna)
        assert "200" in out  # total_functions
        assert "45%" in out  # async adoption
        assert "80%" in out  # type hints

    def test_includes_critical_files(self, sample_dna: CodebaseDNA):
        out = render_markdown(sample_dna)
        assert "services/auth.py" in out
        assert "12 dependents" in out

    def test_includes_circular_deps(self, sample_dna: CodebaseDNA):
        out = render_markdown(sample_dna)
        assert "Circular" in out
        assert "services/auth.py" in out
        assert "services/user.py" in out

    def test_empty_dna_no_crash(self, empty_dna: CodebaseDNA):
        out = render_markdown(empty_dna)
        assert "empty-project" in out


class TestClaudeMdFormatter:
    """Tests for CLAUDE.md output."""

    def test_imperative_style(self, sample_dna: CodebaseDNA):
        """CLAUDE.md should use imperative instructions."""
        out = render_claude_md(sample_dna)
        assert "Use" in out

    def test_includes_coding_conventions(self, sample_dna: CodebaseDNA):
        out = render_claude_md(sample_dna)
        assert "snake_case" in out
        assert "PascalCase" in out

    def test_includes_architecture(self, sample_dna: CodebaseDNA):
        out = render_claude_md(sample_dna)
        assert "Singleton in dependencies.py" in out

    def test_includes_testing(self, sample_dna: CodebaseDNA):
        out = render_claude_md(sample_dna)
        assert "pytest" in out

    def test_includes_stats(self, sample_dna: CodebaseDNA):
        out = render_claude_md(sample_dna)
        assert "200" in out  # functions
        assert "45%" in out  # async

    def test_includes_circular_warning(self, sample_dna: CodebaseDNA):
        out = render_claude_md(sample_dna)
        assert "Circular" in out

    def test_empty_dna_no_crash(self, empty_dna: CodebaseDNA):
        out = render_claude_md(empty_dna)
        assert "CLAUDE.md" in out


class TestCursorRulesFormatter:
    """Tests for .cursorrules output."""

    def test_includes_project_name(self, sample_dna: CodebaseDNA):
        out = render_cursorrules(sample_dna)
        assert "my-project" in out

    def test_includes_arch(self, sample_dna: CodebaseDNA):
        out = render_cursorrules(sample_dna)
        assert "require_auth" in out

    def test_includes_error_handling(self, sample_dna: CodebaseDNA):
        out = render_cursorrules(sample_dna)
        assert "HTTPException" in out

    def test_empty_dna_no_crash(self, empty_dna: CodebaseDNA):
        out = render_cursorrules(empty_dna)
        assert "empty-project" in out


class TestCopilotFormatter:
    """Tests for copilot-instructions.md output."""

    def test_includes_conventions(self, sample_dna: CodebaseDNA):
        out = render_copilot(sample_dna)
        assert "snake_case" in out

    def test_includes_database(self, sample_dna: CodebaseDNA):
        out = render_copilot(sample_dna)
        assert "Supabase" in out
        assert "UUID" in out

    def test_empty_dna_no_crash(self, empty_dna: CodebaseDNA):
        out = render_copilot(empty_dna)
        assert "empty-project" in out
