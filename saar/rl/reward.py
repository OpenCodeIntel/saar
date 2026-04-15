"""Reward engine for the saar RL layer.

Composite reward in [-1, 1] from four components:
  section_coverage  (0.4) — profile-weighted fraction of detected DNA sections
  line_efficiency   (0.3) — how close actual_lines is to budget
  diversity_score   (0.2) — breadth of detected patterns, weighted by profile
  explicit_feedback (0.1) — +1/-1 from `saar rate good/bad`, else 0

Profile depth_multipliers (from action_space.PROFILES) are applied to the
coverage and diversity scores so the reward genuinely varies with action
choice — this closes the RL feedback loop without modifying DNAExtractor.

Section → extractor mapping:
  stack        → ["api", "services"]
  auth         → ["auth", "middleware"]
  exceptions   → ["errors"]
  conventions  → ["naming"]
  verification → ["tests"]
  off_limits   → ["config"]
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import ClassVar, Optional

from saar.models import CodebaseDNA

logger = logging.getLogger(__name__)

# Pattern counts used to normalise diversity score
_MAX_DIVERSITY_PATTERNS: int = 20

# Maps each DNA section → extractor keys whose multipliers apply to it
_SECTION_EXTRACTOR_MAP: dict[str, list[str]] = {
    "stack":        ["api", "services"],
    "auth":         ["auth", "middleware"],
    "exceptions":   ["errors"],
    "conventions":  ["naming"],
    "verification": ["tests"],
    "off_limits":   ["config"],
}

# Maps diversity component → extractor key
_DIVERSITY_EXTRACTOR_MAP: dict[str, str] = {
    "auth_middleware": "auth",
    "auth_decorators": "auth",
    "exception_classes": "errors",
    "canonical_examples": "imports",
    "deep_rules": "naming",
}


def _section_weight(section: str, depth_multipliers: dict[str, float]) -> float:
    """Return the mean multiplier for a section's extractor keys."""
    keys = _SECTION_EXTRACTOR_MAP.get(section, [])
    if not keys:
        return 1.0
    return sum(depth_multipliers.get(k, 1.0) for k in keys) / len(keys)


@dataclass
class RewardComponents:
    """Breakdown of each reward term plus the weighted total."""

    section_coverage: float
    line_efficiency: float
    diversity_score: float
    explicit_feedback: float
    total: float


class RewardEngine:
    """Compute a scalar reward signal from a completed extraction.

    When ``depth_multipliers`` are provided (from an ExtractorAction profile),
    the section coverage and diversity scores are profile-weighted so that the
    reward differentiates between actions even when the underlying DNA is
    identical.  This allows agents to learn which profile best fits each
    codebase type purely from reward signal.
    """

    WEIGHTS: ClassVar[dict[str, float]] = {
        "section_coverage": 0.4,
        "line_efficiency": 0.3,
        "diversity_score": 0.2,
        "explicit_feedback": 0.1,
    }

    def compute(
        self,
        dna: CodebaseDNA,
        output_lines: int,
        budget: int = 100,
        explicit: float = 0.0,
        depth_multipliers: Optional[dict[str, float]] = None,
    ) -> RewardComponents:
        """Compute reward from extraction result.

        Args:
            dna:               Extracted CodebaseDNA.
            output_lines:      Actual lines in the generated output file.
            budget:            Target line count (default 100).
            explicit:          +1.0 or -1.0 from user feedback, 0.0 if none.
            depth_multipliers: Profile multipliers from ExtractorAction.  When
                               provided, coverage and diversity are weighted so
                               the reward varies meaningfully with action choice.

        Returns:
            RewardComponents with each term and weighted total in [-1, 1].
        """
        dm = depth_multipliers or {}
        sc = self._section_coverage(dna, dm)
        le = self._line_efficiency(output_lines, budget)
        ds = self._diversity_score(dna, dm)
        ef = float(max(-1.0, min(1.0, explicit)))

        total = (
            self.WEIGHTS["section_coverage"] * sc
            + self.WEIGHTS["line_efficiency"] * le
            + self.WEIGHTS["diversity_score"] * ds
            + self.WEIGHTS["explicit_feedback"] * ef
        )
        # Normalise to [-1, 1]: components sc, le, ds are in [0,1], ef in [-1,1].
        # Max positive = 0.4*1 + 0.3*1 + 0.2*1 + 0.1*1 = 1.0
        # Min = 0 + 0 + 0 + 0.1*(-1) = -0.1
        # Shift/scale so range is [-1, 1] for cleaner reward signal
        total = max(-1.0, min(1.0, total * 2.0 - 1.0))

        return RewardComponents(
            section_coverage=sc,
            line_efficiency=le,
            diversity_score=ds,
            explicit_feedback=ef,
            total=total,
        )

    def _section_coverage(
        self, dna: CodebaseDNA, depth_multipliers: dict[str, float]
    ) -> float:
        """Profile-weighted fraction of detected DNA sections.

        Each section contributes its _section_weight(profile) to the total.
        Sections present in the DNA contribute their weight to the numerator.
        This makes the score high when the profile's high-weight sections are
        present and low when they are absent — rewarding profile/codebase fit.
        """
        auth = dna.auth_patterns
        err = dna.error_patterns
        nc = dna.naming_conventions
        interview = dna.interview

        sections_present: dict[str, bool] = {
            "stack":        bool(dna.detected_framework or dna.language_distribution),
            "auth":         bool(auth and (auth.middleware_used or auth.auth_decorators)),
            "exceptions":   bool(err and err.exception_classes),
            "conventions":  bool(nc and nc.function_style != "unknown"),
            "verification": bool(dna.verify_workflow),
            "off_limits":   bool(interview and interview.off_limits),
        }

        weighted_present = 0.0
        total_weight = 0.0
        for section, present in sections_present.items():
            w = _section_weight(section, depth_multipliers)
            total_weight += w
            if present:
                weighted_present += w

        return weighted_present / total_weight if total_weight > 0 else 0.0

    def _line_efficiency(self, actual: int, budget: int) -> float:
        """Score how close actual is to budget.  1.0 = exactly on budget."""
        if budget <= 0:
            return 1.0
        efficiency = 1.0 - abs(actual - budget) / budget
        return float(max(0.0, min(1.0, efficiency)))

    def _diversity_score(
        self, dna: CodebaseDNA, depth_multipliers: dict[str, float]
    ) -> float:
        """Profile-weighted breadth of detected patterns.

        Each pattern type is scaled by the multiplier for its extractor,
        rewarding profiles that prioritise what the codebase actually has.
        """
        score = 0.0

        auth = dna.auth_patterns
        if auth:
            auth_w = depth_multipliers.get("auth", 1.0)
            score += len(auth.middleware_used) * auth_w
            score += len(auth.auth_decorators) * auth_w

        err = dna.error_patterns
        if err:
            err_w = depth_multipliers.get("errors", 1.0)
            score += len(err.exception_classes) * err_w

        import_w = depth_multipliers.get("imports", 1.0)
        score += len(dna.canonical_examples) * import_w

        naming_w = depth_multipliers.get("naming", 1.0)
        score += len(dna.deep_rules) * naming_w

        return float(min(score / _MAX_DIVERSITY_PATTERNS, 1.0))
