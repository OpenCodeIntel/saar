"""Synthetic episode generator for offline pre-training.

Produces (state, oracle_action, reward) tuples from procedurally generated
codebase feature vectors. The oracle maps state features to the "best"
profile deterministically, then adds Gaussian noise (σ=0.1) to rewards.

State vector layout (matches StateEncoder.feature_names()):
  0: python_frac    1: typescript_frac   2: javascript_frac  3: other_frac
  4: has_fastapi    5: has_django        6: has_flask
  7: has_react      8: has_next          9: has_express
  10: log_file_count  11: log_function_count  12: type_coverage
  13: has_tests    14: has_auth         15: has_migrations  16: has_docker
  17: tribal_rule_count  18: off_limits_count  19: async_adoption
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Reward drawn from N(mean, noise) for oracle-match vs non-match
_ORACLE_REWARD_MEAN: float = 0.70
_NON_ORACLE_REWARD_MEAN: float = 0.30
_REWARD_NOISE: float = 0.10


@dataclass
class Episode:
    """A single training episode."""

    state: np.ndarray
    action: int
    reward: float
    info: dict = field(default_factory=dict)


class SaarSimulator:
    """Generates synthetic training episodes with a deterministic oracle policy."""

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = np.random.default_rng(seed)

    def generate_episodes(self, n: int = 500) -> list[Episode]:
        """Generate n synthetic episodes with reward conditioned on action quality.

        Each episode:
        1. Samples a random codebase state.
        2. Determines the oracle action via heuristic.
        3. Samples an action — 50% oracle, 50% random non-oracle — to give the
           agent a mix of positive and negative signal.
        4. Assigns reward from N(0.70, σ) if action == oracle, else N(0.30, σ).

        This design lets UCB separate high-reward arms from low-reward ones.
        """
        episodes: list[Episode] = []
        for _ in range(n):
            state = self._random_state()
            oracle = self._oracle_action(state)

            # 50% oracle, 50% random other action (diverse training signal)
            if self._rng.random() < 0.5:
                action = oracle
                is_oracle = True
                reward_mean = _ORACLE_REWARD_MEAN
            else:
                # Pick a non-oracle action at random
                others = [k for k in range(8) if k != oracle]
                action = int(self._rng.choice(others))
                is_oracle = False
                reward_mean = _NON_ORACLE_REWARD_MEAN

            reward = float(
                np.clip(
                    self._rng.normal(reward_mean, _REWARD_NOISE),
                    -1.0,
                    1.0,
                )
            )
            episodes.append(
                Episode(
                    state=state,
                    action=action,
                    reward=reward,
                    info={"oracle_action": oracle, "is_oracle": is_oracle},
                )
            )
        return episodes

    def _random_state(self) -> np.ndarray:
        """Sample a plausible codebase state vector."""
        s = np.zeros(20, dtype=np.float32)

        # Language distribution (sums to 1 across dims 0-3)
        lang = self._rng.dirichlet([2.0, 1.5, 1.0, 0.5])
        s[0:4] = lang.astype(np.float32)

        # Framework flags: mostly sparse
        for i in range(4, 10):
            s[i] = float(self._rng.random() < 0.25)

        # Scale features
        s[10] = float(self._rng.beta(2.0, 5.0))  # file count (log-normalised)
        s[11] = float(self._rng.beta(2.0, 5.0))  # function count
        s[12] = float(self._rng.beta(3.0, 2.0))  # type coverage (skewed high)

        # Structural flags
        for i in range(13, 17):
            s[i] = float(self._rng.random() < 0.40)

        # Tribal features
        s[17] = float(self._rng.beta(1.0, 4.0))
        s[18] = float(self._rng.beta(1.0, 4.0))
        s[19] = float(self._rng.beta(1.5, 3.0))

        np.clip(s, 0.0, 1.0, out=s)
        return s

    def _oracle_action(self, state: np.ndarray) -> int:
        """Deterministic heuristic: map state features to best profile.

        Profile mapping:
          0 — Python backend heavy  (python > 0.7)
          1 — TS/React heavy        (ts > 0.5 or has_react or has_next)
          2 — Full-stack balanced   (default / mixed)
          3 — Small script/utility  (tiny scale, no auth/db)
          4 — Monorepo/large        (very large scale)
          5 — API-only/microservice (has_auth + has_middleware-like, mid-size)
          6 — Data/ML               (large imports, low auth)
          7 — Legacy/mixed          (low type coverage + low tests)
        """
        python_frac = float(state[0])
        ts_frac = float(state[1])
        has_react = float(state[7]) > 0.5
        has_next = float(state[8]) > 0.5
        log_files = float(state[10])
        has_tests = float(state[13]) > 0.5
        has_auth = float(state[14]) > 0.5
        type_coverage = float(state[12])
        async_adoption = float(state[19])

        # Priority-ordered heuristics
        if python_frac > 0.70:
            return 0
        if ts_frac > 0.50 or has_react or has_next:
            return 1
        if log_files > 0.85:
            return 4
        if log_files < 0.20 and not has_auth:
            return 3
        if has_auth and log_files > 0.50:
            return 5
        if async_adoption > 0.60 and python_frac > 0.40:
            return 6
        if type_coverage < 0.30 and not has_tests:
            return 7
        return 2  # full-stack balanced (default)
