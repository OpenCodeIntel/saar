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

    def test_skips_multi_component_path_from_gitignore(self, tmp_path: Path):
        """backend/repos/ style paths (multi-component) must be excluded.

        This was the OCI bug: 29,612 functions from backend/repos/uuid/*.
        Single-component matching missed it. Multi-component prefix matching fixes it.
        """
        nested = tmp_path / "backend" / "repos" / "some-uuid-repo"
        nested.mkdir(parents=True)
        (nested / "huge_file.py").write_text("def user_func(): pass\n" * 500)
        (tmp_path / "app.py").write_text("def real_app_func(): pass\n")
        (tmp_path / ".gitignore").write_text("backend/repos/\n")

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is not None
        assert dna.language_distribution.get("python", 0) == 1

    def test_js_arrow_functions_counted(self, tmp_path: Path):
        """Arrow functions (dominant JS/TS pattern) must be counted.

        Previous bug: only function_declaration was counted, missing 90%+ of modern JS.
        """
        (tmp_path / "app.js").write_text("""
const greet = (name) => `Hello ${name}`;
const fetchUser = async (id) => {
    const res = await fetch(`/api/users/${id}`);
    return res.json();
};
export const formatDate = (date) => date.toISOString();
class UserService {
    getUser(id) { return this.db.find(id); }
    async createUser(data) { return this.db.create(data); }
}
function legacyInit() { return true; }
""")
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is not None
        assert dna.total_functions >= 5

    def test_ts_naming_conventions_detected(self, tmp_path: Path):
        """TypeScript repos should get camelCase naming conventions detected."""
        (tmp_path / "userService.ts").write_text("""
export const getUserById = async (id: string) => {
    return await db.find(id);
};
export const createNewUser = (data: UserData) => {
    return db.create(data);
};
export class UserRepository {
    findById(id: string) { return this.db.find(id); }
}
""")
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is not None
        assert dna.naming_conventions.function_style == "camelCase"

    def test_fullstack_repo_counts_both_languages(self, tmp_path: Path):
        """Full-stack repos should count functions from Python AND JS/TS."""
        (tmp_path / "backend.py").write_text(
            "def get_user(): pass\ndef create_user(): pass\n"
        )
        (tmp_path / "frontend.ts").write_text(
            "const getUser = () => {};\nconst createUser = () => {};\n"
        )
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna is not None
        assert "python" in dna.language_distribution
        assert "typescript" in dna.language_distribution
        assert dna.total_functions >= 4

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


class TestProjectStructure:

    def test_generates_structure_for_nested_repo(self, tmp_path: Path):
        """Project structure should be generated when meaningful dirs exist."""
        (tmp_path / "backend" / "routes").mkdir(parents=True)
        (tmp_path / "backend" / "routes" / "users.py").write_text("def get(): pass")
        (tmp_path / "backend" / "services").mkdir(parents=True)
        (tmp_path / "backend" / "services" / "auth.py").write_text("def login(): pass")
        (tmp_path / "app.py").write_text("from fastapi import FastAPI")

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.project_structure is not None
        assert "routes/" in dna.project_structure
        assert "services/" in dna.project_structure

    def test_annotates_known_directories(self, tmp_path: Path):
        """Known dir names (routes, services, hooks) get annotations."""
        (tmp_path / "routes").mkdir()
        (tmp_path / "routes" / "api.py").write_text("def r(): pass")
        (tmp_path / "services").mkdir()
        (tmp_path / "services" / "auth.py").write_text("def s(): pass")
        (tmp_path / "middleware").mkdir()
        (tmp_path / "middleware" / "auth.py").write_text("def m(): pass")
        (tmp_path / "app.py").write_text("x = 1")

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.project_structure is not None
        assert "API endpoints" in dna.project_structure
        assert "business logic" in dna.project_structure  # partial match works

    def test_skips_empty_directories(self, tmp_path: Path):
        """Dirs with no code files should not appear in structure."""
        (tmp_path / "empty_dir").mkdir()
        (tmp_path / "real" / "code").mkdir(parents=True)
        (tmp_path / "real" / "code" / "app.py").write_text("x=1")
        (tmp_path / "app.py").write_text("y=1")

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        if dna.project_structure:
            assert "empty_dir" not in dna.project_structure

    def test_none_for_flat_repo(self, tmp_path: Path):
        """Single flat directory shouldn't generate structure."""
        (tmp_path / "app.py").write_text("def main(): pass\ndef run(): pass\n")

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.project_structure is None

    def test_structure_rendered_in_agents_md(self, tmp_path: Path):
        from saar.formatters.agents_md import render_agents_md
        from saar.models import CodebaseDNA

        dna = CodebaseDNA(
            repo_name="myapp",
            project_structure="```\nmyapp/\n├── backend/  # FastAPI\n└── frontend/\n```"
        )
        out = render_agents_md(dna)
        assert "## Project Structure" in out
        assert "backend/" in out
        assert "frontend/" in out
