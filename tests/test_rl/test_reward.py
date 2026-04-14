"""Tests for saar/rl/reward.py."""
from __future__ import annotations

import pytest

from saar.models import (
    AuthPattern,
    CodebaseDNA,
    ErrorPattern,
    InterviewAnswers,
    NamingConventions,
)
from saar.rl.reward import RewardEngine


def _minimal_dna(**kwargs) -> CodebaseDNA:
    defaults = dict(repo_name="test")
    defaults.update(kwargs)
    return CodebaseDNA(**defaults)


def _full_dna() -> CodebaseDNA:
    """DNA with all six expected sections populated."""
    return CodebaseDNA(
        repo_name="full",
        detected_framework="fastapi",
        language_distribution={"python": 100},
        auth_patterns=AuthPattern(middleware_used=["oauth2"]),
        error_patterns=ErrorPattern(exception_classes=["AppError"]),
        naming_conventions=NamingConventions(function_style="snake_case"),
        verify_workflow="pytest tests/ -q",
        interview=InterviewAnswers(off_limits="saar/models.py"),
    )


class TestRewardEngine:
    def setup_method(self) -> None:
        self.engine = RewardEngine()

    def test_reward_in_valid_range(self) -> None:
        for explicit in (-1.0, 0.0, 1.0):
            for lines in (0, 50, 100, 200):
                r = self.engine.compute(_minimal_dna(), output_lines=lines, budget=100, explicit=explicit)
                assert -1.0 <= r.total <= 1.0, f"total={r.total} out of range"

    def test_section_coverage_full(self) -> None:
        dna = _full_dna()
        r = self.engine.compute(dna, output_lines=100)
        assert r.section_coverage == pytest.approx(1.0)

    def test_section_coverage_empty(self) -> None:
        dna = _minimal_dna()
        r = self.engine.compute(dna, output_lines=100)
        # Only "stack" section can be present (empty language_distribution is falsy — let's check)
        # Actually empty language_distribution is falsy ({}), so stack is absent too
        assert r.section_coverage == pytest.approx(0.0)

    def test_line_efficiency_at_budget(self) -> None:
        r = self.engine.compute(_minimal_dna(), output_lines=100, budget=100)
        assert r.line_efficiency == pytest.approx(1.0)

    def test_line_efficiency_half_budget(self) -> None:
        r = self.engine.compute(_minimal_dna(), output_lines=50, budget=100)
        assert r.line_efficiency == pytest.approx(0.5)

    def test_explicit_feedback_propagates(self) -> None:
        r_good = self.engine.compute(_minimal_dna(), output_lines=100, explicit=1.0)
        r_bad = self.engine.compute(_minimal_dna(), output_lines=100, explicit=-1.0)
        r_none = self.engine.compute(_minimal_dna(), output_lines=100, explicit=0.0)
        # Explicit feedback should shift total reward
        assert r_good.total > r_none.total
        assert r_bad.total < r_none.total
        assert r_good.explicit_feedback == pytest.approx(1.0)
        assert r_bad.explicit_feedback == pytest.approx(-1.0)

    def test_diversity_score_zero_on_empty(self) -> None:
        r = self.engine.compute(_minimal_dna(), output_lines=100)
        assert r.diversity_score == pytest.approx(0.0)

    def test_diversity_score_nonzero_with_patterns(self) -> None:
        dna = _minimal_dna(
            auth_patterns=AuthPattern(middleware_used=["oauth2", "jwt"]),
            error_patterns=ErrorPattern(exception_classes=["AppError", "AuthError"]),
        )
        r = self.engine.compute(dna, output_lines=100)
        assert r.diversity_score > 0.0

    def test_depth_multipliers_change_reward(self) -> None:
        """Reward must differ when depth_multipliers vary (RL loop is closed)."""
        dna = _full_dna()
        r_backend = self.engine.compute(
            dna, output_lines=100,
            depth_multipliers={"auth": 2.0, "api": 2.0, "errors": 2.0,
                                "services": 2.0, "middleware": 1.5,
                                "naming": 1.0, "imports": 1.0, "tests": 1.0,
                                "config": 1.0, "frontend": 0.5,
                                "database": 2.0, "logging": 1.0},
        )
        r_script = self.engine.compute(
            dna, output_lines=100,
            depth_multipliers={"naming": 2.0, "imports": 2.0, "errors": 1.0,
                                "tests": 1.0, "config": 1.0, "logging": 0.5,
                                "auth": 0.5, "database": 0.5, "services": 0.5,
                                "api": 0.5, "frontend": 0.5, "middleware": 0.5},
        )
        assert r_backend.total != r_script.total

    def test_high_auth_multiplier_boosts_auth_rich_dna(self) -> None:
        """A profile with high auth weight should score higher on auth-rich DNA."""
        dna_auth = _minimal_dna(
            auth_patterns=AuthPattern(middleware_used=["oauth2", "jwt", "bearer"]),
            detected_framework="fastapi",
            language_distribution={"python": 80},
        )
        high_auth_dm = {k: 1.0 for k in
                        ["auth", "database", "errors", "logging", "services",
                         "naming", "imports", "api", "tests", "frontend",
                         "config", "middleware"]}
        high_auth_dm.update({"auth": 2.0, "middleware": 2.0})

        low_auth_dm = dict(high_auth_dm)
        low_auth_dm.update({"auth": 0.5, "middleware": 0.5})

        r_high = self.engine.compute(dna_auth, output_lines=100, depth_multipliers=high_auth_dm)
        r_low = self.engine.compute(dna_auth, output_lines=100, depth_multipliers=low_auth_dm)
        assert r_high.total > r_low.total

    def test_no_multipliers_same_as_empty_dict(self) -> None:
        dna = _full_dna()
        r_none = self.engine.compute(dna, output_lines=100)
        r_empty = self.engine.compute(dna, output_lines=100, depth_multipliers={})
        assert r_none.total == pytest.approx(r_empty.total)
