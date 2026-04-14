"""Tests for saar/rl/environment.py.

DNAExtractor is mocked to avoid real filesystem operations.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from saar.models import AuthPattern, CodebaseDNA, ErrorPattern
from saar.rl.action_space import N_ACTIONS
from saar.rl.environment import SaarEnvironment
from saar.rl.state_encoder import StateEncoder


def _make_dna(**kwargs) -> CodebaseDNA:
    defaults = dict(
        repo_name="mock_repo",
        detected_framework="fastapi",
        language_distribution={"python": 50},
        auth_patterns=AuthPattern(middleware_used=["oauth2"]),
        error_patterns=ErrorPattern(exception_classes=["AppError"]),
    )
    defaults.update(kwargs)
    return CodebaseDNA(**defaults)


def _mock_extractor(dna: CodebaseDNA):
    """Return a mock DNAExtractor that always returns dna."""
    mock = MagicMock()
    mock.return_value.extract.return_value = dna
    return mock


@pytest.fixture()
def env(tmp_path: Path) -> SaarEnvironment:
    return SaarEnvironment(project_path=tmp_path, agent="ucb")


class TestSaarEnvironment:
    def test_reset_returns_state_vector(self, tmp_path: Path) -> None:
        dna = _make_dna()
        with patch("saar.rl.environment.DNAExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = dna
            env = SaarEnvironment(tmp_path)
            state = env.reset()

        assert isinstance(state, np.ndarray)
        assert state.shape == (StateEncoder.STATE_DIM,)
        assert state.dtype == np.float32

    def test_step_returns_valid_tuple(self, tmp_path: Path) -> None:
        dna = _make_dna()
        with patch("saar.rl.environment.DNAExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = dna
            env = SaarEnvironment(tmp_path)
            env.reset()
            next_state, reward, done, info = env.step(0)

        assert isinstance(next_state, np.ndarray)
        assert next_state.shape == (StateEncoder.STATE_DIM,)
        assert isinstance(reward, float)
        assert -1.0 <= reward <= 1.0
        assert isinstance(info, dict)
        assert "profile_id" in info

    def test_step_done_is_always_true(self, tmp_path: Path) -> None:
        dna = _make_dna()
        with patch("saar.rl.environment.DNAExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = dna
            env = SaarEnvironment(tmp_path)
            env.reset()
            for action in range(N_ACTIONS):
                _, _, done, _ = env.step(action)
                assert done is True, f"done should be True for action {action}"

    def test_action_application_does_not_mutate_global_state(self, tmp_path: Path) -> None:
        """Each step creates a fresh extractor — no shared state between calls."""
        call_count = 0

        def mock_extract(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return _make_dna(repo_name=f"run_{call_count}")

        with patch("saar.rl.environment.DNAExtractor") as MockExtractor:
            MockExtractor.return_value.extract.side_effect = mock_extract
            env = SaarEnvironment(tmp_path)
            env.reset()     # call 1
            env.step(0)     # call 2
            env.step(1)     # call 3

        # Each call should create a new extractor instance
        assert MockExtractor.call_count >= 3

    def test_reset_handles_none_extraction(self, tmp_path: Path) -> None:
        """If extractor returns None, reset should return zeros without raising."""
        with patch("saar.rl.environment.DNAExtractor") as MockExtractor:
            MockExtractor.return_value.extract.return_value = None
            env = SaarEnvironment(tmp_path)
            state = env.reset()

        assert state.shape == (StateEncoder.STATE_DIM,)
        assert not np.any(np.isnan(state))

    def test_explicit_feedback_affects_reward(self, tmp_path: Path) -> None:
        dna = _make_dna()
        rewards = {}
        for fb in (0.0, 1.0, -1.0):
            with patch("saar.rl.environment.DNAExtractor") as MockExtractor:
                MockExtractor.return_value.extract.return_value = dna
                env = SaarEnvironment(tmp_path, explicit_feedback=fb)
                env.reset()
                _, reward, _, _ = env.step(0)
                rewards[fb] = reward

        assert rewards[1.0] > rewards[0.0]
        assert rewards[-1.0] < rewards[0.0]
