"""Tests for saar/rl/agents/ucb_bandit.py."""
from __future__ import annotations

import numpy as np

from saar.rl.action_space import N_ACTIONS
from saar.rl.agents.ucb_bandit import UCBContextualBandit


def _state(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.uniform(0.0, 1.0, size=20).astype(np.float32)


class TestUCBContextualBandit:
    def setup_method(self) -> None:
        self.agent = UCBContextualBandit(seed=42)

    def test_select_action_returns_valid_index(self) -> None:
        action = self.agent.select_action(_state())
        assert 0 <= action < N_ACTIONS

    def test_update_increases_pull_count(self) -> None:
        s = _state()
        before = self.agent.total_pulls
        self.agent.update(s, action=0, reward=0.5)
        assert self.agent.total_pulls == before + 1

    def test_ucb_explores_unpulled_arms(self) -> None:
        """After enough random pulls, all arms get selected at least once."""
        rng = np.random.default_rng(7)
        agent = UCBContextualBandit(seed=7)
        seen = set()
        # Run many episodes to ensure exploration covers all arms
        for _ in range(500):
            s = rng.uniform(0.0, 1.0, size=20).astype(np.float32)
            a = agent.select_action(s)
            agent.update(s, a, reward=float(rng.uniform(0, 1)))
            seen.add(a)
        assert len(seen) == N_ACTIONS, f"Only {len(seen)} arms seen: {seen}"

    def test_best_action_is_deterministic(self) -> None:
        """Same state → same best_action after training."""
        rng = np.random.default_rng(3)
        agent = UCBContextualBandit(seed=3)
        # Train with enough pulls to leave cold-start
        for _ in range(200):
            s = rng.uniform(0.0, 1.0, size=20).astype(np.float32)
            a = agent.select_action(s)
            agent.update(s, a, reward=float(rng.uniform(0, 1)))

        s_fixed = _state(99)
        a1 = agent.best_action(s_fixed)
        a2 = agent.best_action(s_fixed)
        assert a1 == a2

    def test_serialisation_roundtrip(self) -> None:
        """save → from_dict → same parameters."""
        rng = np.random.default_rng(5)
        for _ in range(60):
            s = rng.uniform(0.0, 1.0, size=20).astype(np.float32)
            a = self.agent.select_action(s)
            self.agent.update(s, a, reward=float(rng.uniform(0, 1)))

        data = self.agent.to_dict()
        restored = UCBContextualBandit.from_dict(data)

        np.testing.assert_array_almost_equal(self.agent.centroids, restored.centroids)
        np.testing.assert_array_equal(self.agent.n, restored.n)
        np.testing.assert_array_almost_equal(self.agent.q, restored.q)
        assert self.agent.total_pulls == restored.total_pulls

    def test_cold_start_random(self) -> None:
        """Fresh agent (< C*K pulls) uses random selection."""
        agent = UCBContextualBandit(seed=0)
        assert agent.total_pulls == 0
        actions = {agent.select_action(_state(i)) for i in range(30)}
        # With random selection, should see multiple different actions
        assert len(actions) > 1

    def test_best_action_valid_range(self) -> None:
        action = self.agent.best_action(_state())
        assert 0 <= action < N_ACTIONS
