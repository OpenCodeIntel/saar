"""Project-level extractors: team rules, verify workflow, structure, config."""
from __future__ import annotations

import json as _json
import logging
import re
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from saar.models import ConfigPattern

logger = logging.getLogger(__name__)
ReadFile = Callable[[Path], Optional[str]]

RULES_FILES = [
    "CLAUDE.md", ".cursorrules", ".codeintel/rules.md",
    "CONVENTIONS.md", ".github/copilot-instructions.md", "CODING_GUIDELINES.md",
]


def extract_team_rules(repo_path: Path, read_file: ReadFile, exclude_files: Optional[list] = None) -> Tuple[Optional[str], Optional[str]]:
    """Find and read team convention files (CLAUDE.md, .cursorrules, etc.)."""
    skip = set(exclude_files or [])
    for filename in RULES_FILES:
        if filename in skip:
            continue
        rules_path = repo_path / filename
        if rules_path.exists() and rules_path.is_file():
            content = read_file(rules_path)
            if content:
                return content.strip(), filename
    return None, None


def extract_config_patterns(files: List[Path], repo_path: Path, read_file: ReadFile) -> ConfigPattern:
    """Detect environment loading and settings patterns."""
    pattern = ConfigPattern()
    for file_path in files:
        content = read_file(file_path)
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


def extract_verify_workflow(repo_path: Path, read_file: ReadFile) -> Optional[str]:
    """Auto-detect how developers verify their changes work."""
    steps: list[str] = []

    # Python / backend
    py_test_cmd = None
    pyproject = repo_path / "pyproject.toml"
    if not pyproject.exists():
        pyproject = repo_path / "backend" / "pyproject.toml"
    if pyproject.exists():
        content = read_file(pyproject)
        if content and "pytest" in content:
            m = re.search(r'testpaths\s*=\s*\[([^\]]+)\]', content)
            if m:
                paths = m.group(1).replace('"', '').replace("'", '').replace(',', '').split()
                py_test_cmd = f"pytest {' '.join(paths)} -v"
            else:
                py_test_cmd = "pytest tests/ -v"
    if not py_test_cmd:
        for cfg in [repo_path / "pytest.ini", repo_path / "backend" / "pytest.ini",
                    repo_path / "setup.cfg", repo_path / "backend" / "setup.cfg"]:
            if cfg.exists():
                content = read_file(cfg)
                if content and ("pytest" in content or "[tool:pytest]" in content):
                    m = re.search(r'testpaths\s*=\s*(.+)', content)
                    py_test_cmd = f"pytest {' '.join(m.group(1).strip().split()[:2])} -v" if m else "pytest tests/ -v"
                    break
    if not py_test_cmd:
        for req in [repo_path / "requirements.txt", repo_path / "backend" / "requirements.txt"]:
            if req.exists():
                content = read_file(req)
                if content and "pytest" in content:
                    py_test_cmd = "pytest tests/ -v"
                    break
    if py_test_cmd:
        steps.append(f"Backend: `{py_test_cmd}`")

    # JS / frontend
    js_steps: list[str] = []
    for candidate in [repo_path / "package.json", repo_path / "frontend" / "package.json",
                       repo_path / "web" / "package.json", repo_path / "app" / "package.json",
                       repo_path / "apps" / "web" / "package.json"]:
        if not candidate.exists():
            continue
        try:
            data = _json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            break
        scripts = data.get("scripts", {})
        parent = candidate.parent
        if (parent / "bun.lock").exists() or (parent / "bun.lockb").exists():
            pm = "bun"
        elif (parent / "pnpm-lock.yaml").exists():
            pm = "pnpm"
        elif (parent / "yarn.lock").exists():
            pm = "yarn"
        else:
            pm = "npm"
        for key in ("typecheck", "type-check", "test", "lint", "build"):
            if key in scripts and scripts[key]:
                cmd = f"{pm} run {key}"
                if cmd not in js_steps:
                    js_steps.append(cmd)
                if len(js_steps) >= 3:
                    break
        break
    if js_steps:
        steps.append(f"Frontend: `{'` then `'.join(js_steps)}`")

    # Makefile
    makefile = repo_path / "Makefile"
    if makefile.exists():
        content = read_file(makefile)
        if content:
            make_targets = [f"make {t}" for t in ("test", "check", "lint", "validate")
                           if re.search(rf"^{t}[:\s]", content, re.MULTILINE)]
            if make_targets and not any("pytest" in s or "bun" in s for s in steps):
                steps.append(f"Run: `{'` + `'.join(make_targets[:2])}`")

    return " | ".join(steps) if steps else None


def extract_project_structure(repo_path: Path, active_skip_dirs: set, should_skip: Callable) -> Optional[str]:
    """Generate annotated directory tree for the project."""
    _KNOWN_ANNOTATIONS = {
        "routes": "API endpoints", "services": "business logic / API clients",
        "middleware": "auth, rate limiting, request processing", "models": "data models / ORM schemas",
        "schemas": "request/response schemas", "config": "configuration, env validation",
        "utils": "shared utilities", "migrations": "database migrations",
        "tests": "test files", "tasks": "background jobs / celery tasks",
        "components": "UI components", "hooks": "custom React hooks",
        "pages": "route-level page components", "contexts": "React context providers",
        "lib": "shared utilities (cn, etc.)", "types": "TypeScript type definitions",
        "styles": "global styles", "assets": "static assets", "test": "frontend tests",
        "docs": "documentation", "scripts": "dev/deploy scripts", "mcp-server": "MCP protocol server",
    }
    _SKIP_STRUCTURE = active_skip_dirs | {
        "public", "static", "media", "__pycache__", ".pytest_cache",
        ".venv", ".git", ".idea", ".vscode", ".saar", ".claude",
    }

    def _count_code_files(d: Path) -> int:
        count = 0
        try:
            for p in d.rglob("*"):
                if p.is_file() and p.suffix in (".py", ".ts", ".tsx", ".js", ".jsx") and not should_skip(p, repo_path):
                    count += 1
        except PermissionError:
            pass
        return count

    def _build_tree(directory: Path, prefix: str = "", depth: int = 0) -> list[str]:
        if depth > 3:
            return []
        lines = []
        try:
            children = sorted([c for c in directory.iterdir() if c.is_dir()], key=lambda p: p.name)
        except PermissionError:
            return []
        visible = [c for c in children
                   if c.name not in _SKIP_STRUCTURE and not c.name.startswith(".")
                   and not any(skip in c.parts for skip in _SKIP_STRUCTURE)
                   and _count_code_files(c) > 0]
        for i, child in enumerate(visible):
            is_last = i == len(visible) - 1
            annotation = _KNOWN_ANNOTATIONS.get(child.name, "")
            lines.append(f"{prefix}{'└── ' if is_last else '├── '}{child.name}/{f'  # {annotation}' if annotation else ''}")
            lines.extend(_build_tree(child, prefix + ("    " if is_last else "│   "), depth + 1))
        return lines

    tree_lines = _build_tree(repo_path)
    if len(tree_lines) < 3:
        return None
    return f"```\n{repo_path.name}/\n" + "\n".join(tree_lines) + "\n```"
