"""Backend pattern extractors: framework, auth, DB, errors, logging, services.

All functions take a `read_file` callable instead of using `self._safe_read_file`
directly. This keeps them testable in isolation and decoupled from DNAExtractor state.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from pathlib import Path
from typing import Callable, List, Optional

from saar.models import AuthPattern, DatabasePattern, ErrorPattern, LoggingPattern, ServicePattern

logger = logging.getLogger(__name__)

ReadFile = Callable[[Path], Optional[str]]


def detect_framework(files: List[Path], read_file: ReadFile) -> Optional[str]:
    """Detect primary framework from actual imports (line-start anchored)."""
    py_indicators = {
        "fastapi": [r"^from fastapi\b", r"^import fastapi\b"],
        "django-rest-framework": [r"^from rest_framework\b"],
        "django": [r"^from django\b", r"^import django\b"],
        "flask": [r"^from flask\b", r"^import flask\b"],
    }
    js_indicators = {
        "express": [r"require\(['\"]express['\"]\)", r"from ['\"]express['\"]"],
        "nextjs": [r"^import\s+.*from\s+.next/"],
        "nestjs": [r"^import\s+.*from\s+.@nestjs/"],
    }
    py_exts = {".py"}
    js_exts = {".js", ".jsx", ".ts", ".tsx"}
    scores: Counter = Counter()

    for file_path in files:
        content = read_file(file_path)
        if not content:
            continue
        ext = file_path.suffix.lower()
        active = py_indicators if ext in py_exts else (js_indicators if ext in js_exts else None)
        if not active:
            continue
        for framework, patterns in active.items():
            for pattern in patterns:
                if re.search(pattern, content, re.MULTILINE):
                    scores[framework] += 1

    if not scores:
        return None
    top = scores.most_common(1)[0][0]
    return "django + DRF" if top == "django-rest-framework" else top


def extract_auth_patterns(files: List[Path], read_file: ReadFile, framework: Optional[str] = None) -> AuthPattern:
    """Detect auth middleware, decorators, and ownership checks."""
    pattern = AuthPattern()

    for file_path in files:
        if file_path.suffix != ".py":
            continue
        content = read_file(file_path)
        if not content:
            continue

        if re.search(r"^def require_auth\b", content, re.MULTILINE):
            pattern.middleware_used.append("require_auth")
        if re.search(r"^def public_auth\b", content, re.MULTILINE):
            pattern.middleware_used.append("public_auth")
        if "Depends(" in content and re.search(r"^from fastapi", content, re.MULTILINE):
            for dep in re.findall(r"Depends\((\w+)\)", content):
                if "auth" in dep.lower():
                    pattern.auth_decorators.append(f"Depends({dep})")
        if re.search(r"^from starlette.*AuthenticationMiddleware", content, re.MULTILINE):
            pattern.middleware_used.append("AuthenticationMiddleware")
        if re.search(r"^class AuthContext\b", content, re.MULTILINE):
            pattern.auth_context_type = "AuthContext"
        if re.search(r"^from flask", content, re.MULTILINE):
            if "login_required" in content:
                pattern.auth_decorators.append("@login_required")
            if "flask_login" in content:
                pattern.middleware_used.append("flask_login")
        if re.search(r"^from django", content, re.MULTILINE):
            if "@login_required" in content:
                pattern.auth_decorators.append("@login_required")
            if "permission_required" in content:
                pattern.auth_decorators.append("@permission_required")
            if "request.user" in content:
                pattern.auth_context_type = "request.user"
            if "IsAuthenticated" in content:
                pattern.auth_decorators.append("IsAuthenticated")
        if re.search(r"^def verify_ownership\b", content, re.MULTILINE):
            pattern.ownership_checks.append("verify_ownership")

    for file_path in files:
        if file_path.suffix not in (".ts", ".tsx"):
            continue
        content = read_file(file_path)
        if not content or not re.search(r"from '@nestjs/", content):
            continue
        for g in re.findall(r"@UseGuards\((\w+)\)", content):
            pattern.auth_decorators.append(f"@UseGuards({g})")
        if "JwtAuthGuard" in content:
            pattern.middleware_used.append("JwtAuthGuard")
        if "@Public()" in content:
            pattern.auth_decorators.append("@Public()")

    pattern.middleware_used = sorted(set(pattern.middleware_used))
    pattern.auth_decorators = sorted(set(pattern.auth_decorators))
    pattern.ownership_checks = sorted(set(pattern.ownership_checks))
    return pattern


def extract_error_patterns(files: List[Path], read_file: ReadFile) -> ErrorPattern:
    """Detect custom exception classes and HTTP error usage."""
    pattern = ErrorPattern()
    for file_path in files:
        if file_path.suffix != ".py":
            continue
        content = read_file(file_path)
        if not content:
            continue
        if re.search(r"^from.*import.*HTTPException", content, re.MULTILINE):
            pattern.http_exception_usage = True
        if "logger.error" in content and "except" in content:
            pattern.logging_on_error = True
        for match in re.finditer(r"^class\s+(\w+(?:Error|Exception))\s*\(", content, re.MULTILINE):
            name = match.group(1)
            if not (name.endswith("Pattern") or name.startswith("Test")):
                pattern.exception_classes.append(name)
    pattern.exception_classes = sorted(set(pattern.exception_classes))
    return pattern


def extract_logging_patterns(files: List[Path], read_file: ReadFile) -> LoggingPattern:
    """Detect logging library and usage patterns."""
    pattern = LoggingPattern()
    levels: set = set()
    for file_path in files:
        if file_path.suffix != ".py":
            continue
        content = read_file(file_path)
        if not content:
            continue
        if re.search(r"^.*logging\.getLogger", content, re.MULTILINE):
            pattern.logger_import = "logging.getLogger(__name__)"
        elif re.search(r"^import logging\b", content, re.MULTILINE) and not pattern.logger_import:
            pattern.logger_import = "import logging"
        if re.search(r"^import structlog\b|^from structlog\b", content, re.MULTILINE):
            pattern.structured_logging = True
            pattern.logger_import = "structlog"
        for level in ("debug", "info", "warning", "error", "critical"):
            if f"logger.{level}" in content:
                levels.add(level)
    pattern.log_levels_used = list(levels)
    return pattern


def extract_service_patterns(files: List[Path], repo_path: Path, read_file: ReadFile) -> ServicePattern:
    """Detect singleton services and dependency injection patterns."""
    pattern = ServicePattern()
    deps_file = repo_path / "dependencies.py"
    if deps_file.exists():
        pattern.dependencies_file = "dependencies.py"
        content = read_file(deps_file)
        if content:
            for var_name, class_name in re.findall(r"^(\w+)\s*=\s*(\w+)\(\)", content, re.MULTILINE):
                pattern.singleton_services.append(f"{var_name} = {class_name}()")
            pattern.injection_pattern = "Singleton in dependencies.py"
    services_dir = repo_path / "services"
    if services_dir.exists():
        for service_file in sorted(services_dir.glob("*.py")):
            if not service_file.name.startswith("_"):
                content = read_file(service_file)
                if content:
                    pattern.service_base_classes.extend(re.findall(r"^class\s+(\w+)", content, re.MULTILINE))
    return pattern
"""Database pattern extractor and middleware pattern extractor."""
def extract_database_patterns(files: List[Path], repo_path: Path, read_file: ReadFile) -> DatabasePattern:
    """Detect ORM, connection patterns, and DB conventions."""
    pattern = DatabasePattern()

    for file_path in files:
        content = read_file(file_path)
        if not content:
            continue

        if file_path.suffix == ".sql":
            if "gen_random_uuid()" in content: pattern.id_type = "UUID (gen_random_uuid())"
            elif "SERIAL" in content: pattern.id_type = "SERIAL"
            if "TIMESTAMPTZ" in content: pattern.timestamp_type = "TIMESTAMPTZ"
            elif "TIMESTAMP" in content: pattern.timestamp_type = "TIMESTAMP"
            if "ENABLE ROW LEVEL SECURITY" in content: pattern.has_rls = True
            if "ON DELETE CASCADE" in content: pattern.cascade_deletes = True
            continue

        if file_path.suffix != ".py":
            continue

        if re.search(r"^from supabase\b|^import supabase\b", content, re.MULTILINE):
            if not pattern.orm_used: pattern.orm_used = "Supabase"
            if "get_supabase_service()" in content:
                pattern.connection_pattern = "Singleton: get_supabase_service()"
            elif "create_client(" in content and not pattern.connection_pattern:
                pattern.connection_pattern = "Direct: create_client()"

        if re.search(r"^from django\.db import models", content, re.MULTILINE):
            pattern.orm_used = "Django ORM"
            if "models.UUIDField" in content: pattern.id_type = "UUID (Django UUIDField)"
            elif "models.AutoField" in content or "models.BigAutoField" in content: pattern.id_type = "AutoField (Django)"
            if "models.DateTimeField" in content: pattern.timestamp_type = "DateTimeField (Django)"
            if "on_delete=models.CASCADE" in content: pattern.cascade_deletes = True

        if re.search(r"^from django", content, re.MULTILINE) or re.search(r"^import django\b", content, re.MULTILINE):
            if "DATABASES" in content and not pattern.connection_pattern:
                pattern.connection_pattern = "Django DATABASES setting"
            if not pattern.orm_used and "models.Model" in content:
                pattern.orm_used = "Django ORM"

        if re.search(r"^from sqlalchemy\b", content, re.MULTILINE):
            if not pattern.orm_used: pattern.orm_used = "SQLAlchemy"
            if "UUID" in content: pattern.id_type = "UUID (SQLAlchemy)"
            if "DateTime" in content: pattern.timestamp_type = "DateTime (SQLAlchemy)"
            if "create_engine(" in content: pattern.connection_pattern = "SQLAlchemy: create_engine()"

        if re.search(r"^from tortoise\b|^from tortoise\.models\b", content, re.MULTILINE):
            if not pattern.orm_used: pattern.orm_used = "Tortoise ORM"

        if re.search(r"^from mongoengine\b|^import mongoengine\b", content, re.MULTILINE):
            if not pattern.orm_used: pattern.orm_used = "MongoEngine"

        if re.search(r"^from motor\b|^import motor\b", content, re.MULTILINE):
            if not pattern.orm_used: pattern.orm_used = "Motor (async MongoDB)"

    for file_path in files:
        if file_path.suffix not in (".js", ".ts", ".tsx", ".jsx"): continue
        content = read_file(file_path)
        if content and re.search(r"^import\b.*@prisma/client", content, re.MULTILINE):
            if not pattern.orm_used: pattern.orm_used = "Prisma"
            break

    return pattern


def extract_middleware_patterns(files: List[Path], framework: Optional[str], read_file: ReadFile) -> List[str]:
    """Detect middleware class definitions and registration patterns."""
    patterns: List[str] = []
    for file_path in files:
        content = read_file(file_path)
        if not content: continue
        for match in re.finditer(r"^class\s+(\w*Middleware\w*)", content, re.MULTILINE):
            patterns.append(match.group(1))
        if "app.add_middleware" in content: patterns.append("app.add_middleware()")
        if "app.use(" in content: patterns.append("app.use(middleware)")
        if "MIDDLEWARE" in content and "django" in content.lower():
            for mw in re.findall(r"['\"][\w.]*Middleware[\w.]*['\"]", content)[:3]:
                patterns.append(mw.strip("'\"").split(".")[-1])
        if re.search(r"^import.*from '@nestjs/", content, re.MULTILINE):
            if "NestFactory" in content and "app.use(" in content:
                patterns.extend(re.findall(r"app\.use\((\w+)", content)[:3])
    return sorted(set(patterns))
