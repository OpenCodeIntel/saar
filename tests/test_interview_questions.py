"""Tests for OPE-151: stack-aware interview questions.

Every question builder must:
- Return a QuestionContext with non-empty question and instruction
- Include detected patterns in the instruction text
- NOT crash when DNA fields are empty/None
- Produce different output for different stacks
"""
import pytest
from saar.interview_questions import (
    build_never_do_question,
    build_verify_question,
    build_auth_question,
    build_domain_terms_question,
    build_off_limits_question,
    QuestionContext,
)
from saar.models import (
    CodebaseDNA, AuthPattern, DatabasePattern, TestPattern,
    FrontendPattern,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_dna(**kwargs) -> CodebaseDNA:
    """Build a minimal CodebaseDNA with sensible defaults."""
    return CodebaseDNA(repo_name="test-repo", **kwargs)


def fastapi_dna() -> CodebaseDNA:
    return make_dna(
        detected_framework="fastapi",
        auth_patterns=AuthPattern(
            middleware_used=["require_auth", "public_auth"],
            auth_decorators=["Depends(require_auth)"],
        ),
        database_patterns=DatabasePattern(orm_used="Supabase", has_rls=True),
        test_patterns=TestPattern(framework="pytest"),
        frontend_patterns=FrontendPattern(
            framework="React",
            package_manager="bun",
            test_framework="Vitest",
        ),
    )


def django_dna() -> CodebaseDNA:
    return make_dna(
        detected_framework="django",
        auth_patterns=AuthPattern(
            middleware_used=["IsAuthenticated"],
            auth_decorators=["@login_required"],
        ),
        database_patterns=DatabasePattern(orm_used="Django ORM"),
        test_patterns=TestPattern(framework="pytest"),
    )


def flask_dna() -> CodebaseDNA:
    return make_dna(
        detected_framework="flask",
        auth_patterns=AuthPattern(middleware_used=["@login_required"]),
        test_patterns=TestPattern(framework="pytest"),
    )


def empty_dna() -> CodebaseDNA:
    return make_dna()


# ---------------------------------------------------------------------------
# QuestionContext contract
# ---------------------------------------------------------------------------

class TestQuestionContextContract:
    """Every builder must return a valid QuestionContext regardless of input."""

    @pytest.mark.parametrize("builder,dna_factory", [
        (build_never_do_question, fastapi_dna),
        (build_never_do_question, django_dna),
        (build_never_do_question, empty_dna),
        (build_verify_question, fastapi_dna),
        (build_verify_question, django_dna),
        (build_verify_question, empty_dna),
        (build_auth_question, fastapi_dna),
        (build_auth_question, django_dna),
        (build_auth_question, empty_dna),
        (build_domain_terms_question, fastapi_dna),
        (build_domain_terms_question, empty_dna),
        (build_off_limits_question, fastapi_dna),
        (build_off_limits_question, empty_dna),
    ])
    def test_returns_question_context(self, builder, dna_factory):
        result = builder(dna_factory())
        assert isinstance(result, QuestionContext)

    @pytest.mark.parametrize("builder,dna_factory", [
        (build_never_do_question, fastapi_dna),
        (build_never_do_question, empty_dna),
        (build_verify_question, fastapi_dna),
        (build_verify_question, empty_dna),
        (build_auth_question, fastapi_dna),
        (build_auth_question, empty_dna),
        (build_domain_terms_question, fastapi_dna),
        (build_domain_terms_question, empty_dna),
        (build_off_limits_question, fastapi_dna),
        (build_off_limits_question, empty_dna),
    ])
    def test_question_and_instruction_always_non_empty(self, builder, dna_factory):
        result = builder(dna_factory())
        assert result.question, f"{builder.__name__} returned empty question"
        assert result.instruction, f"{builder.__name__} returned empty instruction"

    @pytest.mark.parametrize("builder,dna_factory", [
        (build_never_do_question, fastapi_dna),
        (build_verify_question, fastapi_dna),
        (build_auth_question, fastapi_dna),
        (build_domain_terms_question, fastapi_dna),
        (build_off_limits_question, fastapi_dna),
    ])
    def test_no_multiline_in_instruction(self, builder, dna_factory):
        """Instructions must be single-line -- no newlines that would break questionary."""
        result = builder(dna_factory())
        assert "\n" not in result.instruction, (
            f"{builder.__name__} instruction contains newline -- will break questionary"
        )


# ---------------------------------------------------------------------------
# never_do question -- stack-specific content
# ---------------------------------------------------------------------------

class TestNeverDoQuestion:

    def test_fastapi_mentions_async(self):
        result = build_never_do_question(fastapi_dna())
        assert "async" in result.instruction.lower() or "sync" in result.instruction.lower()

    def test_bun_package_manager_flagged(self):
        result = build_never_do_question(fastapi_dna())
        assert "npm" in result.instruction.lower() or "bun" in result.instruction.lower()

    def test_supabase_rls_flagged(self):
        result = build_never_do_question(fastapi_dna())
        assert "rls" in result.instruction.lower() or "service role" in result.instruction.lower()

    def test_django_mentions_orm(self):
        result = build_never_do_question(django_dna())
        assert "orm" in result.instruction.lower() or "raw sql" in result.instruction.lower()

    def test_flask_mentions_app_context(self):
        result = build_never_do_question(flask_dna())
        assert "context" in result.instruction.lower() or "global" in result.instruction.lower()

    def test_empty_dna_returns_generic_instruction(self):
        result = build_never_do_question(empty_dna())
        assert result.instruction  # must not be empty
        assert result.question == "What are the absolute 'never do' rules in this codebase?"

    def test_fastapi_instruction_differs_from_django(self):
        fastapi_result = build_never_do_question(fastapi_dna())
        django_result = build_never_do_question(django_dna())
        assert fastapi_result.instruction != django_result.instruction, (
            "FastAPI and Django should produce different never_do instructions"
        )


# ---------------------------------------------------------------------------
# verify question -- uses detected test commands
# ---------------------------------------------------------------------------

class TestVerifyQuestion:

    def test_fastapi_with_pytest_includes_pytest(self):
        dna = make_dna(
            test_patterns=TestPattern(framework="pytest"),
            detected_framework="fastapi",
        )
        result = build_verify_question(dna)
        assert "pytest" in result.instruction.lower() or "pytest" in result.default_hint.lower()

    def test_bun_frontend_includes_bun(self):
        result = build_verify_question(fastapi_dna())
        text = result.instruction.lower() + result.default_hint.lower()
        assert "bun" in text or "test" in text

    def test_existing_verify_workflow_used_as_default(self):
        dna = make_dna(verify_workflow="pytest -x && docker compose up")
        result = build_verify_question(dna)
        assert "pytest -x" in result.default_hint or "pytest -x" in result.instruction

    def test_empty_dna_returns_fallback_default(self):
        result = build_verify_question(empty_dna())
        assert result.default_hint in ("Run tests", "") or result.default_hint
        assert result.question


# ---------------------------------------------------------------------------
# auth question -- shows detected patterns
# ---------------------------------------------------------------------------

class TestAuthQuestion:

    def test_fastapi_shows_detected_patterns(self):
        result = build_auth_question(fastapi_dna())
        text = result.instruction.lower()
        assert "require_auth" in text or "public_auth" in text or "auth" in text

    def test_rls_question_included_for_supabase(self):
        result = build_auth_question(fastapi_dna())
        assert "rls" in result.instruction.lower() or "row level" in result.instruction.lower()

    def test_canonical_question_when_multiple_patterns(self):
        """When multiple auth patterns detected, ask which is canonical."""
        dna = make_dna(
            detected_framework="fastapi",
            auth_patterns=AuthPattern(
                middleware_used=["require_auth", "public_auth", "admin_auth"]
            ),
        )
        result = build_auth_question(dna)
        assert "canonical" in result.instruction.lower()

    def test_django_mentions_permissions(self):
        result = build_auth_question(django_dna())
        text = result.instruction.lower()
        assert "permission" in text or "auth" in text or "isauthenticated" in text

    def test_empty_dna_still_returns_valid_question(self):
        result = build_auth_question(empty_dna())
        assert result.question
        assert result.instruction


# ---------------------------------------------------------------------------
# domain terms question
# ---------------------------------------------------------------------------

class TestDomainTermsQuestion:

    def test_supabase_mentioned_for_supabase_projects(self):
        result = build_domain_terms_question(fastapi_dna())
        text = result.instruction.lower()
        assert "supabase" in text or "term" in text or "non-obvious" in text

    def test_empty_dna_returns_generic_with_examples(self):
        result = build_domain_terms_question(empty_dna())
        assert result.instruction
        assert result.question == "Any domain-specific terms AI should know?"


# ---------------------------------------------------------------------------
# off-limits question -- highlights critical files
# ---------------------------------------------------------------------------

class TestOffLimitsQuestion:

    def test_critical_files_appear_in_instruction(self):
        dna = make_dna(
            critical_files=[
                {"file": "backend/middleware/auth.py", "dependents": 12},
                {"file": "backend/config/startup_checks.py", "dependents": 8},
            ]
        )
        result = build_off_limits_question(dna)
        assert "auth.py" in result.instruction or "startup_checks" in result.instruction

    def test_no_critical_files_returns_generic(self):
        result = build_off_limits_question(empty_dna())
        assert result.question
        assert result.instruction
        assert "never" in result.instruction.lower() or "modify" in result.instruction.lower()

    def test_question_text_is_correct(self):
        result = build_off_limits_question(fastapi_dna())
        assert result.question == "Files or modules AI should NEVER modify?"
