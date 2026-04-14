"""Persistent storage for trained RL agents.

Saves/loads UCBContextualBandit, REINFORCEAgent, and EnsembleAgent to
~/.saar/rl/ as JSON.  Atomic writes: write to .tmp then os.replace() to
avoid partial writes.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from saar.rl.agents.ensemble import EnsembleAgent
from saar.rl.agents.reinforce import REINFORCEAgent
from saar.rl.agents.ucb_bandit import UCBContextualBandit

logger = logging.getLogger(__name__)

POLICY_DIR: Path = Path.home() / ".saar" / "rl"

_UCB_FILENAME = "ucb_policy.json"
_REINFORCE_FILENAME = "reinforce_policy.json"
_ENSEMBLE_FILENAME = "ensemble_policy.json"


@dataclass
class PolicySnapshot:
    """Metadata envelope around serialised agent parameters."""

    algorithm: str          # "ucb" | "reinforce"
    version: int
    episode_count: int
    created_at: str         # ISO 8601
    parameters: dict        # algorithm-specific serialised params


def _atomic_write(path: Path, data: dict) -> None:
    """Write JSON to path atomically via a .tmp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(path))
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _next_version(path: Path) -> int:
    """Return the next version number for a policy file."""
    if not path.exists():
        return 1
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
        return int(existing.get("version", 0)) + 1
    except Exception:
        return 1


class PolicyStore:
    """Saves and loads trained agents to/from ~/.saar/rl/."""

    def __init__(self, policy_dir: Path = POLICY_DIR) -> None:
        self._dir = policy_dir

    def save(self, agent: Union[UCBContextualBandit, REINFORCEAgent, EnsembleAgent]) -> Path:
        """Serialise agent and write atomically.  Returns the path written."""
        if isinstance(agent, UCBContextualBandit):
            algorithm = "ucb"
            filename = _UCB_FILENAME
            episode_count = int(agent.total_pulls)
        elif isinstance(agent, REINFORCEAgent):
            algorithm = "reinforce"
            filename = _REINFORCE_FILENAME
            episode_count = int(agent.episode_count)
        elif isinstance(agent, EnsembleAgent):
            algorithm = "ensemble"
            filename = _ENSEMBLE_FILENAME
            episode_count = int(agent.total_updates)
        else:
            raise TypeError(f"Unknown agent type: {type(agent)}")

        target = self._dir / filename
        snapshot = PolicySnapshot(
            algorithm=algorithm,
            version=_next_version(target),
            episode_count=episode_count,
            created_at=datetime.now(tz=timezone.utc).isoformat(),
            parameters=agent.to_dict(),
        )
        payload = {
            "algorithm": snapshot.algorithm,
            "version": snapshot.version,
            "episode_count": snapshot.episode_count,
            "created_at": snapshot.created_at,
            "parameters": snapshot.parameters,
        }
        _atomic_write(target, payload)
        logger.info("Saved %s policy to %s (v%d, %d episodes)", algorithm, target, snapshot.version, episode_count)
        return target

    def load_ucb(self) -> Optional[UCBContextualBandit]:
        """Load the most recently saved UCB agent, or None if not found."""
        path = self._dir / _UCB_FILENAME
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            agent = UCBContextualBandit.from_dict(data["parameters"])
            logger.info("Loaded UCB policy v%d (%d pulls)", data.get("version", 0), agent.total_pulls)
            return agent
        except Exception as e:
            logger.warning("Failed to load UCB policy: %s", e)
            return None

    def load_reinforce(self) -> Optional[REINFORCEAgent]:
        """Load the most recently saved REINFORCE agent, or None if not found."""
        path = self._dir / _REINFORCE_FILENAME
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            agent = REINFORCEAgent.from_dict(data["parameters"])
            logger.info(
                "Loaded REINFORCE policy v%d (%d episodes)", data.get("version", 0), agent.episode_count
            )
            return agent
        except Exception as e:
            logger.warning("Failed to load REINFORCE policy: %s", e)
            return None

    def load_ensemble(self) -> Optional[EnsembleAgent]:
        """Load ensemble agent (requires UCB and REINFORCE to be loaded first)."""
        path = self._dir / _ENSEMBLE_FILENAME
        if not path.exists():
            return None
        ucb = self.load_ucb()
        rf = self.load_reinforce()
        if ucb is None or rf is None:
            logger.warning("Cannot load ensemble: sub-agents missing")
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            agent = EnsembleAgent.from_dict(data["parameters"], ucb=ucb, reinforce=rf)
            logger.info(
                "Loaded ensemble policy v%d (%d updates)",
                data.get("version", 0), agent.total_updates,
            )
            return agent
        except Exception as e:
            logger.warning("Failed to load ensemble policy: %s", e)
            return None

    def stats(self) -> dict:
        """Return a dict of stats for `saar rl status`."""
        result: dict = {}

        ucb_path = self._dir / _UCB_FILENAME
        if ucb_path.exists():
            try:
                data = json.loads(ucb_path.read_text(encoding="utf-8"))
                result["ucb"] = {
                    "version": data.get("version"),
                    "episode_count": data.get("episode_count"),
                    "created_at": data.get("created_at"),
                }
            except Exception as e:
                result["ucb"] = {"error": str(e)}

        rf_path = self._dir / _REINFORCE_FILENAME
        if rf_path.exists():
            try:
                data = json.loads(rf_path.read_text(encoding="utf-8"))
                result["reinforce"] = {
                    "version": data.get("version"),
                    "episode_count": data.get("episode_count"),
                    "created_at": data.get("created_at"),
                }
            except Exception as e:
                result["reinforce"] = {"error": str(e)}

        ens_path = self._dir / _ENSEMBLE_FILENAME
        if ens_path.exists():
            try:
                data = json.loads(ens_path.read_text(encoding="utf-8"))
                result["ensemble"] = {
                    "version": data.get("version"),
                    "episode_count": data.get("episode_count"),
                    "created_at": data.get("created_at"),
                }
            except Exception as e:
                result["ensemble"] = {"error": str(e)}

        return result
