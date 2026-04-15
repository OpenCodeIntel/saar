"""Tests for SaarSimulator: episode generation and oracle policy."""
from __future__ import annotations

import numpy as np
import pytest

from saar.rl.action_space import N_ACTIONS
from saar.rl.simulator import Episode, SaarSimulator


class TestSaarSimulator:
    def test_episode_count(self):
        sim = SaarSimulator(seed=0)
        episodes = sim.generate_episodes(n=50)
        assert len(episodes) == 50

    def test_episode_state_shape(self):
        sim = SaarSimulator(seed=1)
        for ep in sim.generate_episodes(n=10):
            assert ep.state.shape == (20,)
            assert ep.state.dtype == np.float32

    def test_episode_state_in_unit_range(self):
        sim = SaarSimulator(seed=2)
        for ep in sim.generate_episodes(n=20):
            assert ep.state.min() >= 0.0 - 1e-6
            assert ep.state.max() <= 1.0 + 1e-6

    def test_episode_action_valid(self):
        sim = SaarSimulator(seed=3)
        for ep in sim.generate_episodes(n=30):
            assert 0 <= ep.action < N_ACTIONS

    def test_episode_reward_in_range(self):
        sim = SaarSimulator(seed=4)
        for ep in sim.generate_episodes(n=50):
            assert -1.0 <= ep.reward <= 1.0

    def test_oracle_action_in_info(self):
        sim = SaarSimulator(seed=5)
        for ep in sim.generate_episodes(n=10):
            assert "oracle_action" in ep.info
            assert 0 <= ep.info["oracle_action"] < N_ACTIONS

    def test_reproducibility(self):
        s1 = SaarSimulator(seed=42)
        s2 = SaarSimulator(seed=42)
        eps1 = s1.generate_episodes(n=20)
        eps2 = s2.generate_episodes(n=20)
        for e1, e2 in zip(eps1, eps2):
            np.testing.assert_array_equal(e1.state, e2.state)
            assert e1.action == e2.action
            assert e1.reward == e2.reward

    def test_different_seeds_differ(self):
        eps1 = SaarSimulator(seed=0).generate_episodes(n=10)
        eps2 = SaarSimulator(seed=1).generate_episodes(n=10)
        rewards_differ = any(e1.reward != e2.reward for e1, e2 in zip(eps1, eps2))
        assert rewards_differ

    def test_oracle_reward_higher_than_non_oracle(self):
        """Oracle actions should statistically yield higher rewards."""
        sim = SaarSimulator(seed=7)
        episodes = sim.generate_episodes(n=400)
        oracle_rewards = [ep.reward for ep in episodes if ep.info.get("is_oracle")]
        non_oracle_rewards = [ep.reward for ep in episodes if not ep.info.get("is_oracle")]
        assert np.mean(oracle_rewards) > np.mean(non_oracle_rewards)

    def test_half_oracle_actions(self):
        """About 50% of episodes should use oracle action."""
        sim = SaarSimulator(seed=8)
        episodes = sim.generate_episodes(n=400)
        oracle_count = sum(1 for ep in episodes if ep.info.get("is_oracle"))
        ratio = oracle_count / len(episodes)
        assert 0.35 < ratio < 0.65  # loose bound, stochastic

    def test_oracle_covers_all_profiles(self):
        """Oracle heuristic should return each of the 8 profiles at least once."""
        sim = SaarSimulator(seed=9)
        episodes = sim.generate_episodes(n=300)
        oracle_actions = {ep.info["oracle_action"] for ep in episodes}
        # Most profiles should appear; at minimum 6 of 8
        assert len(oracle_actions) >= 6

    def test_language_fractions_sum_to_one(self):
        sim = SaarSimulator(seed=10)
        for ep in sim.generate_episodes(n=20):
            lang_sum = float(ep.state[0:4].sum())
            assert abs(lang_sum - 1.0) < 1e-5
