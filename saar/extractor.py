"""Core DNA extraction engine.

Analyzes a codebase using tree-sitter AST parsing and pattern
matching to extract architectural patterns, conventions, and
constraints. This is the heart of Saar.

Key design decisions:
- Separates app code from test/template code to avoid false positives
- Pattern matching targets line-start positions to skip string literals
- File cache avoids re-reading files across extraction methods
- File is >200 lines because all methods form one cohesive pipeline
"""
import logging
import re
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser

from saar.models import (
    AuthPattern,
    CodebaseDNA,
    ConfigPattern,
    DatabasePattern,
    ErrorPattern,
    LoggingPattern,
    NamingConventions,
    ServicePattern,
    TestPattern,
)

logger = logging.getLogger(__name__)

# Directories that contain tests, not application code
_TEST_DIRS = {"tests", "test", "testing", "spec", "specs", "__tests__"}

# Files that are test files by naming convention
_TEST_PATTERNS = re.compile(r"^(test_|_test\.py|spec_|_spec\.)")


class DNAExtractor:
    """Extracts architectural DNA from a codebase.

    Zero external dependencies beyond tree-sitter. Runs locally,
    reads files from disk, returns a CodebaseDNA dataclass.
    """

    SKIP_DIRS = {
        # version control
        ".git",
        # python
        "__pycache__", "venv", "env", ".venv", "site-packages",
        "*.egg-info", ".eggs",
        # js/ts
        "node_modules", ".next", ".nuxt", ".svelte-kit",
        # build outputs
        "dist", "build", "out", "target",
        # test/coverage artifacts
        "coverage", ".pytest_cache", "htmlcov", ".nyc_output",
        # common data / cloned repo dirs that aren't project code
        "repos", "data", "datasets", "tmp", "temp", "cache",
        # ide
        ".idea", ".vscode",
    }
    MAX_FILE_SIZE = 1024 * 1024  # 1MB
    MAX_FILES = 5000

    RULES_FILES = [
        "CLAUDE.md",
        ".cursorrules",
        ".codeintel/rules.md",
        "CONVENTIONS.md",
        ".github/copilot-instructions.md",
        "CODING_GUIDELINES.md",
    ]

    def __init__(self) -> None:
        self.parsers = {
            "python": Parser(Language(tspython.language())),
            "javascript": Parser(Language(tsjavascript.language())),
            "typescript": Parser(Language(tsjavascript.language())),
        }
        self._file_cache: Dict[Path, str] = {}
        self._stats = {"files_read": 0, "files_skipped": 0, "read_errors": 0}
        self._active_skip_dirs = set(self.SKIP_DIRS)

    # -- file I/O ---------------------------------------------------------

    def _reset_cache(self) -> None:
        self._file_cache.clear()
        self._stats = {"files_read": 0, "files_skipped": 0, "read_errors": 0}

    def _safe_read_file(self, file_path: Path) -> Optional[str]:
        """Read file with caching, size limits, and encoding fallback."""
        if file_path in self._file_cache:
            return self._file_cache[file_path]

        try:
            if file_path.stat().st_size > self.MAX_FILE_SIZE:
                self._stats["files_skipped"] += 1
                return None

            content = None
            for encoding in ["utf-8", "latin-1", "cp1252"]:
                try:
                    content = file_path.read_text(encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                self._stats["read_errors"] += 1
                return None

            if "\x00" in content[:1024]:
                self._stats["files_skipped"] += 1
                return None

            self._file_cache[file_path] = content
            self._stats["files_read"] += 1
            return content

        except Exception as e:
            logger.debug("Error reading %s: %s", file_path, e)
            self._stats["read_errors"] += 1
            return None

    # -- file discovery and classification --------------------------------

    @staticmethod
    def _is_test_file(file_path: Path) -> bool:
        """Check if a file is a test file by directory or naming convention."""
        if any(d in _TEST_DIRS for d in file_path.parts):
            return True
        if _TEST_PATTERNS.match(file_path.name):
            return True
        if file_path.name == "conftest.py":
            return True
        return False

    def _discover_files(self, repo_path: Path) -> Tuple[List[Path], List[Path]]:
        """Find code files, split into app files and test files.

        Returns:
            Tuple of (app_files, test_files). Pattern detection runs
            only on app_files to avoid false positives from test
            fixtures and template strings.
        """
        app_files: List[Path] = []
        test_files: List[Path] = []
        extensions = {".py", ".js", ".jsx", ".ts", ".tsx", ".sql"}

        try:
            for item in repo_path.rglob("*"):
                if item.is_symlink():
                    continue
                if item.is_file() and item.suffix in extensions:
                    if any(skip in item.parts for skip in self._active_skip_dirs):
                        continue
                    total = len(app_files) + len(test_files)
                    if total >= self.MAX_FILES:
                        logger.warning("Hit max file limit (%d)", self.MAX_FILES)
                        break
                    if self._is_test_file(item):
                        test_files.append(item)
                    else:
                        app_files.append(item)
        except Exception as e:
            logger.error("Error discovering files: %s", e)

        return app_files, test_files

    def _detect_language(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        return {
            ".py": "python", ".js": "javascript", ".jsx": "javascript",
            ".ts": "typescript", ".tsx": "typescript",
        }.get(ext, "unknown")

    def _read_ignore_dirs(self, repo_path: Path) -> set:
        """Parse .gitignore and .saarignore for directory patterns to skip.

        Reads both files and merges results. Only handles simple directory
        names and trailing-slash patterns -- no glob negation. A full
        gitignore-spec parser is overkill for our use case.
        """
        dirs: set = set()
        # check both ignore files -- .saarignore takes same syntax as .gitignore
        for ignore_file in [repo_path / ".gitignore", repo_path / ".saarignore"]:
            if not ignore_file.exists():
                continue
            try:
                for line in ignore_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    # lines ending with / are explicitly directories
                    if line.endswith("/"):
                        dirs.add(line.rstrip("/"))
                    # bare names without glob chars that exist as dirs in the repo
                    elif "/" not in line and "*" not in line and "!" not in line:
                        candidate = repo_path / line
                        if candidate.is_dir():
                            dirs.add(line)
            except Exception as e:
                logger.debug("Error reading %s: %s", ignore_file.name, e)
        if dirs:
            logger.debug("Ignore file dirs to skip: %s", dirs)
        return dirs

    # -- team rules -------------------------------------------------------

    def _extract_team_rules(
        self, repo_path: Path, exclude_files: Optional[list] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Find and read team convention files (CLAUDE.md, .cursorrules, etc.).

        Args:
            exclude_files: Filenames to skip (prevents inception loop).
        """
        skip = set(exclude_files or [])
        for filename in self.RULES_FILES:
            if filename in skip:
                logger.debug("Skipping %s (exclude list)", filename)
                continue
            rules_path = repo_path / filename
            if rules_path.exists() and rules_path.is_file():
                content = self._safe_read_file(rules_path)
                if content:
                    logger.info("Found team rules in %s", filename)
                    return content.strip(), filename
        return None, None

    # -- framework detection ----------------------------------------------

    def _detect_framework(self, files: List[Path]) -> Optional[str]:
        """Detect primary framework from actual imports.

        Python indicators only checked in .py files, JS/TS indicators
        only in .js/.ts/.jsx/.tsx. All line-start anchored to avoid
        matching string literals in formatters or templates.
        """
        py_indicators = {
            "fastapi": [r"^from fastapi\b", r"^import fastapi\b"],
            "django-rest-framework": [r"^from rest_framework\b"],
            "django": [r"^from django\b", r"^import django\b"],
            "flask": [r"^from flask\b", r"^import flask\b"],
        }
        js_indicators = {
            "express": [r"^const\s+\w+\s*=\s*require\("],
            "nextjs": [r"^import\s+.*from\s+.next/"],
            "nestjs": [r"^import\s+.*from\s+.@nestjs/"],
        }
        py_exts = {".py"}
        js_exts = {".js", ".jsx", ".ts", ".tsx"}

        scores: Counter = Counter()
        for file_path in files:
            content = self._safe_read_file(file_path)
            if not content:
                continue
            ext = file_path.suffix.lower()
            if ext in py_exts:
                active = py_indicators
            elif ext in js_exts:
                active = js_indicators
            else:
                continue
            for framework, patterns in active.items():
                for pattern in patterns:
                    if re.search(pattern, content, re.MULTILINE):
                        scores[framework] += 1

        if not scores:
            return None
        top = scores.most_common(1)[0][0]
        if top == "django-rest-framework":
            return "django + DRF"
        return top

    # -- pattern extractors -----------------------------------------------

    def _extract_auth_patterns(
        self, files: List[Path], repo_path: Path, framework: Optional[str] = None
    ) -> AuthPattern:
        """Detect auth middleware, decorators, and ownership checks.

        Uses line-start anchored patterns to avoid matching string
        literals in formatters or templates.
        """
        pattern = AuthPattern()

        for file_path in files:
            if file_path.suffix != ".py":
                continue
            content = self._safe_read_file(file_path)
            if not content:
                continue

            # Only match real code patterns -- check function definitions
            # and imports, not arbitrary string occurrences
            if re.search(r"^def require_auth\b", content, re.MULTILINE):
                pattern.middleware_used.append("require_auth")
            if re.search(r"^def public_auth\b", content, re.MULTILINE):
                pattern.middleware_used.append("public_auth")
            if "Depends(" in content and re.search(r"^from fastapi", content, re.MULTILINE):
                # only count Depends if this file actually imports from fastapi
                deps = re.findall(r"Depends\((\w+)\)", content)
                for dep in deps:
                    if "auth" in dep.lower():
                        pattern.auth_decorators.append(f"Depends({dep})")

            if re.search(r"^from starlette.*AuthenticationMiddleware", content, re.MULTILINE):
                pattern.middleware_used.append("AuthenticationMiddleware")
            if re.search(r"^class AuthContext\b", content, re.MULTILINE):
                pattern.auth_context_type = "AuthContext"

            # Flask -- only if flask is actually imported
            if re.search(r"^from flask", content, re.MULTILINE):
                if "login_required" in content:
                    pattern.auth_decorators.append("@login_required")
                if "flask_login" in content:
                    pattern.middleware_used.append("flask_login")

            # Django -- only if django is actually imported
            if re.search(r"^from django", content, re.MULTILINE):
                if "@login_required" in content:
                    pattern.auth_decorators.append("@login_required")
                if "request.user" in content:
                    pattern.auth_context_type = "request.user"

            # Ownership
            if re.search(r"^def verify_ownership\b", content, re.MULTILINE):
                pattern.ownership_checks.append("verify_ownership")

        pattern.middleware_used = list(set(pattern.middleware_used))
        pattern.auth_decorators = list(set(pattern.auth_decorators))
        pattern.ownership_checks = list(set(pattern.ownership_checks))
        return pattern

    def _extract_middleware_patterns(
        self, files: List[Path], framework: Optional[str]
    ) -> List[str]:
        patterns: List[str] = []

        for file_path in files:
            content = self._safe_read_file(file_path)
            if not content:
                continue

            # Real middleware class definitions
            for match in re.finditer(r"^class\s+(\w*Middleware\w*)", content, re.MULTILINE):
                patterns.append(match.group(1))
            if "app.add_middleware" in content:
                patterns.append("app.add_middleware()")
            if "app.use(" in content:
                patterns.append("app.use(middleware)")

        return list(set(patterns))

    def _extract_service_patterns(self, files: List[Path], repo_path: Path) -> ServicePattern:
        pattern = ServicePattern()

        deps_file = repo_path / "dependencies.py"
        if deps_file.exists():
            pattern.dependencies_file = "dependencies.py"
            content = self._safe_read_file(deps_file)
            if content:
                singletons = re.findall(r"^(\w+)\s*=\s*(\w+)\(\)", content, re.MULTILINE)
                for var_name, class_name in singletons:
                    pattern.singleton_services.append(f"{var_name} = {class_name}()")
                pattern.injection_pattern = "Singleton in dependencies.py"

        services_dir = repo_path / "services"
        if services_dir.exists():
            for service_file in services_dir.glob("*.py"):
                if service_file.name.startswith("_"):
                    continue
                content = self._safe_read_file(service_file)
                if content:
                    classes = re.findall(r"^class\s+(\w+)", content, re.MULTILINE)
                    pattern.service_base_classes.extend(classes)

        return pattern

    def _extract_database_patterns(self, files: List[Path], repo_path: Path) -> DatabasePattern:
        pattern = DatabasePattern()

        for file_path in files:
            content = self._safe_read_file(file_path)
            if not content:
                continue

            # SQL files -- most reliable source of DB patterns
            if file_path.suffix == ".sql":
                if "gen_random_uuid()" in content:
                    pattern.id_type = "UUID (gen_random_uuid())"
                elif "SERIAL" in content:
                    pattern.id_type = "SERIAL"
                if "TIMESTAMPTZ" in content:
                    pattern.timestamp_type = "TIMESTAMPTZ"
                elif "TIMESTAMP" in content:
                    pattern.timestamp_type = "TIMESTAMP"
                if "ENABLE ROW LEVEL SECURITY" in content:
                    pattern.has_rls = True
                if "ON DELETE CASCADE" in content:
                    pattern.cascade_deletes = True
                continue

            if file_path.suffix != ".py":
                continue

            # ORM detection -- line-start anchored to avoid matching string literals
            if re.search(r"^from supabase\b|^import supabase\b", content, re.MULTILINE):
                pattern.orm_used = "Supabase"
            if re.search(r"^from django\.db import models", content, re.MULTILINE):
                pattern.orm_used = "Django ORM"
                if "models.UUIDField" in content:
                    pattern.id_type = "UUID (Django UUIDField)"
                if "on_delete=models.CASCADE" in content:
                    pattern.cascade_deletes = True
            if re.search(r"^from sqlalchemy\b", content, re.MULTILINE):
                pattern.orm_used = "SQLAlchemy"
                if "create_engine(" in content:
                    pattern.connection_pattern = "SQLAlchemy: create_engine()"
            if file_path.suffix in (".js", ".ts", ".tsx") and re.search(r"^import\b.*@prisma/client", content, re.MULTILINE):
                pattern.orm_used = "Prisma"

        return pattern

    def _extract_error_patterns(self, files: List[Path]) -> ErrorPattern:
        pattern = ErrorPattern()

        for file_path in files:
            if file_path.suffix != ".py":
                continue
            content = self._safe_read_file(file_path)
            if not content:
                continue

            # Only count HTTPException if it's actually imported
            if re.search(r"^from.*import.*HTTPException", content, re.MULTILINE):
                pattern.http_exception_usage = True
            if "logger.error" in content and "except" in content:
                pattern.logging_on_error = True

            # Custom exception classes -- must inherit from Exception/Error,
            # exclude dataclass-style Pattern/Model classes
            for match in re.finditer(
                r"^class\s+(\w+(?:Error|Exception))\s*\(", content, re.MULTILINE
            ):
                name = match.group(1)
                # Skip our own model dataclasses and test helpers
                if name.endswith("Pattern") or name.startswith("Test"):
                    continue
                pattern.exception_classes.append(name)

        pattern.exception_classes = list(set(pattern.exception_classes))
        return pattern

    def _extract_logging_patterns(self, files: List[Path]) -> LoggingPattern:
        pattern = LoggingPattern()
        levels: set = set()

        for file_path in files:
            if file_path.suffix != ".py":
                continue
            content = self._safe_read_file(file_path)
            if not content:
                continue

            if re.search(r"^.*logging\.getLogger", content, re.MULTILINE):
                pattern.logger_import = "logging.getLogger(__name__)"
            elif re.search(r"^import logging\b", content, re.MULTILINE) and not pattern.logger_import:
                pattern.logger_import = "import logging"
            if re.search(r"^import structlog\b|^from structlog\b", content, re.MULTILINE):
                pattern.structured_logging = True
                pattern.logger_import = "structlog"

            for level in ("debug", "info", "warning", "error", "critical"):
                if f"logger.{level}" in content:
                    levels.add(level)

        pattern.log_levels_used = list(levels)
        return pattern

    def _extract_naming_conventions(self, files: List[Path]) -> NamingConventions:
        conventions = NamingConventions()
        func_styles: Counter = Counter()
        class_styles: Counter = Counter()

        for file_path in files:
            if file_path.suffix != ".py":
                continue
            content = self._safe_read_file(file_path)
            if not content:
                continue

            for func in re.findall(r"^def\s+(\w+)\s*\(", content, re.MULTILINE):
                if func.startswith("_"):
                    continue
                if "_" in func:
                    func_styles["snake_case"] += 1
                elif func[0].islower() and any(c.isupper() for c in func):
                    func_styles["camelCase"] += 1

            for cls in re.findall(r"^class\s+(\w+)", content, re.MULTILINE):
                if cls[0].isupper() and "_" not in cls:
                    class_styles["PascalCase"] += 1

        py_files = [f for f in files if f.suffix == ".py"]
        snake_files = sum(1 for f in py_files if "_" in f.stem and f.stem.islower())
        if py_files and snake_files > len(py_files) * 0.5:
            conventions.file_style = "snake_case"

        if func_styles:
            conventions.function_style = func_styles.most_common(1)[0][0]
        if class_styles:
            conventions.class_style = class_styles.most_common(1)[0][0]
        conventions.constant_style = "UPPER_SNAKE_CASE"

        return conventions

    def _extract_common_imports(self, files: List[Path]) -> List[str]:
        """Find most frequent import statements.

        Only matches complete single-line imports to avoid truncating
        multi-line imports like `from x import (a, b, c)`.
        """
        counter: Counter = Counter()

        for file_path in files:
            if file_path.suffix != ".py":
                continue
            content = self._safe_read_file(file_path)
            if not content:
                continue

            # Only match single-line imports (no opening paren at end)
            for imp in re.findall(
                r"^((?:from\s+[\w.]+\s+)?import\s+[\w., ]+)$", content, re.MULTILINE
            ):
                imp = imp.strip()
                # Skip multi-line (has trailing paren), comments, relative imports
                if imp.endswith("(") or imp.startswith("#") or "from ." in imp:
                    continue
                counter[imp] += 1

        return [imp for imp, count in counter.most_common(20) if count >= 2]

    def _extract_api_patterns(self, files: List[Path], repo_path: Path) -> tuple:
        api_versioning = None
        router_pattern = None

        for candidate in [repo_path / "config" / "api.py", repo_path / "config.py"]:
            if candidate.exists():
                content = self._safe_read_file(candidate)
                if content and ("API_PREFIX" in content or "API_VERSION" in content):
                    api_versioning = "/api/v1 (from config)"
                    break

        routes_dir = repo_path / "routes"
        if routes_dir.exists():
            for route_file in routes_dir.glob("*.py"):
                content = self._safe_read_file(route_file)
                if content and "APIRouter(" in content:
                    match = re.search(r"APIRouter\(prefix=[\"']([^\"']+)[\"']", content)
                    if match:
                        router_pattern = f'APIRouter(prefix="{match.group(1)}", tags=[...])'
                        break

        return api_versioning, router_pattern

    def _extract_test_patterns(
        self, app_files: List[Path], test_files: List[Path], repo_path: Path
    ) -> TestPattern:
        """Detect test framework and conventions from test files specifically."""
        pattern = TestPattern()
        pattern.has_conftest = bool(list(repo_path.rglob("conftest.py")))

        # Check test files for framework and convention signals
        all_files = app_files + test_files
        for file_path in all_files:
            content = self._safe_read_file(file_path)
            if not content:
                continue

            if "import pytest" in content or "@pytest" in content:
                pattern.framework = "pytest"
                if "@pytest.fixture" in content:
                    pattern.fixture_style = "pytest fixtures"
            elif "from unittest" in content and not pattern.framework:
                pattern.framework = "unittest"
                if "def setUp(" in content:
                    pattern.fixture_style = "setUp/tearDown"

            if "from unittest.mock import" in content or "@patch(" in content:
                pattern.mock_library = "unittest.mock"
            elif "pytest_mock" in content or "mocker" in content:
                pattern.mock_library = "pytest-mock"

            if "factory_boy" in content or "from faker import" in content:
                pattern.has_factories = True

        if (repo_path / ".coveragerc").exists() or (repo_path / "pyproject.toml").exists():
            pattern.coverage_config = True

        return pattern

    def _extract_config_patterns(self, files: List[Path], repo_path: Path) -> ConfigPattern:
        pattern = ConfigPattern()

        for file_path in files:
            content = self._safe_read_file(file_path)
            if not content:
                continue

            if re.search(r"^from dotenv import|^load_dotenv\b", content, re.MULTILINE):
                pattern.env_loading = "python-dotenv"
            elif re.search(r"^from decouple import", content, re.MULTILINE):
                pattern.env_loading = "python-decouple"

            if "BaseSettings" in content and re.search(r"^from pydantic", content, re.MULTILINE):
                pattern.settings_pattern = "Pydantic Settings"
                pattern.config_validation = True

            if re.search(r"^.*os\.getenv\(|^.*os\.environ", content, re.MULTILINE):
                pattern.secrets_handling = "Environment variables"

        if (repo_path / "settings.py").exists():
            pattern.settings_pattern = "Single settings file"
        elif (repo_path / "settings").is_dir():
            pattern.settings_pattern = "Split settings (by environment)"
        elif (repo_path / "config").is_dir() and not pattern.settings_pattern:
            pattern.settings_pattern = "Config directory"

        return pattern

    # -- main entry point -------------------------------------------------

    def extract(
        self,
        repo_path: str,
        exclude_dirs: Optional[list] = None,
        exclude_rules_files: Optional[list] = None,
    ) -> Optional[CodebaseDNA]:
        """Extract complete DNA profile from a codebase.

        Args:
            repo_path: Path to the repository root.
            exclude_dirs: Extra directories to skip during file discovery.
            exclude_rules_files: Config filenames to skip when reading team
                rules (prevents inception when generating CLAUDE.md etc.).
        """
        start = time.time()
        path = Path(repo_path)

        if not path.exists() or not path.is_dir():
            logger.error("Invalid repo path: %s", path)
            return None

        # merge user excludes with defaults + .gitignore dirs
        skip = set(self.SKIP_DIRS)
        if exclude_dirs:
            skip.update(exclude_dirs)
        skip.update(self._read_ignore_dirs(path))
        self._active_skip_dirs = skip

        # show user-added skips at info level so --verbose surfaces them
        extra_skips = skip - self.SKIP_DIRS
        if extra_skips:
            logger.info("Extra dirs excluded: %s", sorted(extra_skips))

        self._reset_cache()
        repo_name = path.name
        logger.info("Extracting DNA from %s", repo_name)

        app_files, test_files = self._discover_files(path)
        total = len(app_files) + len(test_files)
        logger.info("Found %d code files (%d app, %d test)", total, len(app_files), len(test_files))

        if not app_files and not test_files:
            logger.warning("No code files found in %s", path)
            return None

        # Framework detection on app code only
        framework = self._detect_framework(app_files)
        logger.info("Detected framework: %s", framework)

        # Language distribution counts ALL files
        lang_dist: Counter = Counter()
        for f in app_files + test_files:
            lang = self._detect_language(str(f))
            if lang != "unknown":
                lang_dist[lang] += 1

        team_rules, team_rules_source = self._extract_team_rules(path, exclude_rules_files)
        api_versioning, router_pattern = self._extract_api_patterns(app_files, path)

        # Pattern extraction on APP CODE ONLY (avoids test fixture noise)
        dna = CodebaseDNA(
            repo_name=repo_name,
            detected_framework=framework,
            language_distribution=dict(lang_dist),
            auth_patterns=self._extract_auth_patterns(app_files, path, framework),
            service_patterns=self._extract_service_patterns(app_files, path),
            database_patterns=self._extract_database_patterns(app_files, path),
            error_patterns=self._extract_error_patterns(app_files),
            logging_patterns=self._extract_logging_patterns(app_files),
            naming_conventions=self._extract_naming_conventions(app_files),
            test_patterns=self._extract_test_patterns(app_files, test_files, path),
            config_patterns=self._extract_config_patterns(app_files, path),
            middleware_patterns=self._extract_middleware_patterns(app_files, framework),
            common_imports=self._extract_common_imports(app_files),
            skip_directories=list(self._active_skip_dirs),
            api_versioning=api_versioning,
            router_pattern=router_pattern,
            team_rules=team_rules,
            team_rules_source=team_rules_source,
        )

        # Enrich with style analysis (AST-based, more precise than regex)
        self._enrich_with_style(dna, str(path))

        # Enrich with dependency graph data
        self._enrich_with_deps(dna, str(path))

        elapsed = time.time() - start
        logger.info(
            "DNA extraction complete: %.2fs, %d files read, %d skipped",
            elapsed, self._stats["files_read"], self._stats["files_skipped"],
        )
        return dna

    def _enrich_with_style(self, dna: CodebaseDNA, repo_path: str) -> None:
        """Run style analyzer and merge results into DNA."""
        try:
            from saar.style_analyzer import StyleAnalyzer
            extra = self._active_skip_dirs - self.SKIP_DIRS
            style = StyleAnalyzer().analyze(repo_path, extra_skip_dirs=extra or None)
            summary = style.get("summary", {})
            dna.async_adoption_pct = summary.get("async_pct", 0.0)
            dna.type_hint_pct = summary.get("typed_pct", 0.0)
            dna.total_functions = summary.get("total_functions", 0)
            dna.total_classes = summary.get("total_classes", 0)
            logger.info(
                "Style: %d functions, %d classes, %.0f%% async, %.0f%% typed",
                dna.total_functions, dna.total_classes,
                dna.async_adoption_pct, dna.type_hint_pct,
            )
        except Exception as e:
            logger.warning("Style analysis failed: %s", e)

    def _enrich_with_deps(self, dna: CodebaseDNA, repo_path: str) -> None:
        """Run dependency analyzer and merge results into DNA."""
        try:
            from saar.dependency_analyzer import DependencyAnalyzer
            extra = self._active_skip_dirs - self.SKIP_DIRS
            graph = DependencyAnalyzer().build_graph(repo_path, extra_skip_dirs=extra or None)
            dna.total_dependencies = graph.get("total_dependencies", 0)
            dna.circular_dependencies = graph.get("circular_dependencies", [])
            metrics = graph.get("metrics", {})
            dna.critical_files = metrics.get("most_critical_files", [])
            logger.info(
                "Deps: %d edges, %d cycles, %d critical files",
                dna.total_dependencies,
                len(dna.circular_dependencies),
                len(dna.critical_files),
            )
        except Exception as e:
            logger.warning("Dependency analysis failed: %s", e)
