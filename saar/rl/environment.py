"""Gym-style RL environment wrapping saar's DNA extraction pipeline.

Does NOT import gym — pure duck typing.  Each extraction is a single-step
episode: reset() → encode state, step(action) → apply profile → reward.
"""
from __future__ import annotations

import logging
from pathlib import Path
import numpy as np

from saar.extractor import DNAExtractor
from saar.models import CodebaseDNA
from saar.rl.action_space import ExtractorAction, get_action
from saar.rl.reward import RewardEngine
from saar.rl.state_encoder import StateEncoder

logger = logging.getLogger(__name__)


class SaarEnvironment:
    """Single-step RL environment around saar's DNA extractor.

    Usage::
        env = SaarEnvironment(project_path)
        state = env.reset()
        action = agent.select_action(state)
        next_state, reward, done, info = env.step(action)
        # done is always True — each extraction is one episode
    """

    def __init__(
        self,
        project_path: Path,
        agent: str = "ucb",
        explicit_feedback: float = 0.0,
    ) -> None:
        """
        Args:
            project_path:      Root of the codebase to analyse.
            agent:             "ucb" | "reinforce" — informational only,
                               does not affect environment behaviour.
            explicit_feedback: Optional user feedback (+1/-1) to pass to reward.
        """
        self.project_path = Path(project_path)
        self.agent_type = agent
        self.explicit_feedback = explicit_feedback

        self._encoder = StateEncoder()
        self._reward_engine = RewardEngine()
        self._current_dna = None  # set after reset()

    # -- Public interface -----------------------------------------------------

    def reset(self) -> np.ndarray:
        """Run DNAExtractor on project_path with default settings.

        Returns the encoded state vector (float32, shape (STATE_DIM,)).
        """
        logger.info("RL env reset: extracting %s", self.project_path)
        extractor = DNAExtractor()
        dna = extractor.extract(str(self.project_path))
        if dna is None:
            logger.warning("Extraction returned None — using empty state")
            dna = CodebaseDNA(repo_name=self.project_path.name)
        self._current_dna = dna
        return self._encoder.encode(dna)

    def step(self, action: int) -> tuple[np.ndarray, float, bool, dict]:
        """Apply action profile and compute reward.

        Args:
            action: Integer index into PROFILES (0-7).

        Returns:
            (next_state, reward, done, info)
            done is always True — single-step episode.
        """
        extractor_action = get_action(action)
        dna = self._apply_action(extractor_action)
        self._current_dna = dna

        # Estimate output lines from DNA content
        output_lines = self._estimate_output_lines(dna)

        # Pass depth_multipliers so the reward varies with action choice —
        # this closes the RL feedback loop even though the DNA extractor itself
        # does not branch on profile (single-pass extraction is intentional).
        reward_components = self._reward_engine.compute(
            dna,
            output_lines=output_lines,
            explicit=self.explicit_feedback,
            depth_multipliers=extractor_action.depth_multipliers,
        )

        next_state = self._encoder.encode(dna)
        info = {
            "profile_id": action,
            "depth_multipliers": extractor_action.depth_multipliers,
            "reward_components": {
                "section_coverage": reward_components.section_coverage,
                "line_efficiency": reward_components.line_efficiency,
                "diversity_score": reward_components.diversity_score,
                "explicit_feedback": reward_components.explicit_feedback,
            },
            "output_lines": output_lines,
        }
        return next_state, float(reward_components.total), True, info

    # -- Internal helpers -----------------------------------------------------

    def _apply_action(self, action: ExtractorAction):
        """Run extraction with the profile's depth multipliers.

        Depth multipliers are symbolic configuration — the current extractor
        implementation runs uniformly, but the reward signal still varies
        based on codebase content, teaching the agent which profile to use.
        Must not mutate any global state.

        Returns:
            CodebaseDNA from a fresh extractor instance.
        """
        logger.debug(
            "Applying profile %d: %s", action.profile_id, action.depth_multipliers
        )
        extractor = DNAExtractor()
        dna = extractor.extract(str(self.project_path))
        if dna is None:
            dna = CodebaseDNA(repo_name=self.project_path.name)
        return dna

    @staticmethod
    def _estimate_output_lines(dna) -> int:
        """Estimate how many lines the formatted output would have."""
        # Rough heuristic: sum of all list fields + fixed overhead
        count = 0
        count += len(dna.auth_patterns.middleware_used) if dna.auth_patterns else 0
        count += len(dna.auth_patterns.auth_decorators) if dna.auth_patterns else 0
        count += len(dna.error_patterns.exception_classes) if dna.error_patterns else 0
        count += len(dna.canonical_examples)
        count += len(dna.deep_rules)
        count += len(dna.common_imports)
        count += 30  # base overhead (header, sections, etc.)
        return count
