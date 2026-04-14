"""Tests for EnsembleAgent: Thompson Sampling meta-agent."""
from __future__ import annotations

import numpy as np
import pytest

from saar.rl.action_space import N_ACTIONS
from saar.rl.agents.ensemble import EnsembleAgent
from saar.rl.agents.reinforce import REINFORCEAgent
from saar.rl.agents.ucb_bandit import UCBContextualBandit


@pytest.fixture()
def agents():
    ucb = UCBContextualBandit(seed=0)
    rf = REINFORCEAgent(seed=0)
    return ucb, rf


@pytest.fixture()
def ensemble(agents):
    ucb, rf = agents
    return EnsembleAgent(ucb=ucb, reinforce=rf, seed=42)


@pytest.fixture()
def state():
    rng = np.random.default_rng(0)
    return rng.random(20).astype(np.float32)


class TestEnsembleSelectAction:
    def test_returns_valid_action(self, ensemble, state):
        action, agent_idx = ensemble.select_action(state)
        assert 0 <= action < N_ACTIONS
        assert agent_idx in (0, 1)

    def test_select_action_multiple_times(self, ensemble, state):
        for _ in range(10):
            a, idx = ensemble.select_action(state)
            assert 0 <= a < N_ACTIONS
            assert idx in (0, 1)

    def test_selection_counts_increment(self, ensemble, state):
        before = ensemble.selection_counts.sum()
        ensemble.select_action(state)
        assert ensemble.selection_counts.sum() == before + 1


class TestEnsembleUpdate:
    def test_total_updates_increments(self, ensemble, state):
        a, idx = ensemble.select_action(state)
        ensemble.update(state, a, 0.8, idx)
        assert ensemble.total_updates == 1

    def test_good_reward_increases_alpha(self, ensemble, state):
        a, idx = ensemble.select_action(state)
        alpha_before = ensemble.beta_params[idx, 0]
        ensemble.update(state, a, 1.0, idx)  # reward above threshold
        assert ensemble.beta_params[idx, 0] > alpha_before

    def test_bad_reward_increases_beta(self, ensemble, state):
        a, idx = ensemble.select_action(state)
        # Force idx=0 for determinism
        beta_before = ensemble.beta_params[idx, 1]
        ensemble.update(state, a, 0.0, idx)  # reward below threshold
        assert ensemble.beta_params[idx, 1] > beta_before

    def test_sub_agent_ucb_updated(self, ensemble, state):
        a, idx = ensemble.select_action(state)
        pulls_before = ensemble.ucb.total_pulls
        ensemble.update(state, a, 0.7, idx)
        if idx == 0:
            assert ensemble.ucb.total_pulls > pulls_before

    def test_sub_agent_reinforce_updated(self, state):
        ucb = UCBContextualBandit(seed=0)
        rf = REINFORCEAgent(seed=0)
        ens = EnsembleAgent(ucb=ucb, reinforce=rf, seed=1)
        # Force REINFORCE to be selected by manipulating Beta params
        ens.beta_params[0] = [0.01, 100.0]  # UCB nearly never selected
        ens.beta_params[1] = [100.0, 0.01]  # REINFORCE heavily favoured
        eps_before = ens.reinforce.episode_count
        for _ in range(5):
            a, idx = ens.select_action(state)
            ens.update(state, a, 0.7, idx)
        assert ens.reinforce.episode_count > eps_before


class TestEnsembleBestAction:
    def test_best_action_valid(self, ensemble, state):
        action = ensemble.best_action(state)
        assert 0 <= action < N_ACTIONS

    def test_best_action_deterministic(self, ensemble, state):
        a1 = ensemble.best_action(state)
        a2 = ensemble.best_action(state)
        assert a1 == a2


class TestEnsembleThompsonSampling:
    def test_both_agents_selected_eventually(self, state):
        """With uniform Beta priors both agents should be chosen at some point."""
        ucb = UCBContextualBandit(seed=0)
        rf = REINFORCEAgent(seed=0)
        ens = EnsembleAgent(ucb=ucb, reinforce=rf, seed=10)
        rng = np.random.default_rng(10)
        for _ in range(50):
            s = rng.random(20).astype(np.float32)
            a, idx = ens.select_action(s)
            ens.update(s, a, float(rng.random()), idx)
        assert ens.selection_counts[0] > 0
        assert ens.selection_counts[1] > 0

    def test_better_agent_selected_more_often(self):
        """After training, the consistently good agent should dominate."""
        ucb = UCBContextualBandit(seed=0)
        rf = REINFORCEAgent(seed=0)
        ens = EnsembleAgent(ucb=ucb, reinforce=rf, seed=99)
        rng = np.random.default_rng(99)

        for _ in range(200):
            s = rng.random(20).astype(np.float32)
            a, idx = ens.select_action(s)
            # UCB (idx=0) always gets good reward, REINFORCE bad
            reward = 0.9 if idx == 0 else 0.1
            ens.update(s, a, reward, idx)

        # UCB should have much higher α (successes)
        assert ens.beta_params[0, 0] > ens.beta_params[1, 0]


class TestEnsembleAgentWeights:
    def test_agent_weights_sum_to_something_reasonable(self, ensemble):
        weights = ensemble.agent_weights()
        assert set(weights.keys()) == {"ucb", "reinforce"}
        for v in weights.values():
            assert 0.0 < v < 1.0


class TestEnsembleSerialisation:
    def test_to_dict_roundtrip(self, ensemble, state):
        rng = np.random.default_rng(5)
        for _ in range(10):
            s = rng.random(20).astype(np.float32)
            a, idx = ensemble.select_action(s)
            ensemble.update(s, a, float(rng.random()), idx)

        d = ensemble.to_dict()
        restored = EnsembleAgent.from_dict(
            d, ucb=ensemble.ucb, reinforce=ensemble.reinforce
        )
        assert restored.total_updates == ensemble.total_updates
        np.testing.assert_allclose(restored.beta_params, ensemble.beta_params)
        np.testing.assert_array_equal(
            restored.selection_counts, ensemble.selection_counts
        )

    def test_repr_contains_agent_names(self, ensemble):
        r = repr(ensemble)
        assert "UCB" in r
        assert "REINFORCE" in r
        assert "EnsembleAgent" in r
