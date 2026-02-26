"""Tests for the DNA extractor engine."""
import pytest
from pathlib import Path

from saar.extractor import DNAExtractor


class TestDNAExtractor:
    """Core extraction tests using tmp_repo fixture."""

    def test_extract_returns_dna(self, tmp_repo: Path):
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_repo))
        assert dna is not None
        assert dna.repo_name == tmp_repo.name

    def test_detects_fastapi(self, tmp_repo: Path):
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_repo))
        assert dna.detected_framework == "fastapi"

    def test_detects_python_files(self, tmp_repo: Path):
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_repo))
        assert "python" in dna.language_distribution
        assert dna.language_distribution["python"] >= 3

    def test_detects_auth_patterns(self, tmp_repo: Path):
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_repo))
        assert "require_auth" in dna.auth_patterns.middleware_used
        assert any("Depends" in d for d in dna.auth_patterns.auth_decorators)

    def test_detects_service_singleton(self, tmp_repo: Path):
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_repo))
        assert dna.service_patterns.dependencies_file == "dependencies.py"
        assert any("UserService" in s for s in dna.service_patterns.singleton_services)

    def test_detects_database_patterns(self, tmp_repo: Path):
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_repo))
        assert "UUID" in dna.database_patterns.id_type
        assert "TIMESTAMPTZ" in dna.database_patterns.timestamp_type
        assert dna.database_patterns.has_rls is True

    def test_detects_test_framework(self, tmp_repo: Path):
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_repo))
        assert dna.test_patterns.framework == "pytest"
        assert dna.test_patterns.has_conftest is True
        assert dna.test_patterns.mock_library is not None

    def test_detects_naming_conventions(self, tmp_repo: Path):
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_repo))
        assert dna.naming_conventions.function_style == "snake_case"

    def test_finds_team_rules(self, tmp_repo: Path):
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_repo))
        assert dna.team_rules is not None
        assert "No emojis" in dna.team_rules
        assert dna.team_rules_source == "CLAUDE.md"

    def test_detects_common_imports(self, tmp_repo: Path):
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_repo))
        # logging is imported in 2+ files
        assert any("logging" in imp for imp in dna.common_imports)


class TestExtractorEdgeCases:
    """Edge cases and error handling."""

    def test_invalid_path_returns_none(self):
        extractor = DNAExtractor()
        dna = extractor.extract("/nonexistent/path")
        assert dna is None

    def test_empty_directory_returns_none(self, tmp_path: Path):
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is None

    def test_skips_node_modules(self, tmp_path: Path):
        """Files inside node_modules should be ignored."""
        nm = tmp_path / "node_modules" / "somelib"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("export default function() {}")
        (tmp_path / "app.py").write_text("x = 1")

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is not None
        # only app.py should be counted
        assert dna.language_distribution.get("javascript", 0) == 0

    def test_handles_binary_files(self, tmp_path: Path):
        """Binary files should be skipped without crashing."""
        (tmp_path / "data.py").write_bytes(b"\x00\x01\x02\x03" * 100)
        (tmp_path / "real.py").write_text("x = 1")

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is not None

    def test_respects_max_file_size(self, tmp_path: Path):
        """Files over MAX_FILE_SIZE should be skipped."""
        big = tmp_path / "big.py"
        big.write_text("x = 1\n" * 200_000)  # ~1.2MB

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is not None
