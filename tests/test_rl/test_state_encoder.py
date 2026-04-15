"""Tests for saar/rl/state_encoder.py."""
from __future__ import annotations

import numpy as np
import pytest

from saar.models import (
    AuthPattern,
    CodebaseDNA,
    ErrorPattern,
    InterviewAnswers,
    TestPattern,
)
from saar.rl.state_encoder import StateEncoder


def _minimal_dna(**kwargs) -> CodebaseDNA:
    defaults = dict(repo_name="test")
    defaults.update(kwargs)
    return CodebaseDNA(**defaults)


class TestStateEncoder:
    def setup_method(self) -> None:
        self.enc = StateEncoder()

    def test_encode_returns_correct_shape(self) -> None:
        dna = _minimal_dna()
        vec = self.enc.encode(dna)
        assert vec.shape == (StateEncoder.STATE_DIM,)
        assert vec.dtype == np.float32

    def test_encode_all_zeros_for_empty_dna(self) -> None:
        dna = _minimal_dna()
        vec = self.enc.encode(dna)
        # Must not raise; result should be valid floats
        assert not np.any(np.isnan(vec))

    def test_encode_values_in_range(self) -> None:
        dna = CodebaseDNA(
            repo_name="rich",
            detected_framework="fastapi",
            language_distribution={"python": 80, "typescript": 10, "javascript": 5},
            auth_patterns=AuthPattern(middleware_used=["oauth2"], auth_decorators=["@login_required"]),
            error_patterns=ErrorPattern(exception_classes=["AppError", "AuthError"]),
            test_patterns=TestPattern(framework="pytest"),
            total_functions=500,
            type_hint_pct=85.0,
            async_adoption_pct=40.0,
            deep_rules=[{"text": "rule1", "confidence": 0.9, "category": "auth", "evidence": []}],
            interview=InterviewAnswers(never_do="do not do X\ndo not do Y", off_limits="saar/models.py"),
        )
        vec = self.enc.encode(dna)
        assert np.all(vec >= 0.0), f"Values below 0: {vec[vec < 0.0]}"
        assert np.all(vec <= 1.0), f"Values above 1: {vec[vec > 1.0]}"

    def test_feature_names_length_matches_state_dim(self) -> None:
        names = self.enc.feature_names()
        assert len(names) == StateEncoder.STATE_DIM
        assert all(isinstance(n, str) for n in names)

    def test_language_fractions_sum_to_one(self) -> None:
        dna = _minimal_dna(language_distribution={"python": 60, "typescript": 30, "javascript": 10})
        vec = self.enc.encode(dna)
        # dims 0-3 are python, ts, js, other → should sum to 1
        assert abs(float(vec[0]) + float(vec[1]) + float(vec[2]) + float(vec[3]) - 1.0) < 1e-5

    def test_framework_flags_fastapi(self) -> None:
        dna = _minimal_dna(detected_framework="fastapi")
        vec = self.enc.encode(dna)
        assert vec[4] == pytest.approx(1.0)  # has_fastapi
        assert vec[5] == pytest.approx(0.0)  # has_django

    def test_handles_missing_interview_gracefully(self) -> None:
        dna = _minimal_dna(interview=None)
        vec = self.enc.encode(dna)
        assert not np.any(np.isnan(vec))
        assert vec[17] == pytest.approx(0.0)
        assert vec[18] == pytest.approx(0.0)
