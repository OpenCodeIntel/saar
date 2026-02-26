"""Core DNA extraction engine.

Analyzes a codebase using tree-sitter AST parsing and pattern
matching to extract architectural patterns, conventions, and
constraints. This is the heart of Saar.

File is >200 lines because all extraction methods form a single
cohesive pipeline. Candidate for splitting into per-category
analyzers in a future refactor.
"""
import logging
import re
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

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


class DNAExtractor:
    """Extracts architectural DNA from a codebase.

    Zero external dependencies beyond tree-sitter. Runs locally,
    reads files from disk, returns a CodebaseDNA dataclass.
    """

    SKIP_DIRS = {
        "node_modules", ".git", "__pycache__", "venv", "env", "dist",
        "build", ".next", "coverage", ".venv", "site-packages",
    }
    MAX_FILE_SIZE = 1024 * 1024  # 1MB
    MAX_FILES = 5000

    # Team rules files in priority order (first found wins)
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

    # -- file I/O ---------------------------------------------------------

    def _reset_cache(self) -> None:
        """Clear file cache between extractions."""
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

            # binary content check (null bytes)
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

    def _discover_files(self, repo_path: Path) -> List[Path]:
        """Find all code files, skipping irrelevant directories."""
        files: List[Path] = []
        extensions = {".py", ".js", ".jsx", ".ts", ".tsx", ".sql"}

        try:
            for item in repo_path.rglob("*"):
                if item.is_symlink():
                    continue
                if item.is_file() and item.suffix in extensions:
                    if not any(skip in item.parts for skip in self.SKIP_DIRS):
                        files.append(item)
                        if len(files) >= self.MAX_FILES:
                            logger.warning("Hit max file limit (%d)", self.MAX_FILES)
                            break
        except Exception as e:
            logger.error("Error discovering files: %s", e)

        return files

    def _detect_language(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        return {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
        }.get(ext, "unknown")

    # -- team rules -------------------------------------------------------

    def _extract_team_rules(self, repo_path: Path) -> tuple[Optional[str], Optional[str]]:
        """Find and read team convention files (CLAUDE.md, .cursorrules, etc.)."""
        for filename in self.RULES_FILES:
            rules_path = repo_path / filename
            if rules_path.exists() and rules_path.is_file():
                content = self._safe_read_file(rules_path)
                if content:
                    logger.info("Found team rules in %s", filename)
                    return content.strip(), filename
        return None, None

    # -- framework detection ----------------------------------------------

    def _detect_framework(self, files: List[Path]) -> Optional[str]:
        """Detect the primary framework by counting indicator strings."""
        indicators = {
            "fastapi": ["from fastapi", "FastAPI()", "APIRouter"],
            "django-rest-framework": ["from rest_framework", "APIView", "ViewSet"],
            "django": ["from django", "django.conf", "INSTALLED_APPS"],
            "flask": ["from flask", "Flask(__name__)", "@app.route"],
            "express": ['require("express")', "express()", "express.Router"],
            "nextjs": ["getServerSideProps", "getStaticProps", "next/router"],
            "nestjs": ["@Module(", "@Injectable(", "@Controller("],
        }

        scores: Counter = Counter()
        for file_path in files:
            content = self._safe_read_file(file_path)
            if not content:
                continue
            for framework, keywords in indicators.items():
                for kw in keywords:
                    if kw in content:
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
        """Detect auth middleware, decorators, and ownership checks."""
        pattern = AuthPattern()

        for file_path in files:
            if file_path.suffix != ".py":
                continue
            content = self._safe_read_file(file_path)
            if not content:
                continue

            # FastAPI / Starlette
            if "require_auth" in content:
                pattern.middleware_used.append("require_auth")
            if "public_auth" in content:
                pattern.middleware_used.append("public_auth")
            if "Depends(" in content and "auth" in content.lower():
                pattern.auth_decorators.append("Depends(require_auth)")
            if "AuthenticationMiddleware" in content:
                pattern.middleware_used.append("AuthenticationMiddleware")
            if "AuthCredentials" in content:
                pattern.auth_context_type = "AuthCredentials"

            # Flask
            if "login_required" in content:
                pattern.auth_decorators.append("@login_required")
            if "flask_login" in content:
                pattern.middleware_used.append("flask_login")

            # Django
            if "@login_required" in content:
                pattern.auth_decorators.append("@login_required")
            if "permission_required" in content:
                pattern.auth_decorators.append("@permission_required")
            if "request.user" in content:
                pattern.auth_context_type = "request.user"

            # Ownership
            if "verify_ownership" in content:
                pattern.ownership_checks.append("verify_ownership")
            if "AuthContext" in content:
                pattern.auth_context_type = "AuthContext"

        pattern.middleware_used = list(set(pattern.middleware_used))
        pattern.auth_decorators = list(set(pattern.auth_decorators))
        pattern.ownership_checks = list(set(pattern.ownership_checks))
        return pattern

    def _extract_middleware_patterns(
        self, files: List[Path], framework: Optional[str]
    ) -> List[str]:
        """Detect middleware registration patterns."""
        patterns: List[str] = []

        for file_path in files:
            content = self._safe_read_file(file_path)
            if not content:
                continue

            if "class" in content and "Middleware" in content:
                middlewares = re.findall(r"class\s+(\w*Middleware\w*)", content)
                patterns.extend(middlewares)
            if "app.add_middleware" in content:
                patterns.append("app.add_middleware()")
            if "Depends(" in content:
                deps = re.findall(r"Depends\((\w+)\)", content)
                for dep in deps:
                    patterns.append(f"Depends({dep})")
            if "app.use(" in content:
                patterns.append("app.use(middleware)")
            if "permission_classes" in content:
                patterns.append("DRF permission_classes")

        return list(set(patterns))

    def _extract_service_patterns(self, files: List[Path], repo_path: Path) -> ServicePattern:
        """Detect service layer structure and DI patterns."""
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
        """Detect ORM, ID types, timestamps, RLS, and cascade behaviour."""
        pattern = DatabasePattern()

        for file_path in files:
            content = self._safe_read_file(file_path)
            if not content:
                continue

            # ORM detection
            if "supabase" in content.lower() and not pattern.orm_used:
                pattern.orm_used = "Supabase"
            if "from django.db import models" in content or "models.Model" in content:
                pattern.orm_used = "Django ORM"
            if "from sqlalchemy" in content:
                pattern.orm_used = "SQLAlchemy"
            if "prisma" in content.lower() or "@prisma/client" in content:
                pattern.orm_used = "Prisma"

            # SQL files give the most precise info
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

            # Python ORM field types
            if file_path.suffix == ".py":
                if "models.UUIDField" in content:
                    pattern.id_type = "UUID (Django UUIDField)"
                if "on_delete=models.CASCADE" in content:
                    pattern.cascade_deletes = True
                if "create_engine(" in content:
                    pattern.connection_pattern = "SQLAlchemy: create_engine()"

        return pattern

    def _extract_error_patterns(self, files: List[Path]) -> ErrorPattern:
        """Detect exception classes, HTTP errors, and logging-on-error."""
        pattern = ErrorPattern()

        for file_path in files:
            if file_path.suffix != ".py":
                continue
            content = self._safe_read_file(file_path)
            if not content:
                continue

            if "HTTPException" in content:
                pattern.http_exception_usage = True
            if "logger.error" in content and "except" in content:
                pattern.logging_on_error = True

            custom = re.findall(r"class\s+(\w*(?:Error|Exception)\w*)", content)
            pattern.exception_classes.extend(custom)

        pattern.exception_classes = list(set(pattern.exception_classes))
        return pattern

    def _extract_logging_patterns(self, files: List[Path]) -> LoggingPattern:
        """Detect logger setup, levels, and structured logging."""
        pattern = LoggingPattern()
        levels: set = set()

        for file_path in files:
            if file_path.suffix != ".py":
                continue
            content = self._safe_read_file(file_path)
            if not content:
                continue

            if "logging.getLogger" in content:
                pattern.logger_import = "logging.getLogger(__name__)"
            elif "import logging" in content and not pattern.logger_import:
                pattern.logger_import = "import logging"
            if "structlog" in content:
                pattern.structured_logging = True
                pattern.logger_import = "structlog"

            for level in ("debug", "info", "warning", "error", "critical"):
                if f"logger.{level}" in content or f"logging.{level}" in content:
                    levels.add(level)

            if "metrics.increment" in content or "metrics.gauge" in content:
                pattern.metrics_tracking = True

        pattern.log_levels_used = list(levels)
        return pattern

    def _extract_naming_conventions(self, files: List[Path]) -> NamingConventions:
        """Detect dominant naming styles for functions, classes, files."""
        conventions = NamingConventions()
        func_styles: Counter = Counter()
        class_styles: Counter = Counter()

        for file_path in files:
            if file_path.suffix != ".py":
                continue
            content = self._safe_read_file(file_path)
            if not content:
                continue

            for func in re.findall(r"def\s+(\w+)\s*\(", content):
                if func.startswith("_"):
                    continue
                if "_" in func:
                    func_styles["snake_case"] += 1
                elif func[0].islower() and any(c.isupper() for c in func):
                    func_styles["camelCase"] += 1

            for cls in re.findall(r"class\s+(\w+)", content):
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
        """Find the most frequently used import statements."""
        counter: Counter = Counter()

        for file_path in files:
            if file_path.suffix != ".py":
                continue
            content = self._safe_read_file(file_path)
            if not content:
                continue

            for imp in re.findall(r"^(?:from\s+[\w.]+\s+)?import\s+.+$", content, re.MULTILINE):
                imp = imp.strip()
                if imp and not imp.startswith("#"):
                    counter[imp] += 1

        return [imp for imp, count in counter.most_common(20) if count >= 2]

    def _extract_api_patterns(self, files: List[Path], repo_path: Path) -> tuple:
        """Detect API versioning and router patterns."""
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

    def _extract_test_patterns(self, files: List[Path], repo_path: Path) -> TestPattern:
        """Detect test framework, fixtures, mocking, and coverage config."""
        pattern = TestPattern()
        pattern.has_conftest = bool(list(repo_path.rglob("conftest.py")))

        for file_path in files:
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
            elif "from django.test" in content:
                pattern.framework = "django.test"

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
        """Detect env loading, settings structure, and secrets handling."""
        pattern = ConfigPattern()

        for file_path in files:
            content = self._safe_read_file(file_path)
            if not content:
                continue

            if "load_dotenv" in content or "from dotenv import" in content:
                pattern.env_loading = "python-dotenv"
            elif "from decouple import" in content:
                pattern.env_loading = "python-decouple"

            if "BaseSettings" in content and "pydantic" in content:
                pattern.settings_pattern = "Pydantic Settings"
                pattern.config_validation = True
            elif "dynaconf" in content:
                pattern.settings_pattern = "Dynaconf"
                pattern.config_validation = True

            if "os.getenv(" in content or "os.environ" in content:
                pattern.secrets_handling = "Environment variables"

        if (repo_path / "settings.py").exists():
            pattern.settings_pattern = "Single settings file"
        elif (repo_path / "settings").is_dir():
            pattern.settings_pattern = "Split settings (by environment)"
        elif (repo_path / "config").is_dir() and not pattern.settings_pattern:
            pattern.settings_pattern = "Config directory"

        return pattern

    # -- main entry point -------------------------------------------------

    def extract(self, repo_path: str) -> Optional[CodebaseDNA]:
        """Extract complete DNA profile from a codebase.

        Args:
            repo_path: Path to the repository root.

        Returns:
            CodebaseDNA dataclass, or None if extraction fails.
        """
        start = time.time()
        path = Path(repo_path)

        if not path.exists() or not path.is_dir():
            logger.error("Invalid repo path: %s", path)
            return None

        self._reset_cache()
        repo_name = path.name
        logger.info("Extracting DNA from %s", repo_name)

        files = self._discover_files(path)
        logger.info("Found %d code files", len(files))

        if not files:
            logger.warning("No code files found in %s", path)
            return None

        framework = self._detect_framework(files)
        logger.info("Detected framework: %s", framework)

        lang_dist: Counter = Counter()
        for f in files:
            lang = self._detect_language(str(f))
            if lang != "unknown":
                lang_dist[lang] += 1

        team_rules, team_rules_source = self._extract_team_rules(path)
        api_versioning, router_pattern = self._extract_api_patterns(files, path)

        dna = CodebaseDNA(
            repo_name=repo_name,
            detected_framework=framework,
            language_distribution=dict(lang_dist),
            auth_patterns=self._extract_auth_patterns(files, path, framework),
            service_patterns=self._extract_service_patterns(files, path),
            database_patterns=self._extract_database_patterns(files, path),
            error_patterns=self._extract_error_patterns(files),
            logging_patterns=self._extract_logging_patterns(files),
            naming_conventions=self._extract_naming_conventions(files),
            test_patterns=self._extract_test_patterns(files, path),
            config_patterns=self._extract_config_patterns(files, path),
            middleware_patterns=self._extract_middleware_patterns(files, framework),
            common_imports=self._extract_common_imports(files),
            skip_directories=list(self.SKIP_DIRS),
            api_versioning=api_versioning,
            router_pattern=router_pattern,
            team_rules=team_rules,
            team_rules_source=team_rules_source,
        )

        elapsed = time.time() - start
        logger.info(
            "DNA extraction complete: %.2fs, %d files read, %d skipped",
            elapsed,
            self._stats["files_read"],
            self._stats["files_skipped"],
        )
        return dna
