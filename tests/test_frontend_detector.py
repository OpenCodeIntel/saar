"""Tests for frontend stack detection from package.json.

All tests create minimal package.json fixtures in tmp_path --
no real network calls, no real repos needed.
"""
import json
from pathlib import Path

import pytest

from saar.extractor import DNAExtractor
from saar.models import FrontendPattern


def _write_pkg(tmp_path: Path, deps: dict = None, dev_deps: dict = None,
               scripts: dict = None, lockfile: str = "bun.lock") -> None:
    """Write a package.json + lockfile to tmp_path."""
    pkg = {}
    if deps:
        pkg["dependencies"] = deps
    if dev_deps:
        pkg["devDependencies"] = dev_deps
    if scripts:
        pkg["scripts"] = scripts
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    if lockfile:
        (tmp_path / lockfile).write_text("")
    # need at least one code file so extraction doesn't bail
    (tmp_path / "app.ts").write_text("const x = 1;")


class TestPackageManagerDetection:

    def test_detects_bun(self, tmp_path: Path):
        _write_pkg(tmp_path, {"react": "^18"}, lockfile="bun.lock")
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns is not None
        assert dna.frontend_patterns.package_manager == "bun"

    def test_detects_pnpm(self, tmp_path: Path):
        _write_pkg(tmp_path, {"react": "^18"}, lockfile="pnpm-lock.yaml")
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.package_manager == "pnpm"

    def test_detects_yarn(self, tmp_path: Path):
        _write_pkg(tmp_path, {"react": "^18"}, lockfile="yarn.lock")
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.package_manager == "yarn"

    def test_defaults_to_npm(self, tmp_path: Path):
        _write_pkg(tmp_path, {"react": "^18"}, lockfile=None)
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.package_manager == "npm"


class TestFrameworkDetection:

    def test_detects_nextjs(self, tmp_path: Path):
        _write_pkg(tmp_path, {"next": "^14", "react": "^18"})
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.framework == "Next.js"

    def test_detects_react(self, tmp_path: Path):
        _write_pkg(tmp_path, {"react": "^18", "react-dom": "^18"})
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.framework == "React"

    def test_detects_vue(self, tmp_path: Path):
        _write_pkg(tmp_path, {"vue": "^3"})
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.framework == "Vue"

    def test_detects_svelte(self, tmp_path: Path):
        _write_pkg(tmp_path, {"svelte": "^4"})
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.framework == "Svelte"

    def test_nextjs_takes_priority_over_react(self, tmp_path: Path):
        # Next.js projects always have react too -- Next should win
        _write_pkg(tmp_path, {"next": "^14", "react": "^18", "react-dom": "^18"})
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.framework == "Next.js"

    def test_no_frontend_for_pure_python(self, tmp_path: Path):
        # Pure Python repo -- no package.json
        (tmp_path / "app.py").write_text("def main(): pass")
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns is None


class TestTestFrameworkDetection:

    def test_detects_vitest(self, tmp_path: Path):
        _write_pkg(
            tmp_path,
            {"react": "^18"},
            {"vitest": "^1", "@vitest/coverage-v8": "^1"},
            {"test": "vitest run"},
        )
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.test_framework == "Vitest"

    def test_vitest_test_command_uses_package_manager(self, tmp_path: Path):
        _write_pkg(
            tmp_path,
            {"react": "^18"},
            {"vitest": "^1"},
            {"test": "vitest run"},
            lockfile="bun.lock",
        )
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.test_command == "bun run test"

    def test_detects_jest(self, tmp_path: Path):
        _write_pkg(tmp_path, {"react": "^18"}, {"jest": "^29"})
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.test_framework == "Jest"

    def test_detects_playwright(self, tmp_path: Path):
        _write_pkg(tmp_path, {}, {"@playwright/test": "^1"})
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.test_framework == "Playwright"


class TestComponentLibraryDetection:

    def test_detects_shadcn_via_radix(self, tmp_path: Path):
        # shadcn/ui uses radix primitives -- 3+ radix packages = shadcn signal
        deps = {
            "react": "^18",
            "@radix-ui/react-dialog": "^1",
            "@radix-ui/react-dropdown-menu": "^1",
            "@radix-ui/react-select": "^1",
            "@radix-ui/react-tooltip": "^1",
        }
        _write_pkg(tmp_path, deps)
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.component_library == "shadcn/ui"

    def test_detects_mui(self, tmp_path: Path):
        _write_pkg(tmp_path, {"react": "^18", "@mui/material": "^5"})
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.component_library == "Material UI"

    def test_two_radix_packages_not_shadcn(self, tmp_path: Path):
        # only 2 radix packages -- could be manual, not necessarily shadcn
        deps = {
            "react": "^18",
            "@radix-ui/react-dialog": "^1",
            "@radix-ui/react-tooltip": "^1",
        }
        _write_pkg(tmp_path, deps)
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.component_library is None


class TestStateManagementDetection:

    def test_detects_tanstack_query(self, tmp_path: Path):
        _write_pkg(tmp_path, {"react": "^18", "@tanstack/react-query": "^5"})
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.state_management == "TanStack Query"

    def test_detects_zustand(self, tmp_path: Path):
        _write_pkg(tmp_path, {"react": "^18", "zustand": "^4"})
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.state_management == "Zustand"

    def test_detects_redux_toolkit(self, tmp_path: Path):
        _write_pkg(tmp_path, {"react": "^18", "@reduxjs/toolkit": "^2", "redux": "^5"})
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.state_management == "Redux Toolkit"


class TestStylingDetection:

    def test_detects_tailwind(self, tmp_path: Path):
        _write_pkg(tmp_path, {"react": "^18"}, {"tailwindcss": "^3"})
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.styling == "Tailwind CSS"

    def test_detects_styled_components(self, tmp_path: Path):
        _write_pkg(tmp_path, {"react": "^18", "styled-components": "^6"})
        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        assert dna.frontend_patterns.styling == "styled-components"


class TestFullStackDetection:

    def test_oci_style_fullstack_repo(self, tmp_path: Path):
        """Simulate the OpenCodeIntel repo: React + Vite + Tailwind + shadcn + TanStack + Vitest + Bun."""
        # Write Python backend file
        (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()")

        # Write package.json with OCI's actual deps
        deps = {
            "react": "^18",
            "react-dom": "^18",
            "@tanstack/react-query": "^5",
            "tailwindcss": "^3",
            "@radix-ui/react-dialog": "^1",
            "@radix-ui/react-dropdown-menu": "^1",
            "@radix-ui/react-select": "^1",
            "@radix-ui/react-tooltip": "^1",
        }
        dev_deps = {
            "vite": "^5",
            "@vitejs/plugin-react": "^4",
            "vitest": "^1",
            "typescript": "^5",
        }
        scripts = {"test": "vitest run", "dev": "vite", "build": "vite build"}
        _write_pkg(tmp_path, deps, dev_deps, scripts, lockfile="bun.lock")

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))

        fp = dna.frontend_patterns
        assert fp is not None
        assert fp.framework == "React"
        assert fp.package_manager == "bun"
        assert fp.test_framework == "Vitest"
        assert fp.test_command == "bun run test"
        assert fp.component_library == "shadcn/ui"
        assert fp.state_management == "TanStack Query"
        assert fp.styling == "Tailwind CSS"
        assert fp.build_tool == "Vite"
        assert fp.language == "TypeScript"


class TestFrontendInFormatters:

    def test_agents_md_includes_frontend_section(self, tmp_path: Path):
        from saar.formatters.agents_md import render_agents_md
        from saar.models import CodebaseDNA, FrontendPattern

        dna = CodebaseDNA(
            repo_name="test",
            frontend_patterns=FrontendPattern(
                framework="React",
                package_manager="bun",
                test_framework="Vitest",
                test_command="bun run test",
                component_library="shadcn/ui",
                state_management="TanStack Query",
                styling="Tailwind CSS",
                build_tool="Vite",
                language="TypeScript",
            )
        )
        out = render_agents_md(dna)
        assert "## Frontend" in out
        assert "React" in out
        assert "bun" in out
        assert "Vitest" in out
        assert "bun run test" in out
        assert "shadcn/ui" in out
        assert "TanStack Query" in out
        assert "Tailwind CSS" in out

    def test_no_frontend_section_for_pure_python(self):
        from saar.formatters.agents_md import render_agents_md
        from saar.models import CodebaseDNA

        dna = CodebaseDNA(repo_name="python-only")
        out = render_agents_md(dna)
        assert "## Frontend" not in out
