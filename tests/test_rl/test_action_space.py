"""Tests for action_space: profiles, ExtractorAction, and get_action."""
from __future__ import annotations

import pytest

from saar.rl.action_space import (
    N_ACTIONS,
    PROFILES,
    ExtractorAction,
    action_count,
    get_action,
)

_EXPECTED_EXTRACTOR_NAMES = {
    "auth", "database", "errors", "logging", "services",
    "naming", "imports", "api", "tests", "frontend", "config", "middleware",
}


class TestActionSpace:
    def test_n_actions(self):
        assert N_ACTIONS == 8

    def test_action_count_matches(self):
        assert action_count() == N_ACTIONS

    def test_profiles_keys(self):
        assert set(PROFILES.keys()) == set(range(N_ACTIONS))

    def test_each_profile_has_all_extractor_keys(self):
        for profile_id, profile in PROFILES.items():
            missing = _EXPECTED_EXTRACTOR_NAMES - set(profile.keys())
            assert missing == set(), (
                f"Profile {profile_id} missing extractor keys: {missing}"
            )

    def test_multipliers_positive(self):
        for profile_id, profile in PROFILES.items():
            for key, val in profile.items():
                assert val > 0, (
                    f"Profile {profile_id} key '{key}' has non-positive multiplier {val}"
                )

    def test_multipliers_in_reasonable_range(self):
        """All multipliers should be between 0.25 and 4.0."""
        for profile_id, profile in PROFILES.items():
            for key, val in profile.items():
                assert 0.25 <= val <= 4.0, (
                    f"Profile {profile_id} key '{key}' multiplier {val} out of expected range"
                )

    def test_get_action_valid_ids(self):
        for i in range(N_ACTIONS):
            action = get_action(i)
            assert isinstance(action, ExtractorAction)
            assert action.profile_id == i

    def test_get_action_returns_copy(self):
        """Modifying the returned dict must not affect PROFILES."""
        action = get_action(0)
        original_auth = PROFILES[0]["auth"]
        action.depth_multipliers["auth"] = 999.0
        assert PROFILES[0]["auth"] == original_auth

    def test_get_action_invalid_raises(self):
        with pytest.raises(ValueError):
            get_action(N_ACTIONS)

    def test_get_action_negative_raises(self):
        with pytest.raises(ValueError):
            get_action(-1)

    def test_each_profile_has_at_least_one_high_multiplier(self):
        """Each profile should prioritise at least one extractor (multiplier >= 1.5)."""
        for profile_id, profile in PROFILES.items():
            has_high = any(v >= 1.5 for v in profile.values())
            assert has_high, f"Profile {profile_id} has no high-priority extractor"

    def test_profiles_differ_from_each_other(self):
        """No two profiles should have identical multiplier dicts."""
        profile_list = list(PROFILES.values())
        for i in range(len(profile_list)):
            for j in range(i + 1, len(profile_list)):
                assert profile_list[i] != profile_list[j], (
                    f"Profiles {i} and {j} are identical"
                )
