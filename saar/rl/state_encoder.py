"""State encoder: maps CodebaseDNA to a fixed-length float32 feature vector.

20-dimensional state space:
  0-3:   language mix (python, typescript, javascript, other) as fractions
  4-9:   framework flags (fastapi, django, flask, react, next, express) as 0/1
  10-12: scale (log_file_count, log_function_count, type_coverage)
  13-16: structural (has_tests, has_auth, has_migrations, has_docker)
  17-19: tribal (tribal_rule_count, off_limits_count, async_adoption)
"""
from __future__ import annotations

import logging
import math
from typing import ClassVar

import numpy as np

from saar.models import CodebaseDNA

logger = logging.getLogger(__name__)

_LOG_NORM_MAX: float = math.log1p(10000)


class StateEncoder:
    """Encodes a CodebaseDNA into a float32 feature vector of length STATE_DIM."""

    STATE_DIM: ClassVar[int] = 20

    def encode(self, dna: CodebaseDNA) -> np.ndarray:
        """Return float32 vector of length STATE_DIM, all values in [0, 1].

        Never raises — missing fields default to 0.0.
        """
        try:
            return self._encode_safe(dna)
        except Exception as e:
            logger.warning("State encoding failed, returning zeros: %s", e)
            return np.zeros(self.STATE_DIM, dtype=np.float32)

    def _encode_safe(self, dna: CodebaseDNA) -> np.ndarray:
        vec = np.zeros(self.STATE_DIM, dtype=np.float32)

        # -- Language mix (dims 0-3) ------------------------------------------
        lang = dna.language_distribution or {}
        total_files = max(sum(lang.values()), 1)
        vec[0] = lang.get("python", 0) / total_files
        vec[1] = lang.get("typescript", 0) / total_files
        vec[2] = lang.get("javascript", 0) / total_files
        other = sum(v for k, v in lang.items() if k not in {"python", "typescript", "javascript"})
        vec[3] = other / total_files

        # -- Framework flags (dims 4-9) ----------------------------------------
        fw = (dna.detected_framework or "").lower()
        vec[4] = 1.0 if "fastapi" in fw else 0.0
        vec[5] = 1.0 if "django" in fw else 0.0
        vec[6] = 1.0 if "flask" in fw else 0.0
        fp = dna.frontend_patterns
        vec[7] = 1.0 if (fp and fp.framework in {"react", "next"}) else 0.0
        vec[8] = 1.0 if (fp and fp.framework == "next") else 0.0
        vec[9] = 1.0 if "express" in fw else 0.0

        # -- Scale (dims 10-12) -----------------------------------------------
        file_count = sum(lang.values())
        vec[10] = min(math.log1p(file_count) / _LOG_NORM_MAX, 1.0)
        vec[11] = min(math.log1p(max(dna.total_functions, 0)) / _LOG_NORM_MAX, 1.0)
        vec[12] = min(max(dna.type_hint_pct, 0.0) / 100.0, 1.0)

        # -- Structural (dims 13-16) ------------------------------------------
        tp = dna.test_patterns
        vec[13] = 1.0 if (tp and tp.framework) else 0.0
        auth = dna.auth_patterns
        vec[14] = 1.0 if (auth and (auth.middleware_used or auth.auth_decorators)) else 0.0
        db = dna.database_patterns
        vec[15] = 1.0 if (db and db.orm_used) else 0.0
        ps = dna.project_structure or ""
        vec[16] = 1.0 if ("Dockerfile" in ps or "docker-compose" in ps) else 0.0

        # -- Tribal (dims 17-19) ----------------------------------------------
        interview = dna.interview
        never_do_lines = len((interview.never_do or "").splitlines()) if interview else 0
        off_limits_lines = len((interview.off_limits or "").splitlines()) if interview else 0
        tribal_total = len(dna.deep_rules) + never_do_lines
        vec[17] = min(math.log1p(tribal_total) / _LOG_NORM_MAX, 1.0)
        vec[18] = min(math.log1p(off_limits_lines) / _LOG_NORM_MAX, 1.0)
        vec[19] = min(max(dna.async_adoption_pct, 0.0) / 100.0, 1.0)

        np.clip(vec, 0.0, 1.0, out=vec)
        return vec

    def feature_names(self) -> list[str]:
        """Return list of 20 strings, one per feature dim."""
        return [
            "python_frac",
            "typescript_frac",
            "javascript_frac",
            "other_frac",
            "has_fastapi",
            "has_django",
            "has_flask",
            "has_react",
            "has_next",
            "has_express",
            "log_file_count",
            "log_function_count",
            "type_coverage",
            "has_tests",
            "has_auth",
            "has_migrations",
            "has_docker",
            "tribal_rule_count",
            "off_limits_count",
            "async_adoption",
        ]
