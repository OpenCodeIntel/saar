"""Core DNA extraction engine.

Orchestrates pattern extraction across the codebase.
Logic is split into focused modules under saar/extractors/:
  backend.py     -- framework, auth, db, errors, logging, services
  conventions.py -- naming, imports, api patterns, test patterns
  frontend.py    -- package.json analysis, React pattern detection
  project.py     -- team rules, verify workflow, structure, config
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
    FrontendPattern,
    LoggingPattern,
    NamingConventions,
    ServicePattern,
    TestPattern,
)
from saar.extractors.backend import (
    detect_framework,
    extract_auth_patterns,
    extract_error_patterns,
    extract_logging_patterns,
    extract_service_patterns,
    extract_database_patterns,
    extract_middleware_patterns,
)
from saar.extractors.conventions import (
    extract_naming_conventions,
    extract_common_imports,
    extract_api_patterns,
    extract_test_patterns,
)
from saar.extractors.frontend import extract_frontend_patterns
from saar.extractors.project import (
    extract_team_rules,
    extract_config_patterns,
    extract_verify_workflow,
    extract_project_structure,
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
        # compiled/vendored assets -- never source code (OPE-184)
        "compiled", "bundles", "vendor", "vendors",
        # test/coverage artifacts
        "coverage", ".pytest_cache", "htmlcov", ".nyc_output",
        # cloned repo dirs (the specific OCI case)
        "repos",
        # ide
        ".idea", ".vscode",
        # example/demo apps -- not the primary project (OPE-185)
        # These directories contain demo applications that use different stacks.
        # Scanning them produces false positives (Express in a React Native lib,
        # shadcn/ui in the Next.js framework repo itself, etc.)
        "examples", "example", "demo", "demos", "playground", "playgrounds",
        "starters", "templates", "fixtures", "test-fixtures",
    }

    # file suffixes that are never source code -- skip regardless of directory
    SKIP_FILE_SUFFIXES = {
        ".pyc", ".pyo", ".pyd",          # compiled python
        ".DS_Store", ".Thumbs.db",        # OS junk
        ".min.js", ".min.css",            # minified assets
        ".map",                           # source maps
        ".lock",                          # lockfiles (bun.lock, poetry.lock)
        ".log",                           # log files
    }

    MAX_FILE_SIZE = 1024 * 1024  # 1MB
    MAX_FILES = 25000  # generous limit -- PostHog has 19K, most repos <10K

    RULES_FILES = [
        "CLAUDE.md",
        ".cursorrules",
        ".codeintel/rules.md",
        "CONVENTIONS.md",
        ".github/copilot-instructions.md",
        "CODING_GUIDELINES.md",
    ]

    def __init__(self) -> None:
        try:
            self.parsers = {
                "python": Parser(Language(tspython.language())),
                "javascript": Parser(Language(tsjavascript.language())),
                "typescript": Parser(Language(tsjavascript.language())),
            }
        except TypeError:
            # tree-sitter <0.24 uses Parser().set_language() API
            py_lang = Language(tspython.language())
            js_lang = Language(tsjavascript.language())
            self.parsers = {}
            for name, lang in [("python", py_lang), ("javascript", js_lang), ("typescript", js_lang)]:
                p = Parser()
                p.language = lang
                self.parsers[name] = p
        self._file_cache: Dict[Path, str] = {}
        self._stats = {"files_read": 0, "files_skipped": 0, "read_errors": 0}
        self._active_skip_dirs = set(self.SKIP_DIRS)
        self._file_limit_hit = False  # set True when MAX_FILES cap is reached

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

    def _should_skip(self, file_path: Path, repo_path: Path) -> bool:
        """Check whether a file should be excluded from analysis.

        Handles both simple dir names ('node_modules') and multi-component
        paths ('backend/repos') from gitignore. Simple names are matched
        against individual path parts; multi-component paths are matched
        as a relative prefix of the file's path from the repo root.
        """
        parts = file_path.parts
        try:
            rel = file_path.relative_to(repo_path)
            rel_parts = rel.parts
        except ValueError:
            rel_parts = parts

        for skip in self._active_skip_dirs:
            if "/" in skip or "\\" in skip:
                # multi-component path -- check as prefix of relative path
                skip_parts = tuple(skip.replace("\\", "/").split("/"))
                if rel_parts[:len(skip_parts)] == skip_parts:
                    return True
            else:
                # single component -- check against all parts of absolute path
                if skip in parts:
                    return True
        return False

    def _discover_files(
        self,
        repo_path: Path,
        include_roots: Optional[List[Path]] = None,
    ) -> Tuple[List[Path], List[Path]]:
        """Find code files, split into app files and test files.

        Args:
            repo_path: Root of the repository (used for _should_skip resolution).
            include_roots: When provided, only scan these subdirectories.
                           Used by --include flag for monorepo subset analysis.
                           Each path should be absolute and under repo_path.

        Returns:
            Tuple of (app_files, test_files). Pattern detection runs
            only on app_files to avoid false positives from test
            fixtures and template strings.
        """
        app_files: List[Path] = []
        test_files: List[Path] = []
        extensions = {".py", ".js", ".jsx", ".ts", ".tsx", ".sql"}

        # determine which roots to scan -- subset or full repo
        scan_roots = include_roots if include_roots else [repo_path]

        try:
            for scan_root in scan_roots:
                for item in sorted(scan_root.rglob("*")):
                    if item.is_symlink():
                        continue
                    if item.is_file() and item.suffix in extensions:
                        if self._should_skip(item, repo_path):
                            continue
                        if item.suffix in self.SKIP_FILE_SUFFIXES:
                            continue
                        total = len(app_files) + len(test_files)
                        if total >= self.MAX_FILES:
                            # Store hit count on self so CLI can warn user
                            self._file_limit_hit = True
                            logger.warning("Hit max file limit (%d)", self.MAX_FILES)
                            break
                        if self._is_test_file(item):
                            test_files.append(item)
                        else:
                            app_files.append(item)
        except Exception as e:
            logger.error("Error discovering files: %s", e)

        return app_files, test_files

    def _detect_framework(self, files: List[Path]) -> Optional[str]:
        return detect_framework(files, self._safe_read_file)

    # -- pattern extractors -----------------------------------------------

    def _extract_auth_patterns(self, files: List[Path], repo_path: Path, framework: Optional[str] = None) -> AuthPattern:
        return extract_auth_patterns(files, self._safe_read_file, framework)

    def _extract_middleware_patterns(self, files: List[Path], framework: Optional[str]) -> List[str]:
        return extract_middleware_patterns(files, framework, self._safe_read_file)

    def _extract_service_patterns(self, files: List[Path], repo_path: Path) -> ServicePattern:
        return extract_service_patterns(files, repo_path, self._safe_read_file)

    def _extract_database_patterns(self, files: List[Path], repo_path: Path) -> DatabasePattern:
        return extract_database_patterns(files, repo_path, self._safe_read_file)

    def _extract_error_patterns(self, files: List[Path]) -> ErrorPattern:
        return extract_error_patterns(files, self._safe_read_file)

    def _extract_logging_patterns(self, files: List[Path]) -> LoggingPattern:
        return extract_logging_patterns(files, self._safe_read_file)

    def _extract_naming_conventions(self, files: List[Path]) -> NamingConventions:
        return extract_naming_conventions(files, self._safe_read_file)

    def _extract_common_imports(self, files: List[Path]) -> List[str]:
        return extract_common_imports(files, self._safe_read_file)

    def _extract_api_patterns(self, files: List[Path], repo_path: Path) -> tuple:
        return extract_api_patterns(files, repo_path, self._safe_read_file)

    def _extract_test_patterns(self, app_files: List[Path], test_files: List[Path], repo_path: Path) -> TestPattern:
        return extract_test_patterns(app_files, test_files, repo_path, self._safe_read_file)

    def _extract_frontend_patterns(self, repo_path: Path) -> Optional[FrontendPattern]:
        return extract_frontend_patterns(repo_path, self._should_skip)

    def _detect_react_patterns(self, fp, repo_path: Path) -> None:
        # handled inside extract_frontend_patterns -- kept for compat
        pass

    def _extract_verify_workflow(self, repo_path: Path) -> Optional[str]:
        return extract_verify_workflow(repo_path, self._safe_read_file)

    def _extract_project_structure(self, repo_path: Path) -> Optional[str]:
        return extract_project_structure(repo_path, self._active_skip_dirs, self._should_skip)

    def _extract_config_patterns(self, files: List[Path], repo_path: Path) -> ConfigPattern:
        return extract_config_patterns(files, repo_path, self._safe_read_file)

    def _extract_team_rules(self, repo_path: Path, exclude_files: Optional[list] = None) -> Tuple[Optional[str], Optional[str]]:
        return extract_team_rules(repo_path, self._safe_read_file, exclude_files)

    # -- file type helpers ------------------------------------------------

    def _detect_language(self, file_path: str) -> str:
        """Map file extension to language name."""
        ext = Path(file_path).suffix.lower()
        return {
            ".py": "python", ".js": "javascript", ".jsx": "javascript",
            ".ts": "typescript", ".tsx": "typescript",
        }.get(ext, "unknown")

    def _read_ignore_dirs(self, repo_path: Path) -> set:
        """Parse .gitignore and .saarignore for directory patterns to skip."""
        dirs: set = set()
        for ignore_file in [repo_path / ".gitignore", repo_path / ".saarignore"]:
            if not ignore_file.exists():
                continue
            try:
                for line in ignore_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.endswith("/"):
                        dirs.add(line.rstrip("/"))
                    elif "/" not in line and "*" not in line and "!" not in line:
                        candidate = repo_path / line
                        if candidate.is_dir():
                            dirs.add(line)
            except Exception as e:
                logger.debug("Error reading %s: %s", ignore_file.name, e)
        if dirs:
            logger.debug("Ignore file dirs to skip: %s", dirs)
        return dirs

    def extract(
        self,
        repo_path: str,
        exclude_dirs: Optional[list] = None,
        exclude_rules_files: Optional[list] = None,
        include_paths: Optional[list] = None,
    ) -> Optional[CodebaseDNA]:
        """Extract complete DNA profile from a codebase.

        Args:
            repo_path: Path to the repository root.
            exclude_dirs: Extra directories to skip during file discovery.
            exclude_rules_files: Config filenames to skip when reading team
                rules (prevents inception when generating CLAUDE.md etc.).
            include_paths: Subdirectories to INCLUDE (monorepo subset analysis).
                When provided, ONLY these directories are scanned for source files.
                Team rules (CLAUDE.md etc) are always read from repo_path root.
                Example: ["packages/effect", "packages/schema"]
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

        # resolve include_paths to absolute Path objects (OPE-108)
        include_roots: Optional[list] = None
        if include_paths:
            resolved = []
            for p in include_paths:
                candidate = Path(p) if Path(p).is_absolute() else path / p
                if candidate.is_dir():
                    resolved.append(candidate)
                else:
                    logger.warning("--include path not found: %s (skipped)", candidate)
            if resolved:
                include_roots = resolved
                logger.info("Subset analysis: scanning %d paths: %s",
                            len(resolved), [str(r.relative_to(path)) for r in resolved])

        app_files, test_files = self._discover_files(path, include_roots=include_roots)
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
            frontend_patterns=self._extract_frontend_patterns(path),
            project_structure=self._extract_project_structure(path),
            verify_workflow=self._extract_verify_workflow(path),
        )

        # Enrich with style analysis (AST-based, more precise than regex)
        self._enrich_with_style(dna, str(path))

        # Enrich with dependency graph data
        self._enrich_with_deps(dna, str(path))

        # Extract canonical examples from dependency data (OPE-142)
        self._extract_canonical_examples(dna)

        # Deep extraction -- rules WITH reasoning, not just labels (OPE-96)
        self._run_deep_extraction(dna, app_files)

        elapsed = time.time() - start
        logger.info(
            "DNA extraction complete: %.2fs, %d files read, %d skipped",
            elapsed, self._stats["files_read"], self._stats["files_skipped"],
        )

        # surface file limit warning directly on DNA (OPE-182)
        if self._file_limit_hit:
            total_files = len(app_files) + len(test_files)
            dna.analysis_warnings.append(
                f"Large repo: analysed {total_files:,} files (cap={self.MAX_FILES:,}). "
                "Some files may be missing from critical-files and exception detection. "
                "Use --exclude to focus on specific directories."
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

    def _extract_canonical_examples(self, dna: CodebaseDNA) -> None:
        """Nominate the most-imported file per category as a canonical example.

        The highest-value thing in an AGENTS.md is "For new hooks, follow
        useUserUsage.ts." Static analysis can find this -- it's the file that
        gets imported the most within its category.

        Uses critical_files (fan-in counts) already collected by _enrich_with_deps.
        Groups by file category, picks the top file per category.

        Why fan-in (in-degree)?
            A file imported by many others is the de-facto standard for that
            pattern. It didn't become popular by accident -- it's the one devs
            trust enough to reuse. That's the definition of canonical.
        """
        if not dna.critical_files:
            return

        # Categories: map path patterns to human labels
        # Order matters -- first match wins
        CATEGORIES = [
            ("hooks/",      "hooks",      "For new hooks, follow"),
            ("services/",   "services",   "For new services, follow"),
            ("components/", "components", "For new components, follow"),
            ("pages/",      "pages",      "For new pages, follow"),
            ("routes/",     "routes",     "For new routes, follow"),
            ("middleware/",  "middleware", "For new middleware, follow"),
            ("utils/",      "utils",      "For new utilities, follow"),
            ("tests/",      "tests",      "For new tests, follow"),
            ("test/",       "tests",      "For new tests, follow"),
        ]

        # Group critical files by category, keeping the highest fan-in per category
        seen_categories: dict = {}

        for entry in dna.critical_files:
            file_path = entry.get("file", "") if isinstance(entry, dict) else str(entry)
            dependents = entry.get("dependents", 0) if isinstance(entry, dict) else 0

            if not file_path or dependents < 2:
                # Skip files with fewer than 2 importers -- not canonical enough
                continue

            # Normalise path separators
            normalised = file_path.replace("\\", "/")

            for pattern, category, reason_prefix in CATEGORIES:
                if pattern in normalised:
                    # Keep only the most-imported file per category
                    if category not in seen_categories or dependents > seen_categories[category]["import_count"]:
                        seen_categories[category] = {
                            "category": category,
                            "file": file_path,
                            "import_count": dependents,
                            "reason": f"{reason_prefix} `{file_path}`",
                        }
                    break  # first matching category wins

        # Sort by import count descending so highest-confidence examples appear first
        dna.canonical_examples = sorted(
            seen_categories.values(),
            key=lambda x: x["import_count"],
            reverse=True,
        )

        logger.info("Canonical examples: %d categories found", len(dna.canonical_examples))

    def _run_deep_extraction(self, dna, app_files: List[Path]) -> None:
        """Run deep rule extraction -- patterns WITH reasoning. (OPE-96)

        Stores results as dicts on dna.deep_rules so the formatter
        can render them as actionable rules instead of bare labels.

        Graceful: any failure here must never break saar extract.
        """
        try:
            from saar.deep_extractor import run_deep_extraction
            result = run_deep_extraction(app_files, dna, self._safe_read_file)
            high_confidence = result.all_rules(min_confidence=0.65)
            dna.deep_rules = [
                {
                    "text": r.text,
                    "confidence": r.confidence,
                    "category": r.category,
                    "evidence": r.evidence,
                }
                for r in high_confidence
            ]
            logger.info("Deep extraction: %d rules generated", len(dna.deep_rules))
        except Exception as e:
            logger.warning("Deep extraction failed gracefully: %s", e)
            dna.deep_rules = []
