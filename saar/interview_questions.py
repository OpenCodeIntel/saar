"""Stack-aware interview question builder for OPE-151.

Instead of generic questions, we inject what saar already detected into
the question text. The developer sees exactly what was found and corrects
or confirms it -- much faster and produces more precise answers.

Generic:  "Any auth gotchas?"
Smart:    "I found require_auth and public_auth -- which is canonical for
           new endpoints? Any JWT/session edge cases to warn AI about?"

Generic:  "How do you verify changes work?"
Smart:    "I found: pytest tests/ -v and bun run build -- is this the full
           verification loop, or are there other steps (docker, migrations)?"

The builder returns QuestionContext objects -- plain dataclasses with
the question text and instruction hint. No questionary dependency here,
so this module is testable without a TTY.
"""
from __future__ import annotations

from dataclasses import dataclass

from saar.models import CodebaseDNA


@dataclass
class QuestionContext:
    """Text for a single interview question, tailored to detected stack."""
    question: str
    instruction: str
    default_hint: str = ""  # pre-filled text hint based on DNA


def build_never_do_question(dna: CodebaseDNA) -> QuestionContext:
    """Build the 'never do' question with detected anti-patterns as context."""
    hints: list[str] = []

    # Package manager -- common footgun
    fp = dna.frontend_patterns
    if fp and fp.package_manager and fp.package_manager.lower() != "npm":
        hints.append(f"never use npm/yarn (detected: {fp.package_manager})")

    # Framework-specific gotchas
    fw = (dna.detected_framework or "").lower()
    if fw in ("fastapi", "starlette"):
        hints.append("never use sync functions in async endpoints (blocks event loop)")
    elif fw == "django":
        hints.append("never bypass the ORM for writes (use Model.save(), not raw SQL)")
    elif fw in ("express", "nestjs"):
        hints.append("never forget to call next() in middleware")
    elif fw == "flask":
        hints.append("never use global state outside of app context")

    # Database-specific
    db = dna.database_patterns
    if db.has_rls:
        hints.append("never bypass RLS -- always use authenticated client for user data")
    if db.orm_used and "supabase" in db.orm_used.lower():
        hints.append("never use service role key on the frontend")

    # Auth patterns
    auth = dna.auth_patterns
    if len(auth.middleware_used) > 1:
        patterns = ", ".join(auth.middleware_used[:3])
        hints.append(f"never mix auth patterns ({patterns}) without understanding which is canonical")

    if hints:
        hint_str = "; ".join(hints[:3])  # cap at 3 to keep question readable
        instruction = (
            f"saar detected these potential footguns: {hint_str}. "
            "Add more or correct -- separate with semicolons"
        )
    else:
        instruction = (
            "Gotchas, frozen modules, anti-patterns -- "
            "e.g. 'Never modify billing/; never use sync in async endpoints'"
        )

    return QuestionContext(
        question="What are the absolute 'never do' rules in this codebase?",
        instruction=instruction,
        default_hint="; ".join(hints[:2]) if hints else "",
    )


def build_verify_question(dna: CodebaseDNA) -> QuestionContext:
    """Build the verification question with detected test/build commands as context."""
    detected_steps: list[str] = []

    # Backend test command
    tp = dna.test_patterns
    if tp.framework == "pytest":
        detected_steps.append("pytest tests/ -v")
    elif tp.framework == "jest":
        detected_steps.append("npx jest")
    elif tp.framework == "vitest":
        detected_steps.append("bun run test")

    # Frontend build
    fp = dna.frontend_patterns
    if fp:
        pm = fp.package_manager or "npm"
        if fp.test_framework:
            detected_steps.append(f"{pm} run test")
        detected_steps.append(f"{pm} run build")

    # Verification workflow already detected
    if dna.verify_workflow:
        return QuestionContext(
            question="How do you verify that changes actually work?",
            instruction=(
                f"saar detected: {dna.verify_workflow[:80]}. "
                "Confirm or add missing steps (docker, migrations, curl checks)"
            ),
            default_hint=dna.verify_workflow,
        )

    if detected_steps:
        detected_str = " && ".join(detected_steps[:3])
        instruction = (
            f"saar detected these commands: {detected_str}. "
            "Is this the full loop, or are there other steps?"
        )
        return QuestionContext(
            question="How do you verify that changes actually work?",
            instruction=instruction,
            default_hint=detected_str,
        )

    return QuestionContext(
        question="How do you verify that changes actually work?",
        instruction=(
            "Full loop -- e.g. 'pytest -x, then docker compose up and curl /health'"
        ),
        default_hint="Run tests",
    )


def build_auth_question(dna: CodebaseDNA) -> QuestionContext:
    """Build auth gotchas question with detected auth patterns as context."""
    auth = dna.auth_patterns
    parts: list[str] = []

    if auth.middleware_used:
        patterns = ", ".join(auth.middleware_used[:4])
        parts.append(f"I found these auth patterns: {patterns}")
        if len(auth.middleware_used) > 1:
            parts.append("which is canonical for new endpoints?")

    db = dna.database_patterns
    if db.has_rls:
        parts.append("RLS is enabled -- any tables where it should NOT apply?")

    if auth.auth_decorators:
        decorators = ", ".join(auth.auth_decorators[:3])
        parts.append(f"decorators: {decorators}")

    fw = (dna.detected_framework or "").lower()
    if fw in ("fastapi", "starlette"):
        parts.append("any JWT expiry / refresh token edge cases to warn AI about?")
    elif fw == "django":
        parts.append("any permission classes or custom backends to be aware of?")

    if parts:
        instruction = " ".join(parts[:4])
    else:
        instruction = (
            "e.g. 'JWT tokens expire in 15min, always refresh; "
            "never log token values'"
        )

    return QuestionContext(
        question="Any auth / security gotchas?",
        instruction=instruction,
    )


def build_domain_terms_question(dna: CodebaseDNA) -> QuestionContext:
    """Build domain vocabulary question with framework context."""
    fw = (dna.detected_framework or "").lower()
    db = dna.database_patterns

    examples: list[str] = []

    if fw in ("fastapi", "django", "flask"):
        examples.append("e.g. 'Workspace = tenant, not a directory'")
    if db.orm_used:
        examples.append(f"any {db.orm_used}-specific terms with non-obvious meaning?")

    fp = dna.frontend_patterns
    if fp and fp.state_management:
        examples.append(
            f"any {fp.state_management} patterns that differ from the docs?"
        )

    if examples:
        instruction = " -- ".join(examples[:2])
    else:
        instruction = (
            "Terms with non-obvious meanings -- "
            "separate with semicolons, e.g. 'Workspace = tenant; Plan = subscription tier'"
        )

    return QuestionContext(
        question="Any domain-specific terms AI should know?",
        instruction=instruction,
    )


def build_off_limits_question(dna: CodebaseDNA) -> QuestionContext:
    """Build off-limits question highlighting critical files already detected."""
    critical = dna.critical_files or []

    # Pick top 2 most critical files as examples
    top_files: list[str] = []
    for cf in critical[:2]:
        fname = cf.get("file", "") if isinstance(cf, dict) else str(cf)
        if fname:
            top_files.append(fname)

    if top_files:
        files_str = ", ".join(top_files)
        instruction = (
            f"saar flagged these as high-dependency files: {files_str}. "
            "Which should AI never modify without explicit permission? "
            "Separate with semicolons"
        )
    else:
        instruction = (
            "Files or modules AI should never modify -- "
            "e.g. 'core/auth.py; billing/ is frozen'"
        )

    return QuestionContext(
        question="Files or modules AI should NEVER modify?",
        instruction=instruction,
    )
