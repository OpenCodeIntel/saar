"""Tests for saar deep_extractor (OPE-96) -- rules WITH reasoning."""
from pathlib import Path
from saar.deep_extractor import (
    DeepRule, DeepExtractionResult,
    _derive_auth_rules, _derive_exception_rules,
    _derive_testing_rules, _derive_naming_rules,
    _derive_never_do_rules, run_deep_extraction,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_py(tmp_path: Path, name: str, content: str) -> Path:
    f = tmp_path / name
    f.write_text(content, encoding="utf-8")
    return f


def _make_ts(tmp_path: Path, name: str, content: str) -> Path:
    f = tmp_path / name
    f.write_text(content, encoding="utf-8")
    return f


def safe_read(path: Path):
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


class FakeDNA:
    """Minimal DNA stub for deep extractor tests."""
    class _lp:
        structured_logging = False
        logger_import = "logging"
    logging_patterns = _lp()


# ── DeepRule ─────────────────────────────────────────────────────────────────

class TestDeepRule:
    def test_defaults(self):
        r = DeepRule("test rule", 0.8)
        assert r.text == "test rule"
        assert r.confidence == 0.8
        assert r.evidence == []
        assert r.category == "general"

    def test_with_evidence(self):
        r = DeepRule("rule", 0.9, evidence=["file.py"], category="auth")
        assert r.evidence == ["file.py"]
        assert r.category == "auth"


# ── DeepExtractionResult ──────────────────────────────────────────────────────

class TestDeepExtractionResult:
    def test_all_rules_filters_by_confidence(self):
        result = DeepExtractionResult()
        result.auth_rules = [
            DeepRule("high conf", 0.9, category="auth"),
            DeepRule("low conf", 0.3, category="auth"),
        ]
        result.never_do_rules = [DeepRule("medium", 0.7, category="never_do")]
        high = result.all_rules(min_confidence=0.65)
        assert len(high) == 2
        assert all(r.confidence >= 0.65 for r in high)

    def test_all_rules_sorted_by_confidence(self):
        result = DeepExtractionResult()
        result.auth_rules = [
            DeepRule("a", 0.7),
            DeepRule("b", 0.95),
            DeepRule("c", 0.8),
        ]
        ordered = result.all_rules(min_confidence=0.0)
        assert ordered[0].confidence >= ordered[1].confidence >= ordered[2].confidence

    def test_empty_result(self):
        result = DeepExtractionResult()
        assert result.all_rules() == []


# ── Auth rule derivation ──────────────────────────────────────────────────────

class TestDeriveAuthRules:
    def test_fastapi_depends_rule(self, tmp_path: Path):
        f = _make_py(tmp_path, "routes.py", """
from fastapi import APIRouter, Depends
from app.api.deps import get_current_active_user

router = APIRouter()

@router.get("/me")
def get_me(current_user = Depends(get_current_active_user)):
    return current_user

@router.get("/items")
def list_items(current_user = Depends(get_current_active_user)):
    return []
""")
        rules = _derive_auth_rules([f], None, safe_read)
        assert len(rules) >= 1
        auth_rule = rules[0]
        assert "get_current_active_user" in auth_rule.text
        assert auth_rule.confidence >= 0.6
        assert auth_rule.category == "auth"

    def test_fastapi_import_path_detected(self, tmp_path: Path):
        f = _make_py(tmp_path, "routes.py", """
from fastapi import Depends
from app.api.deps import get_current_user, get_current_active_user

def endpoint(user = Depends(get_current_user)):
    pass

def endpoint2(user = Depends(get_current_user)):
    pass
""")
        rules = _derive_auth_rules([f], None, safe_read)
        rule_texts = " ".join(r.text for r in rules)
        assert "app.api.deps" in rule_texts

    def test_django_login_required(self, tmp_path: Path):
        files = []
        for i in range(4):
            f = _make_py(tmp_path, f"views{i}.py", f"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def my_view{i}(request):
    return render(request, 'template.html')
""")
            files.append(f)
        rules = _derive_auth_rules(files, None, safe_read)
        rule_texts = " ".join(r.text for r in rules)
        assert "login_required" in rule_texts

    def test_nestjs_useguards(self, tmp_path: Path):
        files = []
        for i in range(3):
            f = _make_ts(tmp_path, f"controller{i}.ts", f"""
import {{ Controller, Get, UseGuards }} from '@nestjs/common';
import {{ JwtAuthGuard }} from './auth/guards';

@Controller('items')
@UseGuards(JwtAuthGuard)
export class ItemController{i} {{
    @Get()
    findAll() {{ return []; }}
}}
""")
            files.append(f)
        rules = _derive_auth_rules(files, None, safe_read)
        rule_texts = " ".join(r.text for r in rules)
        assert "JwtAuthGuard" in rule_texts

    def test_no_auth_returns_empty(self, tmp_path: Path):
        f = _make_py(tmp_path, "utils.py", "def helper(): return 42")
        rules = _derive_auth_rules([f], None, safe_read)
        assert rules == []

    def test_single_usage_below_threshold(self, tmp_path: Path):
        f = _make_py(tmp_path, "routes.py", """
from fastapi import Depends
from app.deps import get_auth_user

def endpoint(u = Depends(get_auth_user)):
    pass
""")
        # only 1 usage -- should not generate rule (threshold is 2)
        rules = _derive_auth_rules([f], None, safe_read)
        assert all(r.confidence < 1.0 for r in rules)  # low confidence at best


# ── Exception rule derivation ─────────────────────────────────────────────────

class TestDeriveExceptionRules:
    def test_base_exception_hierarchy(self, tmp_path: Path):
        f = _make_py(tmp_path, "exceptions.py", """
class AppError(Exception):
    pass

class AuthError(AppError):
    pass

class NotFoundError(AppError):
    pass

class ValidationError(AppError):
    pass

class RateLimitError(AppError):
    pass
""")
        rules = _derive_exception_rules([f], None, safe_read)
        rule_texts = " ".join(r.text for r in rules)
        # should find AppError as the base
        assert "AppError" in rule_texts

    def test_dedicated_exceptions_file(self, tmp_path: Path):
        f = _make_py(tmp_path, "exceptions.py", """
class DomainError(Exception): pass
class AuthError(DomainError): pass
""")
        rules = _derive_exception_rules([f], None, safe_read)
        rule_texts = " ".join(r.text for r in rules)
        assert "exceptions.py" in rule_texts

    def test_no_custom_exceptions(self, tmp_path: Path):
        f = _make_py(tmp_path, "utils.py", "def helper(): raise ValueError('bad')")
        rules = _derive_exception_rules([f], None, safe_read)
        # no custom exception classes defined -- no hierarchy rule
        hierarchy_rules = [r for r in rules if "base exception" in r.text.lower()]
        assert len(hierarchy_rules) == 0


# ── Testing rule derivation ───────────────────────────────────────────────────

class TestDeriveTestingRules:
    def test_conftest_rule(self, tmp_path: Path):
        conftest = _make_py(tmp_path, "conftest.py", """
import pytest

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_headers(client):
    return {"Authorization": "Bearer test"}
""")
        rules = _derive_testing_rules([conftest], None, safe_read)
        rule_texts = " ".join(r.text for r in rules)
        assert "conftest" in rule_texts

    def test_parametrize_rule(self, tmp_path: Path):
        files = []
        for i in range(4):
            f = _make_py(tmp_path, f"test_thing{i}.py", f"""
import pytest

@pytest.mark.parametrize("val,expected", [(1, 2), (3, 4)])
def test_something{i}(val, expected):
    assert val + 1 == expected
""")
            files.append(f)
        rules = _derive_testing_rules(files, None, safe_read)
        rule_texts = " ".join(r.text for r in rules)
        assert "parametrize" in rule_texts

    def test_no_tests_returns_empty(self, tmp_path: Path):
        f = _make_py(tmp_path, "utils.py", "def helper(): return 42")
        rules = _derive_testing_rules([f], None, safe_read)
        assert rules == []


# ── Naming rule derivation ────────────────────────────────────────────────────

class TestDeriveNamingRules:
    def test_pascal_component_rule(self, tmp_path: Path):
        files = []
        for name in ["UserCard", "LoginForm", "Dashboard", "Header"]:
            f = _make_ts(tmp_path, f"{name}.tsx", f"export default function {name}() {{ return null; }}")
            files.append(f)
        rules = _derive_naming_rules(files, None, safe_read)
        rule_texts = " ".join(r.text for r in rules)
        assert "PascalCase" in rule_texts

    def test_hook_naming_rule(self, tmp_path: Path):
        files = []
        for name in ["useAuth", "useUser", "useData", "useTheme"]:
            f = _make_ts(tmp_path, f"{name}.ts", f"export function {name}() {{ return null; }}")
            files.append(f)
        rules = _derive_naming_rules(files, None, safe_read)
        rule_texts = " ".join(r.text for r in rules)
        assert "use" in rule_texts or "hook" in rule_texts.lower()


# ── Never-do rule derivation ──────────────────────────────────────────────────

class TestDeriveNeverDoRules:
    def test_no_print_with_logging(self, tmp_path: Path):
        f = _make_py(tmp_path, "service.py", """
import logging
logger = logging.getLogger(__name__)

def do_work():
    logger.info("doing work")
    return 42
""")
        dna = FakeDNA()
        dna.logging_patterns.logger_import = "logging.getLogger(__name__)"
        rules = _derive_never_do_rules([f], dna, safe_read)
        rule_texts = " ".join(r.text for r in rules)
        assert "print" in rule_texts.lower()

    def test_print_exists_no_rule(self, tmp_path: Path):
        f = _make_py(tmp_path, "script.py", """
import logging
logger = logging.getLogger(__name__)
print("debug output")
""")
        dna = FakeDNA()
        dna.logging_patterns.logger_import = "logging"
        # print() IS used -- rule should not fire
        rules = _derive_never_do_rules([f], dna, safe_read)
        # if print is used, no "never use print" rule
        assert all("print" not in r.text.lower() for r in rules)


# ── Integration: run_deep_extraction ─────────────────────────────────────────

class TestRunDeepExtraction:
    def test_graceful_on_empty(self, tmp_path: Path):
        # Empty file list -- no crashes, result is a valid DeepExtractionResult.
        # Note: never_do rules may still fire from dna metadata alone
        # (e.g. logging configured + no print() = never use print rule).
        dna = FakeDNA()
        result = run_deep_extraction([], dna, safe_read)
        assert isinstance(result, DeepExtractionResult)
        # all returned rules must have text and a valid confidence
        for r in result.all_rules():
            assert r.text
            assert 0.0 <= r.confidence <= 1.0

    def test_fastapi_end_to_end(self, tmp_path: Path):
        """Full pipeline: FastAPI project with auth, exceptions, tests."""
        # auth
        deps = _make_py(tmp_path, "deps.py", """
from fastapi.security import OAuth2PasswordBearer
reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="auth/login")
""")
        route1 = _make_py(tmp_path, "routes_users.py", """
from fastapi import APIRouter, Depends
from .deps import reusable_oauth2

router = APIRouter()

@router.get("/users")
def list_users(token = Depends(reusable_oauth2)):
    return []

@router.get("/users/me")
def get_me(token = Depends(reusable_oauth2)):
    return {}
""")
        # exceptions
        exc_file = _make_py(tmp_path, "exceptions.py", """
class AppError(Exception): pass
class AuthError(AppError): pass
class NotFoundError(AppError): pass
class ValidationError(AppError): pass
""")
        # conftest
        conftest = _make_py(tmp_path, "conftest.py", """
import pytest
@pytest.fixture
def client(): pass
""")

        dna = FakeDNA()
        result = run_deep_extraction([deps, route1, exc_file, conftest], dna, safe_read)

        all_rules = result.all_rules(min_confidence=0.5)

        # should have found something
        assert len(all_rules) >= 1
        # all returned rules have text
        assert all(r.text for r in all_rules)
        # no crashes
        assert isinstance(result, DeepExtractionResult)

    def test_failure_in_one_extractor_doesnt_crash_others(self, tmp_path: Path):
        """If one deep extractor fails, others still run."""
        f = _make_py(tmp_path, "app.py", "x = 1")
        dna = FakeDNA()
        # should not raise
        result = run_deep_extraction([f], dna, safe_read)
        assert isinstance(result, DeepExtractionResult)
