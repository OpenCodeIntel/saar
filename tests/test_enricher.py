"""Tests for the AI enrichment engine.

All tests mock the Anthropic API -- no real network calls, no API key needed.
Tests verify prompt construction, response parsing, error handling,
and graceful degradation when enrichment is unavailable.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from saar.enricher import enrich_answers, _build_raw_notes, _build_detected_stack
from saar.models import (
    CodebaseDNA, InterviewAnswers,
)


# -- fixtures ---------------------------------------------------------------

@pytest.fixture
def raw_answers() -> InterviewAnswers:
    """Deliberately messy, informal answers -- like a real developer would write."""
    return InterviewAnswers(
        project_purpose="supply chain api thing for warehouses",
        never_do="don't touch billing it's messy\nnever use sync with boto3",
        domain_terms="workspace means tenant not directory\npipeline is our etl thing",
        verify_workflow="run tests then check the docker thing works",
        auth_gotchas=None,
        off_limits="billing/ and core/auth.py",
        extra_context=None,
    )


@pytest.fixture
def enriched_response() -> dict:
    """What Claude should return after enriching the raw answers."""
    return {
        "project_purpose": "Supply chain API connecting warehouses to retail distribution centers.",
        "never_do": "- NEVER modify `billing/` -- legacy Stripe integration, no test coverage, frozen until Q3 migration\n- NEVER use `sync` functions with `boto3` -- blocks the async event loop",
        "domain_terms": "- `Workspace` = tenant-level container (maps to `Organization` in DB). NOT a file system directory.\n- `Pipeline` = ETL transformation sequence. NOT CI/CD.",
        "verify_workflow": "Run `pytest tests/ -v`, then `docker compose up -d && curl localhost:8000/health`",
        "auth_gotchas": None,
        "off_limits": "- `billing/` -- legacy Stripe, no tests, frozen pending migration\n- `core/auth.py` -- clock-skew workaround, extremely fragile",
        "extra_context": None,
    }


@pytest.fixture
def minimal_dna() -> CodebaseDNA:
    return CodebaseDNA(
        repo_name="warehouse-api",
        language_distribution={"python": 30},
        detected_framework="fastapi",
    )


def _make_mock_response(data: dict) -> MagicMock:
    """Build a mock Anthropic API response object."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = json.dumps(data)
    return mock_response


# -- _build_raw_notes ------------------------------------------------------

class TestBuildRawNotes:

    def test_includes_all_non_null_fields(self, raw_answers: InterviewAnswers):
        notes = _build_raw_notes(raw_answers)
        assert "supply chain api" in notes
        assert "don't touch billing" in notes
        assert "workspace means tenant" in notes
        assert "run tests" in notes
        assert "billing/ and core/auth.py" in notes

    def test_skips_null_fields(self, raw_answers: InterviewAnswers):
        raw_answers.auth_gotchas = None
        notes = _build_raw_notes(raw_answers)
        assert "AUTH / SECURITY" not in notes

    def test_empty_answers_returns_placeholder(self):
        notes = _build_raw_notes(InterviewAnswers())
        assert "no notes provided" in notes


# -- _build_detected_stack -------------------------------------------------

class TestBuildDetectedStack:

    def test_includes_framework(self, minimal_dna: CodebaseDNA):
        stack = _build_detected_stack(minimal_dna)
        assert "fastapi" in stack

    def test_includes_languages(self, minimal_dna: CodebaseDNA):
        stack = _build_detected_stack(minimal_dna)
        assert "python" in stack

    def test_handles_none_dna(self):
        stack = _build_detected_stack(None)
        assert stack == "unknown"

    def test_empty_dna_returns_unknown(self):
        dna = CodebaseDNA(repo_name="empty")
        stack = _build_detected_stack(dna)
        assert stack == "unknown"


# -- enrich_answers --------------------------------------------------------

class TestEnrichAnswers:

    def test_returns_original_when_no_api_key(self, raw_answers: InterviewAnswers):
        with patch.dict("os.environ", {}, clear=True):
            result, was_enriched = enrich_answers(raw_answers, api_key=None)
        assert was_enriched is False
        assert result is raw_answers  # same object -- no copy

    def test_returns_original_when_anthropic_not_installed(
        self, raw_answers: InterviewAnswers
    ):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("saar.enricher._anthropic_module", None):
                result, was_enriched = enrich_answers(raw_answers)
        assert was_enriched is False
        assert result is raw_answers

    def test_successful_enrichment(
        self,
        raw_answers: InterviewAnswers,
        enriched_response: dict,
        minimal_dna: CodebaseDNA,
    ):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(enriched_response)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("saar.enricher._anthropic_module") as mock_anthropic:
                mock_anthropic.Anthropic.return_value = mock_client
                result, was_enriched = enrich_answers(raw_answers, dna=minimal_dna)

        assert was_enriched is True
        assert result is not raw_answers  # new object returned
        assert "NEVER modify `billing/`" in result.never_do
        assert "`Workspace`" in result.domain_terms
        assert "pytest" in result.verify_workflow

    def test_enrichment_calls_correct_model(
        self, raw_answers: InterviewAnswers, enriched_response: dict
    ):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(enriched_response)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("saar.enricher._anthropic_module") as mock_anthropic:
                mock_anthropic.Anthropic.return_value = mock_client
                enrich_answers(raw_answers)

        call_kwargs = mock_client.messages.create.call_args[1]
        assert "haiku" in call_kwargs["model"]

    def test_strips_markdown_fences_from_response(
        self, raw_answers: InterviewAnswers, enriched_response: dict
    ):
        """Claude sometimes wraps JSON in ```json fences despite instructions."""
        mock_client = MagicMock()
        fenced = f"```json\n{json.dumps(enriched_response)}\n```"
        mock_client.messages.create.return_value.content = [MagicMock(text=fenced)]

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("saar.enricher._anthropic_module") as mock_anthropic:
                mock_anthropic.Anthropic.return_value = mock_client
                result, was_enriched = enrich_answers(raw_answers)

        assert was_enriched is True
        assert result.never_do is not None

    def test_invalid_json_falls_back_gracefully(self, raw_answers: InterviewAnswers):
        """Bad JSON from API should return original answers, not crash."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value.content = [
            MagicMock(text="this is not json {{{")
        ]

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("saar.enricher._anthropic_module") as mock_anthropic:
                mock_anthropic.Anthropic.return_value = mock_client
                result, was_enriched = enrich_answers(raw_answers)

        assert was_enriched is False
        assert result is raw_answers

    def test_api_exception_falls_back_gracefully(self, raw_answers: InterviewAnswers):
        """Network errors / API failures should return original answers, not crash."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Connection error")

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("saar.enricher._anthropic_module") as mock_anthropic:
                mock_anthropic.Anthropic.return_value = mock_client
                result, was_enriched = enrich_answers(raw_answers)

        assert was_enriched is False
        assert result is raw_answers

    def test_null_fields_from_api_fall_back_to_original(
        self, raw_answers: InterviewAnswers
    ):
        """If API returns null for a field, keep original answer for that field."""
        partial_response = {
            "project_purpose": "Enriched purpose",
            "never_do": None,  # API returned null
            "domain_terms": None,
            "verify_workflow": None,
            "auth_gotchas": None,
            "off_limits": None,
            "extra_context": None,
        }
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(partial_response)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("saar.enricher._anthropic_module") as mock_anthropic:
                mock_anthropic.Anthropic.return_value = mock_client
                result, was_enriched = enrich_answers(raw_answers)

        assert was_enriched is True
        assert result.project_purpose == "Enriched purpose"
        # original preserved when API returned null
        assert result.never_do == raw_answers.never_do

    def test_empty_answers_skips_enrichment(self):
        """No point calling API if there's nothing to enrich."""
        empty = InterviewAnswers()
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("saar.enricher._anthropic_module") as mock_anthropic:
                result, was_enriched = enrich_answers(empty)

        # should not have called the API at all
        mock_anthropic.Anthropic.assert_not_called()
        assert was_enriched is False


# -- saar enrich CLI command -----------------------------------------------

class TestSaarEnrichCommand:

    def test_enrich_no_cache_exits_with_error(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app
        runner = CliRunner()
        result = runner.invoke(app, ["enrich", "--repo", str(tmp_path)])
        assert result.exit_code == 1
        assert "No cached" in result.stdout

    def test_enrich_no_api_key_exits_with_error(
        self, tmp_path: Path, raw_answers: InterviewAnswers
    ):
        from typer.testing import CliRunner
        from saar.cli import app
        from saar.interview import save_cache
        runner = CliRunner()
        save_cache(tmp_path, raw_answers)
        with patch.dict("os.environ", {}, clear=True):
            result = runner.invoke(app, ["enrich", "--repo", str(tmp_path)])
        assert result.exit_code == 1

    def test_enrich_dry_run_does_not_save(
        self, tmp_path: Path, raw_answers: InterviewAnswers, enriched_response: dict
    ):
        from typer.testing import CliRunner
        from saar.cli import app
        from saar.interview import save_cache, load_cached
        runner = CliRunner()
        save_cache(tmp_path, raw_answers)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(enriched_response)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("saar.enricher._anthropic_module") as mock_anthropic:
                mock_anthropic.Anthropic.return_value = mock_client
                result = runner.invoke(
                    app, ["enrich", "--repo", str(tmp_path), "--dry-run"]
                )

        assert result.exit_code == 0
        # cache should still have original answers
        saved = load_cached(tmp_path)
        assert saved.project_purpose == raw_answers.project_purpose

    def test_enrich_saves_enriched_answers(
        self, tmp_path: Path, raw_answers: InterviewAnswers, enriched_response: dict
    ):
        from typer.testing import CliRunner
        from saar.cli import app
        from saar.interview import save_cache, load_cached
        runner = CliRunner()
        save_cache(tmp_path, raw_answers)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(enriched_response)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("saar.enricher._anthropic_module") as mock_anthropic:
                mock_anthropic.Anthropic.return_value = mock_client
                result = runner.invoke(app, ["enrich", "--repo", str(tmp_path)])

        assert result.exit_code == 0
        saved = load_cached(tmp_path)
        assert saved is not None
        assert "NEVER modify" in saved.never_do
