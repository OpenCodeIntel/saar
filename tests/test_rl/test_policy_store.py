"""Tests for PolicyStore: save/load UCB, REINFORCE, and Ensemble agents."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from saar.rl.agents.ensemble import EnsembleAgent
from saar.rl.agents.reinforce import REINFORCEAgent
from saar.rl.agents.ucb_bandit import UCBContextualBandit
from saar.rl.policy_store import PolicyStore


@pytest.fixture()
def tmp_store(tmp_path):
    return PolicyStore(policy_dir=tmp_path)


@pytest.fixture()
def trained_ucb():
    agent = UCBContextualBandit(seed=0)
    rng = np.random.default_rng(1)
    for _ in range(60):
        state = rng.random(20).astype(np.float32)
        a = agent.select_action(state)
        agent.update(state, a, float(rng.random()))
    return agent


@pytest.fixture()
def trained_rf():
    agent = REINFORCEAgent(seed=0)
    rng = np.random.default_rng(2)
    for _ in range(20):
        state = rng.random(20).astype(np.float32)
        a, lp = agent.select_action(state)
        agent.update(lp, float(rng.random()))
    return agent


class TestPolicyStoreSaveLoad:
    def test_save_ucb_returns_path(self, tmp_store, trained_ucb):
        path = tmp_store.save(trained_ucb)
        assert path.exists()
        assert path.suffix == ".json"

    def test_roundtrip_ucb(self, tmp_store, trained_ucb):
        tmp_store.save(trained_ucb)
        loaded = tmp_store.load_ucb()
        assert loaded is not None
        assert loaded.total_pulls == trained_ucb.total_pulls
        np.testing.assert_allclose(loaded.q, trained_ucb.q, atol=1e-8)

    def test_roundtrip_reinforce(self, tmp_store, trained_rf):
        tmp_store.save(trained_rf)
        loaded = tmp_store.load_reinforce()
        assert loaded is not None
        assert loaded.episode_count == trained_rf.episode_count
        np.testing.assert_allclose(loaded.W1, trained_rf.W1, atol=1e-8)

    def test_load_missing_returns_none(self, tmp_store):
        assert tmp_store.load_ucb() is None
        assert tmp_store.load_reinforce() is None
        assert tmp_store.load_ensemble() is None

    def test_versioning_increments(self, tmp_store, trained_ucb):
        tmp_store.save(trained_ucb)
        tmp_store.save(trained_ucb)
        path = tmp_store._dir / "ucb_policy.json"
        data = json.loads(path.read_text())
        assert data["version"] == 2

    def test_atomic_write_no_partial(self, tmp_store, trained_ucb):
        """The .tmp file must not linger after save."""
        tmp_store.save(trained_ucb)
        tmp_files = list(tmp_store._dir.glob("*.tmp"))
        assert tmp_files == []

    def test_save_unknown_type_raises(self, tmp_store):
        with pytest.raises(TypeError):
            tmp_store.save("not_an_agent")  # type: ignore[arg-type]

    def test_stats_empty(self, tmp_store):
        assert tmp_store.stats() == {}

    def test_stats_after_save(self, tmp_store, trained_ucb, trained_rf):
        tmp_store.save(trained_ucb)
        tmp_store.save(trained_rf)
        stats = tmp_store.stats()
        assert "ucb" in stats
        assert "reinforce" in stats
        assert stats["ucb"]["episode_count"] == trained_ucb.total_pulls

    def test_roundtrip_ensemble(self, tmp_store, trained_ucb, trained_rf):
        ensemble = EnsembleAgent(ucb=trained_ucb, reinforce=trained_rf, seed=0)
        rng = np.random.default_rng(3)
        for _ in range(10):
            state = rng.random(20).astype(np.float32)
            a, idx = ensemble.select_action(state)
            ensemble.update(state, a, float(rng.random()), idx)

        tmp_store.save(trained_ucb)
        tmp_store.save(trained_rf)
        tmp_store.save(ensemble)

        loaded = tmp_store.load_ensemble()
        assert loaded is not None
        assert loaded.total_updates == ensemble.total_updates
        np.testing.assert_allclose(
            loaded.beta_params, ensemble.beta_params, atol=1e-8
        )
