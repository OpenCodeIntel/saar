"""Tests for saar/rl/agents/reinforce.py."""
from __future__ import annotations

import numpy as np
import pytest

from saar.rl.action_space import N_ACTIONS
from saar.rl.agents.reinforce import REINFORCEAgent


def _state(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.uniform(0.0, 1.0, size=20).astype(np.float32)


class TestREINFORCEAgent:
    def setup_method(self) -> None:
        self.agent = REINFORCEAgent(seed=42)

    def test_select_action_returns_valid_index_and_log_prob(self) -> None:
        action, log_prob = self.agent.select_action(_state())
        assert 0 <= action < N_ACTIONS
        assert log_prob <= 0.0  # log of a probability in [0,1]

    def test_update_changes_parameters(self) -> None:
        s = _state(1)
        W2_before = self.agent.W2.copy()
        action, log_prob = self.agent.select_action(s)
        self.agent.update(log_prob, reward=0.8)
        # At least W2 should change (it has the strongest gradient path)
        assert not np.allclose(W2_before, self.agent.W2), "W2 did not change after update"

    def test_action_probs_sum_to_one(self) -> None:
        probs = self.agent.action_probs(_state())
        assert probs.shape == (N_ACTIONS,)
        assert abs(float(probs.sum()) - 1.0) < 1e-6
        assert np.all(probs >= 0.0)

    def test_gradient_ascent_direction(self) -> None:
        """If reward > baseline, the probability of the taken action should increase."""
        agent = REINFORCEAgent(seed=0)
        s = _state(2)

        # Force baseline low so reward > baseline is guaranteed
        agent.baseline = -1.0

        probs_before = agent.action_probs(s).copy()
        action, log_prob = agent.select_action(s)
        agent.update(log_prob, reward=1.0)  # reward > baseline → prob of action should increase
        probs_after = agent.action_probs(s)

        # The probability of the taken action should have increased
        assert probs_after[action] > probs_before[action], (
            f"Expected prob[{action}] to increase; "
            f"before={probs_before[action]:.4f} after={probs_after[action]:.4f}"
        )

    def test_serialisation_roundtrip(self) -> None:
        rng = np.random.default_rng(9)
        for _ in range(20):
            s = rng.uniform(0.0, 1.0, size=20).astype(np.float32)
            action, log_prob = self.agent.select_action(s)
            self.agent.update(log_prob, reward=float(rng.uniform(-1, 1)))

        data = self.agent.to_dict()
        restored = REINFORCEAgent.from_dict(data)

        np.testing.assert_array_almost_equal(self.agent.W1, restored.W1)
        np.testing.assert_array_almost_equal(self.agent.b1, restored.b1)
        np.testing.assert_array_almost_equal(self.agent.W2, restored.W2)
        np.testing.assert_array_almost_equal(self.agent.b2, restored.b2)
        assert self.agent.baseline == pytest.approx(restored.baseline)
        assert self.agent.episode_count == restored.episode_count

    def test_episode_count_increments(self) -> None:
        s = _state(3)
        before = self.agent.episode_count
        action, log_prob = self.agent.select_action(s)
        self.agent.update(log_prob, reward=0.5)
        assert self.agent.episode_count == before + 1

    def test_backward_gradient_shapes(self) -> None:
        s = _state(4)
        self.agent.forward(s)
        grads = self.agent.backward(action=2)
        assert grads["W1"].shape == (32, 20)
        assert grads["b1"].shape == (32,)
        assert grads["W2"].shape == (N_ACTIONS, 32)
        assert grads["b2"].shape == (N_ACTIONS,)
