"""Tests for the DNA extractor engine."""
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
        assert any("logging" in imp for imp in dna.common_imports)


    def test_enriches_with_style(self, tmp_repo: Path):
        """Style analyzer should populate function/class counts."""
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_repo))
        assert dna.total_functions >= 2
        assert dna.total_classes >= 1

    def test_enriches_with_deps(self, tmp_repo: Path):
        """Dependency analyzer should populate graph data."""
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_repo))
        # tmp_repo has dependencies.py importing from services/
        assert dna.total_dependencies >= 0


class TestFileClassification:
    """Test that app code and test code are separated correctly."""

    def test_separates_app_and_test_files(self, tmp_repo: Path):
        """_discover_files should split files into app and test lists."""
        extractor = DNAExtractor()
        app_files, test_files = extractor._discover_files(tmp_repo)
        app_names = {f.name for f in app_files}
        test_names = {f.name for f in test_files}
        assert "main.py" in app_names
        assert "user_service.py" in app_names
        assert "test_main.py" in test_names
        assert "conftest.py" in test_names

    def test_no_false_positives_from_test_fixtures(self, tmp_path: Path):
        """Patterns in test fixtures should not appear in extraction."""
        # app code -- plain Python, no frameworks
        (tmp_path / "app.py").write_text(
            "import logging\n\n"
            "logger = logging.getLogger(__name__)\n\n"
            "def main():\n"
            "    logger.info('starting')\n"
        )
        # test file that mentions Flask -- should NOT trigger flask detection
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "__init__.py").write_text("")
        (tests / "test_app.py").write_text(
            "from flask import Flask\n"
            "from flask_login import login_required\n\n"
            "def test_something():\n"
            "    assert True\n"
        )

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is not None
        # Should NOT detect flask -- it's only in test code
        assert dna.detected_framework is None
        assert "flask_login" not in dna.auth_patterns.middleware_used

    def test_no_false_positives_from_string_literals(self, tmp_path: Path):
        """String mentions of frameworks should not trigger detection."""
        (tmp_path / "formatter.py").write_text(
            "import logging\n\n"
            "def format_output():\n"
            "    return 'This project uses from fastapi import FastAPI'\n"
        )

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is not None
        # "from fastapi" is inside a string, not a real import
        assert dna.detected_framework is None

    def test_dataclass_not_detected_as_exception(self, tmp_path: Path):
        """Pattern dataclasses like ErrorPattern should not be listed as exceptions."""
        (tmp_path / "models.py").write_text(
            "from dataclasses import dataclass\n\n"
            "@dataclass\n"
            "class ErrorPattern:\n"
            "    message: str = ''\n\n"
            "class AppError(Exception):\n"
            "    pass\n"
        )

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is not None
        assert "AppError" in dna.error_patterns.exception_classes
        assert "ErrorPattern" not in dna.error_patterns.exception_classes


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
        nm = tmp_path / "node_modules" / "somelib"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("export default function() {}")
        (tmp_path / "app.py").write_text("x = 1")

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is not None
        assert dna.language_distribution.get("javascript", 0) == 0

    def test_handles_binary_files(self, tmp_path: Path):
        (tmp_path / "data.py").write_bytes(b"\x00\x01\x02\x03" * 100)
        (tmp_path / "real.py").write_text("x = 1")

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is not None

    def test_respects_max_file_size(self, tmp_path: Path):
        big = tmp_path / "big.py"
        big.write_text("x = 1\n" * 200_000)

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is not None

    def test_skips_repos_dir(self, tmp_path: Path):
        """repos/ should be skipped -- it contains user-cloned repos, not project code."""
        repos_dir = tmp_path / "repos" / "some-user-repo"
        repos_dir.mkdir(parents=True)
        # put a python file inside repos/ -- should NOT be counted
        (repos_dir / "main.py").write_text("def user_code(): pass\n" * 50)
        # real project code
        (tmp_path / "app.py").write_text("def real_function(): pass\n")

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is not None
        # only app.py should be counted, not repos/
        assert dna.language_distribution.get("python", 0) == 1

    def test_skips_dist_and_build(self, tmp_path: Path):
        """dist/ and build/ are generated artifacts, not source code."""
        for junk_dir in ["dist", "build", "out"]:
            d = tmp_path / junk_dir
            d.mkdir()
            (d / "bundle.py").write_text("# compiled output\n" * 100)
        (tmp_path / "src.py").write_text("def real(): pass\n")

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is not None
        assert dna.language_distribution.get("python", 0) == 1

    def test_respects_saarignore(self, tmp_path: Path):
        """.saarignore uses same syntax as .gitignore and is merged into skip dirs."""
        custom_dir = tmp_path / "vendor"
        custom_dir.mkdir()
        (custom_dir / "lib.py").write_text("def vendor_code(): pass\n" * 20)
        (tmp_path / "app.py").write_text("def real(): pass\n")
        # tell saar to skip vendor/ via .saarignore
        (tmp_path / ".saarignore").write_text("vendor/\n")

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is not None
        assert dna.language_distribution.get("python", 0) == 1

    def test_saarignore_stacks_with_gitignore(self, tmp_path: Path):
        """Both .gitignore and .saarignore dirs are skipped -- they merge, not replace."""
        (tmp_path / "gitignored").mkdir()
        (tmp_path / "gitignored" / "a.py").write_text("x = 1\n" * 10)
        (tmp_path / "saarignored").mkdir()
        (tmp_path / "saarignored" / "b.py").write_text("y = 2\n" * 10)
        (tmp_path / "real.py").write_text("def real(): pass\n")
        (tmp_path / ".gitignore").write_text("gitignored/\n")
        (tmp_path / ".saarignore").write_text("saarignored/\n")

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is not None
        assert dna.language_distribution.get("python", 0) == 1
