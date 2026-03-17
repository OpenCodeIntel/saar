"""Frontend pattern extractor: package.json analysis and React pattern detection."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Optional

from saar.models import FrontendPattern

ShouldSkip = Callable[[Path, Path], bool]


def extract_frontend_patterns(repo_path: Path, should_skip: ShouldSkip) -> Optional[FrontendPattern]:
    """Detect frontend stack from package.json files. Returns None for pure backend repos."""
    pkg_files = [
        p for p in repo_path.rglob("package.json")
        if not should_skip(p, repo_path) and "node_modules" not in p.parts
    ]
    if not pkg_files:
        return None

    all_deps: dict = {}
    all_dev_deps: dict = {}
    all_scripts: dict = {}
    for pkg_file in pkg_files:
        try:
            data = json.loads(pkg_file.read_text(encoding="utf-8"))
            all_deps.update(data.get("dependencies", {}))
            all_dev_deps.update(data.get("devDependencies", {}))
            all_scripts.update(data.get("scripts", {}))
        except Exception:
            continue

    combined = {**all_deps, **all_dev_deps}
    if not combined:
        return None

    fp = FrontendPattern()

    # package manager (check root + immediate subdirs for lockfiles)
    def _has_lockfile(name: str) -> bool:
        if (repo_path / name).exists():
            return True
        return any(
            (p / name).exists()
            for p in repo_path.iterdir()
            if p.is_dir() and not should_skip(p, repo_path)
        )

    if _has_lockfile("bun.lock") or _has_lockfile("bun.lockb"):
        fp.package_manager = "bun"
    elif _has_lockfile("pnpm-lock.yaml"):
        fp.package_manager = "pnpm"
    elif _has_lockfile("yarn.lock"):
        fp.package_manager = "yarn"
    else:
        fp.package_manager = "npm"

    fp.language = "TypeScript" if ("typescript" in combined or any(k.startswith("@types/") for k in combined)) else "JavaScript"

    # UI framework
    if "next" in combined:
        fp.framework = "Next.js"
    elif "nuxt" in combined or "nuxt3" in combined:
        fp.framework = "Nuxt"
    elif "@sveltejs/kit" in combined or "svelte" in combined:
        fp.framework = "SvelteKit" if "@sveltejs/kit" in combined else "Svelte"
    elif "astro" in combined:
        fp.framework = "Astro"
    elif "@angular/core" in combined:
        fp.framework = "Angular"
    elif "react" in combined or "react-dom" in combined:
        fp.framework = "React"
    elif "vue" in combined:
        fp.framework = "Vue"

    # build tool
    if "vite" in combined or "@vitejs/plugin-react" in combined:
        fp.build_tool = "Vite"
    elif "turbopack" in combined or ("next" in combined and "webpack" not in combined):
        fp.build_tool = "Turbopack"
    elif "webpack" in combined:
        fp.build_tool = "webpack"

    # test framework
    if "vitest" in combined:
        fp.test_framework = "Vitest"
        test_cmd = all_scripts.get("test", "")
        if "vitest" in test_cmd:
            pm = fp.package_manager or "npm"
            fp.test_command = f"{pm} run test"
    elif "jest" in combined or "@jest/core" in combined:
        fp.test_framework = "Jest"
        fp.test_command = "jest"
    elif "@playwright/test" in combined:
        fp.test_framework = "Playwright"
    elif "cypress" in combined:
        fp.test_framework = "Cypress"
    elif "mocha" in combined:
        fp.test_framework = "Mocha"

    # component library
    radix_count = sum(1 for k in combined if k.startswith("@radix-ui/"))
    if radix_count >= 3:
        fp.component_library = "shadcn/ui"
    elif "@mui/material" in combined or "@material-ui/core" in combined:
        fp.component_library = "Material UI"
    elif "@chakra-ui/react" in combined:
        fp.component_library = "Chakra UI"
    elif "antd" in combined:
        fp.component_library = "Ant Design"
    elif "react-bootstrap" in combined:
        fp.component_library = "React Bootstrap"
    elif "@mantine/core" in combined:
        fp.component_library = "Mantine"

    # state management
    if "@tanstack/react-query" in combined or "react-query" in combined:
        fp.state_management = "TanStack Query"
    elif "zustand" in combined:
        fp.state_management = "Zustand"
    elif "@reduxjs/toolkit" in combined or "redux" in combined:
        fp.state_management = "Redux Toolkit" if "@reduxjs/toolkit" in combined else "Redux"
    elif "jotai" in combined:
        fp.state_management = "Jotai"
    elif "valtio" in combined:
        fp.state_management = "Valtio"
    elif "recoil" in combined:
        fp.state_management = "Recoil"

    # styling
    if "tailwindcss" in combined:
        fp.styling = "Tailwind CSS"
    elif "styled-components" in combined:
        fp.styling = "styled-components"
    elif "@emotion/react" in combined or "@emotion/styled" in combined:
        fp.styling = "Emotion"
    elif "sass" in combined or "node-sass" in combined:
        fp.styling = "Sass/SCSS"

    if fp.framework in ("React", "Next.js"):
        _detect_react_patterns(fp, repo_path, should_skip)

    return fp


def _detect_react_patterns(fp: FrontendPattern, repo_path: Path, should_skip: ShouldSkip) -> None:
    """Scan React/TS source files to detect actual usage patterns."""
    all_fe_files = [
        p for p in (
            list(repo_path.rglob("*.tsx")) + [
                p for p in repo_path.rglob("*.ts")
                if not p.name.endswith(".d.ts")
            ]
        )
        if not should_skip(p, repo_path) and "node_modules" not in p.parts
    ]
    if not all_fe_files:
        return

    use_query_count = 0
    fetch_in_effect_count = 0
    cn_usage_count = 0
    hook_files = []
    custom_hook_imports: dict = {}

    for file_path in all_fe_files[:150]:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        if re.search(r"\buseQuery\b|\buseMutation\b|\buseInfiniteQuery\b", content):
            use_query_count += 1
        if re.search(r"useEffect\s*\(", content) and re.search(r"\bfetch\s*\(", content):
            fetch_in_effect_count += 1
        if re.search(r"\bcn\s*\(", content):
            cn_usage_count += 1
        if "hooks" in file_path.parts and file_path.name.startswith("use"):
            hook_files.append(file_path.stem)
        for match in re.finditer(r"import\s+\{([^}]+)\}\s+from\s+['\"].*?hooks/([^'\"]+)['\"]", content):
            for imp in [i.strip() for i in match.group(1).split(",")]:
                if imp.startswith("use"):
                    custom_hook_imports[imp] = custom_hook_imports.get(imp, 0) + 1

    if use_query_count >= 2:
        fp.uses_react_query = True
    if fetch_in_effect_count == 0 and use_query_count >= 2:
        fp.avoids_fetch_in_effect = True
    if cn_usage_count >= 3:
        fp.uses_cn_utility = True
    if hook_files:
        fp.has_custom_hooks = True
        if custom_hook_imports:
            fp.canonical_data_hook = max(custom_hook_imports, key=custom_hook_imports.get)

    for candidate in ["src/types.ts", "src/types/index.ts", "types.ts", "src/types/index.tsx",
                       "frontend/src/types.ts", "frontend/src/types/index.ts"]:
        if (repo_path / candidate).exists():
            fp.shared_types_file = candidate
            break
