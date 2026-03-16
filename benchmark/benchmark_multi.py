#!/usr/bin/env python3
"""saar multi-repo benchmark -- OPE-99 expanded

Measures whether saar's AGENTS.md reduces Claude's convention violations
across 6 real-world codebases with diverse stacks.

Method:
  For each repo, run repo-specific coding tasks twice:
    1. Without context (Claude training data only)
    2. With context (AGENTS.md prepended as system prompt)

  Check each output against binary pass/fail rules derived from the repo's
  actual conventions. Only tests PROJECT-SPECIFIC conventions that Claude
  cannot know from training data alone.

Repos:
  repo1  fastapi-template  FastAPI + React + bun
  repo3  cal.com           NestJS + Next.js + yarn
  repo4  hoppscotch        NestJS + Svelte + pnpm + @UseGuards auth
  repoA  next.js           Next.js + pnpm
  repoB  storybook-rn      React Native + Emotion (not Tailwind) + pnpm
  repoC  posthog           Django + Next.js + structlog + pnpm

Usage:
  export ANTHROPIC_API_KEY=sk-ant-...
  python benchmark/benchmark_multi.py              # all repos, 3 runs
  python benchmark/benchmark_multi.py --dry-run   # validate setup only
  python benchmark/benchmark_multi.py --repo repoC --runs 1
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1200
RUNS_PER_TASK = 3


# ── Check implementations ─────────────────────────────────────────────────────
# Each check: output (str) -> bool (True = pass, no violation)
# Only include checks where Claude WILL fail without context.
# Generic patterns (snake_case, pytest fixtures) Claude already knows -- skip.


def _check_uses_bun_not_npm(output: str) -> bool:
    """repo1: package manager is bun."""
    return not bool(re.search(
        r'\bnpm install\b|\bnpm i\b|\bnpm add\b|\byarn add\b|\byarn install\b|\bpnpm add\b|\bpnpm install\b',
        output
    ))


def _check_uses_yarn_not_npm(output: str) -> bool:
    """repo3-calcom: package manager is yarn."""
    return not bool(re.search(r'\bnpm install\b|\bnpm i\b|\bnpm add\b', output))


def _check_uses_pnpm_not_npm(output: str) -> bool:
    """repos using pnpm: hoppscotch, nextjs, storybook, posthog."""
    return not bool(re.search(r'\bnpm install\b|\bnpm i\b|\bnpm add\b|\byarn add\b|\byarn install\b', output))


def _check_uses_cn_not_template_literal(output: str) -> bool:
    """repos with shadcn/ui: conditional classes use cn() not template literals."""
    has_cn = bool(re.search(r'\bcn\s*\(', output))
    has_raw = bool(re.search(r'className=\{`[^`]*\$\{[^}]+\}', output))
    return not (has_raw and not has_cn)


def _check_uses_emotion_not_tailwind(output: str) -> bool:
    """repoB-storybook: uses Emotion CSS-in-JS, NOT Tailwind.

    Without context, Claude writes Tailwind utility class strings.
    With context (Styling: Emotion), Claude uses @emotion/styled or similar.
    Most non-obvious check -- both are valid React styling, only AGENTS.md tells you which.
    """
    has_emotion = bool(re.search(
        r'@emotion/styled|@emotion/react|styled\s*\([A-Za-z]|\bstyle\s*=\s*\{|StyleSheet\.create',
        output
    ))
    has_tailwind = bool(re.search(
        r'className=["\'`][^"\'`]*\b(?:text-|bg-|flex|grid-|p-|px-|py-|m-|mx-|my-|w-|h-|rounded|border|font-|items-|justify-)[^"\'`]*["\'`]',
        output
    ))
    return not (has_tailwind and not has_emotion)


def _check_uses_structlog_not_standard_logging(output: str) -> bool:
    """repoC-posthog: uses structlog, not standard Python logging.

    Without context: import logging; logger = logging.getLogger(__name__)
    With context:    import structlog; logger = structlog.get_logger()
    Claude always defaults to standard logging. Structlog is a codebase choice.
    """
    has_structlog = bool(re.search(r'\bstructlog\b', output))
    has_standard = bool(re.search(r'\bimport logging\b|logging\.getLogger', output))
    return not (has_standard and not has_structlog)


def _check_uses_nestjs_guards_not_manual(output: str) -> bool:
    """repo4-hoppscotch: NestJS auth uses @UseGuards(), not manual header parsing."""
    has_guards = bool(re.search(r'@UseGuards\s*\(', output))
    has_manual = bool(re.search(
        r'req\.headers\[.authorization|request\.headers\[.authorization',
        output, re.IGNORECASE
    ))
    return not (has_manual and not has_guards)


# ── Task + Repo definitions ───────────────────────────────────────────────────

@dataclass
class Check:
    name: str
    description: str
    fn: object = field(repr=False)


@dataclass
class Task:
    id: str
    title: str
    prompt: str
    checks: list[Check]


@dataclass
class RepoBenchmark:
    id: str
    name: str
    github: str
    path: Path
    tasks: list[Task]

    @property
    def agents_md_path(self) -> Path:
        return self.path / "AGENTS.md"

    @property
    def total_checks(self) -> int:
        return sum(len(t.checks) for t in self.tasks)


# repo1-fastapi-template: bun + shadcn/ui (cn)
TASKS_REPO1: list[Task] = [
    Task(
        id="install_package",
        title="Install the date-fns package",
        prompt="I need to add the 'date-fns' library for date formatting in my frontend.\nShow the exact terminal command to install it.",
        checks=[Check("uses_bun_not_npm", "Install uses bun, not npm/yarn/pnpm", _check_uses_bun_not_npm)],
    ),
    Task(
        id="styled_component",
        title="Add a React component with conditional styling",
        prompt=(
            "Write a React TypeScript component StatusBadge that takes an `active: boolean` prop "
            "and renders a badge. Active = green background, inactive = gray background.\n"
            "Show complete component code with conditional className logic."
        ),
        checks=[Check("uses_cn_not_template", "Conditional classes use cn(), not template literals", _check_uses_cn_not_template_literal)],
    ),
]


# repo3-calcom: yarn + shadcn/ui (cn)
TASKS_REPO3: list[Task] = [
    Task(
        id="install_package",
        title="Install the date-fns package",
        prompt="I need to add the 'date-fns' library for date formatting.\nShow the exact terminal command to install it.",
        checks=[Check("uses_yarn_not_npm", "Install uses yarn, not npm", _check_uses_yarn_not_npm)],
    ),
    Task(
        id="styled_component",
        title="Add a React component with conditional styling",
        prompt=(
            "Write a React TypeScript component EventStatusBadge that takes a "
            "`status: 'confirmed' | 'pending' | 'cancelled'` prop and renders a badge "
            "with different colors per status. Show complete component with conditional className."
        ),
        checks=[Check("uses_cn_not_template", "Conditional classes use cn(), not template literals", _check_uses_cn_not_template_literal)],
    ),
]

# repo4-hoppscotch: pnpm + NestJS @UseGuards auth
TASKS_REPO4: list[Task] = [
    Task(
        id="install_package",
        title="Install the date-fns package",
        prompt="I need to add the 'date-fns' library for date formatting.\nShow the exact terminal command to install it.",
        checks=[Check("uses_pnpm_not_npm", "Install uses pnpm, not npm/yarn", _check_uses_pnpm_not_npm)],
    ),
    Task(
        id="nestjs_auth",
        title="Add authentication to a NestJS controller endpoint",
        prompt=(
            "I have a NestJS controller with a GET /collections endpoint that is currently public.\n"
            "Make it require JWT authentication so only logged-in users can access it.\n"
            "Show the modified TypeScript controller code."
        ),
        checks=[Check("uses_guards_not_manual", "@UseGuards() decorator, not manual header parsing", _check_uses_nestjs_guards_not_manual)],
    ),
]

