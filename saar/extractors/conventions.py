"""Conventions extractors: naming, imports, API patterns, test patterns."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from saar.models import NamingConventions, TestPattern

ReadFile = Callable[[Path], Optional[str]]


def extract_naming_conventions(files: List[Path], read_file: ReadFile) -> NamingConventions:
    """Detect function, class, and file naming styles from source files."""
    conventions = NamingConventions()
    func_styles: Counter = Counter()
    class_styles: Counter = Counter()
    file_styles: Counter = Counter()

    for file_path in files:
        content = read_file(file_path)
        if not content:
            continue
        if file_path.suffix == ".py":
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
            if "_" in file_path.stem and file_path.stem.islower():
                file_styles["snake_case"] += 1
        elif file_path.suffix in (".js", ".jsx", ".ts", ".tsx"):
            for func in re.findall(r"(?:^|\s)(?:function|const|let|var)\s+(\w+)\s*(?:=\s*(?:async\s*)?\(|[\(<])", content, re.MULTILINE):
                if not func or func[0].isupper():
                    continue
                if func[0].islower() and any(c.isupper() for c in func):
                    func_styles["camelCase"] += 1
                elif "_" in func:
                    func_styles["snake_case"] += 1
            for cls in re.findall(r"(?:^|\s)(?:class|interface|type)\s+(\w+)", content, re.MULTILINE):
                if cls[0].isupper() and "_" not in cls:
                    class_styles["PascalCase"] += 1
            stem = file_path.stem.replace(".test", "").replace(".spec", "")
            if "-" in stem:
                file_styles["kebab-case"] += 1
            elif stem[0].isupper():
                file_styles["PascalCase"] += 1
            elif any(c.isupper() for c in stem):
                file_styles["camelCase"] += 1

    if func_styles:
        conventions.function_style = func_styles.most_common(1)[0][0]
    if class_styles:
        conventions.class_style = class_styles.most_common(1)[0][0]
    if file_styles:
        conventions.file_style = file_styles.most_common(1)[0][0]
    conventions.constant_style = "UPPER_SNAKE_CASE"
    return conventions


def extract_common_imports(files: List[Path], read_file: ReadFile) -> List[str]:
    """Find the most frequently used import statements (Python only)."""
    counter: Counter = Counter()
    for file_path in files:
        if file_path.suffix != ".py":
            continue
        content = read_file(file_path)
        if not content:
            continue
        for imp in re.findall(r"^((?:from\s+[\w.]+\s+)?import\s+[\w., ]+)$", content, re.MULTILINE):
            imp = imp.strip()
            if imp.endswith("(") or imp.startswith("#") or "from ." in imp:
                continue
            counter[imp] += 1
    return [imp for imp, count in counter.most_common(20) if count >= 2]


def extract_api_patterns(files: List[Path], repo_path: Path, read_file: ReadFile) -> Tuple[Optional[str], Optional[str]]:
    """Detect API versioning and router patterns."""
    api_versioning = None
    router_pattern = None
    for candidate in [repo_path / "config" / "api.py", repo_path / "config.py"]:
        if candidate.exists():
            content = read_file(candidate)
            if content and ("API_PREFIX" in content or "API_VERSION" in content):
                api_versioning = "/api/v1 (from config)"
                break
    routes_dir = repo_path / "routes"
    if routes_dir.exists():
        for route_file in sorted(routes_dir.glob("*.py")):
            content = read_file(route_file)
            if content and "APIRouter(" in content:
                match = re.search(r"APIRouter\(prefix=[\"']([^\"']+)[\"']", content)
                if match:
                    router_pattern = f'APIRouter(prefix="{match.group(1)}", tags=[...])'
                    break
    return api_versioning, router_pattern


def extract_test_patterns(app_files: List[Path], test_files: List[Path], repo_path: Path, read_file: ReadFile) -> TestPattern:
    """Detect test framework and conventions."""
    pattern = TestPattern()
    pattern.has_conftest = bool(list(repo_path.rglob("conftest.py")))
    for file_path in app_files + test_files:
        content = read_file(file_path)
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
