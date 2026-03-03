"""Guided interview engine for capturing tribal knowledge.

Static analysis tells you WHAT a codebase does.
The interview tells you WHY, WHAT NOT TO DO, and what the AI will get wrong.

Flow:
    1. Show what saar detected (detect-first-ask-second)
    2. Gateway: quick (4 questions) / full (7 questions) / skip
    3. Ask context-aware questions
    4. Cache answers to .saar/config.json
    5. Return InterviewAnswers merged into CodebaseDNA

Non-interactive mode (CI / --no-interview / non-TTY):
    Silently loads cached answers if available, otherwise skips.
    Never prompts, never crashes.
"""
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from saar.models import CodebaseDNA, InterviewAnswers

logger = logging.getLogger(__name__)

# Cache file lives inside the repo so teams can commit it
_CACHE_FILENAME = ".saar/config.json"
_CACHE_VERSION = 1

# CI environment variables -- any of these present means non-interactive
_CI_ENV_VARS = [
    "CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL",
    "CIRCLECI", "TRAVIS", "BUILDKITE", "TF_BUILD",
]


# -- interactivity detection -----------------------------------------------

def is_interactive(no_interview: bool = False) -> bool:
    """Return True only when safe to prompt the user.

    Checks: explicit flag, TTY availability, CI environment.
    Any one condition being false makes the whole thing non-interactive.
    """
    if no_interview:
        return False
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False
    if any(os.environ.get(v) for v in _CI_ENV_VARS):
        return False
    return True


# -- cache -----------------------------------------------------------------

def load_cached(repo_path: Path) -> Optional[InterviewAnswers]:
    """Load previously saved interview answers from .saar/config.json."""
    cache_file = repo_path / _CACHE_FILENAME
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        if data.get("version") != _CACHE_VERSION:
            logger.debug("Cache version mismatch, ignoring cached answers")
            return None
        answers = data.get("answers", {})
        return InterviewAnswers(
            project_purpose=answers.get("project_purpose"),
            never_do=answers.get("never_do"),
            domain_terms=answers.get("domain_terms"),
            verify_workflow=answers.get("verify_workflow"),
            auth_gotchas=answers.get("auth_gotchas"),
            off_limits=answers.get("off_limits"),
            extra_context=answers.get("extra_context"),
        )
    except Exception as e:
        logger.debug("Failed to load interview cache: %s", e)
        return None


def save_cache(repo_path: Path, answers: InterviewAnswers) -> None:
    """Persist interview answers to .saar/config.json."""
    cache_dir = repo_path / ".saar"
    cache_dir.mkdir(exist_ok=True)

    # write a .gitignore inside .saar so the cache isn't accidentally committed
    # unless the team explicitly wants it (they can delete this file)
    gitignore = cache_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(
            "# Remove this file if you want to commit .saar/config.json to share\n"
            "# interview answers with your team.\n"
            "config.json\n",
            encoding="utf-8",
        )

    data = {
        "version": _CACHE_VERSION,
        "answers": {
            "project_purpose": answers.project_purpose,
            "never_do": answers.never_do,
            "domain_terms": answers.domain_terms,
            "verify_workflow": answers.verify_workflow,
            "auth_gotchas": answers.auth_gotchas,
            "off_limits": answers.off_limits,
            "extra_context": answers.extra_context,
        },
    }
    cache_file = repo_path / _CACHE_FILENAME
    cache_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.debug("Saved interview answers to %s", cache_file)


# -- detection summary -----------------------------------------------------

def _build_detection_summary(dna: CodebaseDNA) -> str:
    """Build a human-readable summary of what saar detected.

    Shown before questions so developers can verify detections are correct
    before being asked to build on them (detect-first-ask-second pattern).
    """
    parts = []

    # languages and framework
    langs = ", ".join(
        f"{lang} ({count} files)"
        for lang, count in sorted(dna.language_distribution.items(), key=lambda x: -x[1])
    )
    if langs:
        parts.append(langs)
    if dna.detected_framework:
        parts.append(dna.detected_framework)

    # scale
    if dna.total_functions:
        parts.append(f"{dna.total_functions:,} functions")
    if dna.test_patterns.framework:
        parts.append(dna.test_patterns.framework)
    if dna.database_patterns.orm_used:
        parts.append(dna.database_patterns.orm_used)

    return " · ".join(parts) if parts else "no specific patterns detected"


# -- the interview ---------------------------------------------------------


def append_to_cache(repo_path: Path, field: str, value: str) -> InterviewAnswers:
    """Append a single correction to one field in the cached answers.

    If no cache exists, creates one with just this field set.
    If the field already has content, appends as a new bullet point.
    Returns the updated InterviewAnswers.
    """
    existing = load_cached(repo_path) or InterviewAnswers()

    current = getattr(existing, field, None)

    if current:
        # normalize existing content to bullet list then append
        lines = [l.strip() for l in current.strip().splitlines() if l.strip()]
        cleaned = [l.lstrip("- ").lstrip("* ").strip() for l in lines]
        cleaned.append(value.strip())
        merged = "\n".join(f"- {l}" for l in cleaned)
    else:
        merged = f"- {value.strip()}"

    setattr(existing, field, merged)
    save_cache(repo_path, existing)
    return existing


def run_interview(
    dna: CodebaseDNA,
    repo_path: Path,
    no_interview: bool = False,
    console=None,
) -> Optional[InterviewAnswers]:
    """Run the guided interview and return answers, or None if skipped.

    In non-interactive mode: returns cached answers if available.
    In interactive mode: runs the questionary flow, caches results.
    """
    # always try to load cache first
    cached = load_cached(repo_path)

    if not is_interactive(no_interview):
        if cached:
            logger.debug("Non-interactive mode: using cached interview answers")
        return cached

    # we're interactive -- import questionary lazily so non-interactive
    # paths never pay the import cost or risk a crash
    try:
        import questionary
        from questionary import Style
    except ImportError:
        logger.warning("questionary not installed -- skipping interview")
        return cached

    saar_style = Style([
        ("qmark", "fg:#00d7ff bold"),
        ("question", "bold"),
        ("answer", "fg:#00d7ff"),
        ("pointer", "fg:#00d7ff bold"),
        ("highlighted", "fg:#00d7ff bold"),
        ("instruction", "fg:#888888"),
    ])

    # -- show what we detected -------------------------------------------
    detection = _build_detection_summary(dna)
    if console:
        console.print(f"\n[dim]Detected:[/dim] [cyan]{detection}[/cyan]")
        if cached:
            console.print("[dim]Found cached answers from a previous run.[/dim]")

    # -- gateway question ------------------------------------------------
    mode = questionary.select(
        "How would you like to proceed?",
        choices=[
            questionary.Choice(
                "Quick setup  (4 essential questions, ~60 seconds)",
                value="quick",
            ),
            questionary.Choice(
                "Full setup   (7 questions for best results, ~2 minutes)",
                value="full",
            ),
            questionary.Choice(
                "Skip interview  (use cached answers or auto-detect only)",
                value="skip",
            ),
        ],
        default="quick",
        style=saar_style,
    ).ask()

    if mode is None or mode == "skip":
        return cached

    # -- pre-fill defaults from cache ------------------------------------
    def default(field: str, fallback: str = "") -> str:
        if cached:
            val = getattr(cached, field, None)
            if val:
                return val
        return fallback

    # -- universal questions (always asked) ------------------------------
    purpose = questionary.text(
        "Describe this project in one sentence:",
        default=default("project_purpose"),
        instruction="(used as the AI's role context -- e.g. 'Multi-tenant SaaS API for supply chain tracking')",
        style=saar_style,
    ).ask()

    never_do = questionary.text(
        "What are the absolute 'never do' rules in this codebase?",
        default=default("never_do"),
        instruction="(gotchas, frozen modules, anti-patterns -- e.g. 'Never modify billing/, never use sync in async endpoints')",
        style=saar_style,
        multiline=True,
    ).ask()

    domain_terms = questionary.text(
        "Any domain-specific terms AI should know?",
        default=default("domain_terms"),
        instruction="(terms with non-obvious meanings -- e.g. 'Workspace = tenant, not directory')",
        style=saar_style,
        multiline=True,
    ).ask()

    verify = questionary.text(
        "How do you verify that changes actually work?",
        default=default("verify_workflow", "Run tests"),
        instruction="(full loop -- e.g. 'pytest -x, then docker compose up and curl /health')",
        style=saar_style,
    ).ask()

    # -- full mode extras ------------------------------------------------
    auth_gotchas = None
    off_limits = None
    extra = None

    if mode == "full":
        auth_gotchas = questionary.text(
            "Any auth / security gotchas?",
            default=default("auth_gotchas"),
            instruction="(e.g. 'JWT tokens expire in 15min, always refresh. Never log token values.')",
            style=saar_style,
            multiline=True,
        ).ask()

        off_limits = questionary.text(
            "Files or modules AI should NEVER modify?",
            default=default("off_limits"),
            instruction="(e.g. 'core/auth.py has clock-skew workaround, billing/ is frozen')",
            style=saar_style,
            multiline=True,
        ).ask()

        extra = questionary.text(
            "Anything else AI assistants consistently get wrong here?",
            default=default("extra_context"),
            instruction="(optional -- press Enter to skip)",
            style=saar_style,
            multiline=True,
        ).ask()

    # -- handle Ctrl+C / None answers cleanly ----------------------------
    # questionary returns None if the user hits Ctrl+C
    if purpose is None and never_do is None:
        return cached

    answers = InterviewAnswers(
        project_purpose=purpose or None,
        never_do=never_do or None,
        domain_terms=domain_terms or None,
        verify_workflow=verify or None,
        auth_gotchas=auth_gotchas or None,
        off_limits=off_limits or None,
        extra_context=extra or None,
    )

    save_cache(repo_path, answers)

    return answers
