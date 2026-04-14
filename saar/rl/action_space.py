"""Action space for the saar RL layer.

K=8 configuration profiles, each mapping extractor name → depth multiplier.
Extractor names correspond to the logical extraction functions in saar/extractors/:
  auth, database, errors, logging, services, naming, imports,
  api, tests, frontend, config, middleware

Depth multiplier semantics:
  2.0 → prioritize this extractor (extra passes, deeper scanning)
  1.0 → baseline behaviour
  0.5 → reduced priority (fewer files scanned for this pattern)
"""
from __future__ import annotations

from dataclasses import dataclass

# K = number of discrete profiles (actions)
N_ACTIONS: int = 8

# Canonical extractor names derived from saar/extractors/ modules
_EXTRACTOR_NAMES: tuple[str, ...] = (
    "auth",
    "database",
    "errors",
    "logging",
    "services",
    "naming",
    "imports",
    "api",
    "tests",
    "frontend",
    "config",
    "middleware",
)

# Profile 0: Python backend heavy (FastAPI / Django / Flask)
_PROFILE_0: dict[str, float] = {
    "auth": 2.0,
    "database": 2.0,
    "errors": 2.0,
    "services": 2.0,
    "middleware": 1.5,
    "api": 1.5,
    "logging": 1.0,
    "naming": 1.0,
    "imports": 1.0,
    "tests": 1.0,
    "config": 1.0,
    "frontend": 0.5,
}

# Profile 1: TypeScript / React heavy (Next.js, SPAs)
_PROFILE_1: dict[str, float] = {
    "frontend": 2.0,
    "naming": 2.0,
    "imports": 2.0,
    "api": 1.5,
    "tests": 1.0,
    "config": 1.0,
    "errors": 1.0,
    "auth": 0.5,
    "database": 0.5,
    "logging": 0.5,
    "services": 0.5,
    "middleware": 0.5,
}

# Profile 2: Full-stack balanced (equal weight, slight frontend + API boost)
_PROFILE_2: dict[str, float] = {
    "auth": 1.0,
    "database": 1.0,
    "errors": 1.0,
    "logging": 1.0,
    "services": 1.0,
    "naming": 1.0,
    "imports": 1.0,
    "api": 1.5,
    "tests": 1.0,
    "frontend": 1.5,
    "config": 1.0,
    "middleware": 1.0,
}

# Profile 3: Small script / utility (no auth/DB, focus on naming and imports)
_PROFILE_3: dict[str, float] = {
    "naming": 2.0,
    "imports": 2.0,
    "errors": 1.0,
    "tests": 1.0,
    "config": 1.0,
    "logging": 0.5,
    "auth": 0.5,
    "database": 0.5,
    "services": 0.5,
    "api": 0.5,
    "frontend": 0.5,
    "middleware": 0.5,
}

# Profile 4: Monorepo / large codebase (services, tests, config, imports)
_PROFILE_4: dict[str, float] = {
    "services": 2.0,
    "tests": 2.0,
    "config": 2.0,
    "imports": 1.5,
    "api": 1.5,
    "auth": 1.0,
    "database": 1.0,
    "errors": 1.0,
    "logging": 1.0,
    "naming": 1.0,
    "frontend": 1.0,
    "middleware": 1.0,
}

# Profile 5: API-only / microservice (api, auth, middleware, errors, config)
_PROFILE_5: dict[str, float] = {
    "api": 2.0,
    "auth": 2.0,
    "middleware": 2.0,
    "errors": 2.0,
    "config": 2.0,
    "database": 1.5,
    "services": 1.5,
    "logging": 1.5,
    "naming": 1.0,
    "imports": 1.0,
    "tests": 1.0,
    "frontend": 0.5,
}

# Profile 6: Data / ML codebase (imports, naming, config, logging)
_PROFILE_6: dict[str, float] = {
    "imports": 2.0,
    "naming": 2.0,
    "config": 2.0,
    "logging": 1.5,
    "database": 1.5,
    "errors": 1.0,
    "services": 1.0,
    "tests": 1.0,
    "auth": 0.5,
    "api": 0.5,
    "frontend": 0.5,
    "middleware": 0.5,
}

# Profile 7: Legacy / mixed (errors, logging, database; weak tests/frontend)
_PROFILE_7: dict[str, float] = {
    "errors": 2.0,
    "logging": 2.0,
    "database": 1.5,
    "imports": 1.5,
    "auth": 1.0,
    "services": 1.0,
    "api": 1.0,
    "naming": 1.0,
    "config": 1.0,
    "middleware": 1.0,
    "tests": 0.5,
    "frontend": 0.5,
}

PROFILES: dict[int, dict[str, float]] = {
    0: _PROFILE_0,
    1: _PROFILE_1,
    2: _PROFILE_2,
    3: _PROFILE_3,
    4: _PROFILE_4,
    5: _PROFILE_5,
    6: _PROFILE_6,
    7: _PROFILE_7,
}


@dataclass
class ExtractorAction:
    """A chosen configuration profile for an extraction run."""

    profile_id: int
    depth_multipliers: dict[str, float]  # extractor_name → multiplier


def get_action(profile_id: int) -> ExtractorAction:
    """Return the ExtractorAction for the given profile_id (0-7)."""
    if profile_id not in PROFILES:
        raise ValueError(f"Invalid profile_id {profile_id}. Must be 0..{N_ACTIONS - 1}.")
    return ExtractorAction(profile_id=profile_id, depth_multipliers=dict(PROFILES[profile_id]))


def action_count() -> int:
    """Return total number of discrete actions (K=8)."""
    return N_ACTIONS
