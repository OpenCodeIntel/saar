"""REINFORCE with Baseline agent — pure numpy, no autograd framework.

Policy: 2-layer MLP
  Layer 1: Linear(state_dim=20, hidden=32) + ReLU
  Layer 2: Linear(hidden=32, n_actions=8) + Softmax

Baseline: exponential moving average of returns (α=0.1).

Manual backprop:
  G   = single-step reward (no discounting)
  δ   = G − baseline
  θ  ← θ + lr * δ * ∇log π(a|s)   (gradient ASCENT)
  Gradients clipped to [−1, 1] before applying.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from saar.rl.action_space import N_ACTIONS

logger = logging.getLogger(__name__)

_HIDDEN_DIM: int = 32
_BASELINE_ALPHA: float = 0.1
_LEARNING_RATE: float = 0.01
_GRAD_CLIP: float = 1.0


class REINFORCEAgent:
    """REINFORCE policy gradient agent with exponential moving average baseline."""

    def __init__(self, state_dim: int = 20, seed: Optional[int] = None) -> None:
        rng = np.random.default_rng(seed)
        self._state_dim = state_dim

        # Xavier-uniform initialisation for better early training
        scale1 = np.sqrt(6.0 / (state_dim + _HIDDEN_DIM))
        scale2 = np.sqrt(6.0 / (_HIDDEN_DIM + N_ACTIONS))

        self.W1: np.ndarray = rng.uniform(-scale1, scale1, (_HIDDEN_DIM, state_dim)).astype(np.float64)
        self.b1: np.ndarray = np.zeros(_HIDDEN_DIM, dtype=np.float64)
        self.W2: np.ndarray = rng.uniform(-scale2, scale2, (N_ACTIONS, _HIDDEN_DIM)).astype(np.float64)
        self.b2: np.ndarray = np.zeros(N_ACTIONS, dtype=np.float64)

        self.baseline: float = 0.0
        self.episode_count: int = 0

        # Cache for backward pass (set during forward())
        self._last_state: Optional[np.ndarray] = None
        self._last_h1_pre: Optional[np.ndarray] = None
        self._last_h1: Optional[np.ndarray] = None
        self._last_probs: Optional[np.ndarray] = None
        self._last_action: Optional[int] = None

    # -- Forward pass ---------------------------------------------------------

    def forward(self, state: np.ndarray) -> np.ndarray:
        """Run forward pass, cache activations, return softmax probabilities."""
        s = state.astype(np.float64)
        h1_pre = self.W1 @ s + self.b1          # (hidden,)
        h1 = np.maximum(0.0, h1_pre)            # ReLU
        logits = self.W2 @ h1 + self.b2         # (n_actions,)
        probs = self._softmax(logits)            # (n_actions,)

        self._last_state = s
        self._last_h1_pre = h1_pre
        self._last_h1 = h1
        self._last_probs = probs

        return probs

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        """Numerically stable softmax."""
        shifted = x - np.max(x)
        exp_x = np.exp(shifted)
        return exp_x / exp_x.sum()

    # -- Backward pass --------------------------------------------------------

    def backward(self, action: int) -> dict[str, np.ndarray]:
        """Compute ∇log π(a|s) for all parameters.

        Returns a dict with keys W1, b1, W2, b2 containing raw gradients
        (before scaling by δ or learning rate).

        Must be called after forward() so cached activations are set.
        """
        assert self._last_state is not None, "Call forward() before backward()"
        probs = self._last_probs
        h1 = self._last_h1
        h1_pre = self._last_h1_pre
        s = self._last_state

        # Gradient of log π(a|s) w.r.t. logits: e_a − probs
        delta2 = -probs.copy()              # (n_actions,)
        delta2[action] += 1.0              # one-hot minus probs

        # Gradients for W2 and b2
        grad_W2 = np.outer(delta2, h1)     # (n_actions, hidden)
        grad_b2 = delta2.copy()            # (n_actions,)

        # Backprop through W2
        d_h1 = self.W2.T @ delta2          # (hidden,)

        # Backprop through ReLU
        relu_mask = (h1_pre > 0).astype(np.float64)
        d_h1_pre = d_h1 * relu_mask        # (hidden,)

        # Gradients for W1 and b1
        grad_W1 = np.outer(d_h1_pre, s)   # (hidden, state_dim)
        grad_b1 = d_h1_pre.copy()         # (hidden,)

        return {"W1": grad_W1, "b1": grad_b1, "W2": grad_W2, "b2": grad_b2}

    # -- Public API -----------------------------------------------------------

    def select_action(self, state: np.ndarray) -> tuple[int, float]:
        """Sample an action from the policy.

        Returns:
            (action_index, log_prob) — log_prob is needed for the update step.
        """
        probs = self.forward(state)
        self._last_action = int(np.random.choice(N_ACTIONS, p=probs))
        log_prob = float(np.log(probs[self._last_action] + 1e-12))
        return self._last_action, log_prob

    def update(self, log_prob: float, reward: float) -> None:  # noqa: ARG002
        """REINFORCE update step.

        Args:
            log_prob: log π(a|s) from the taken action (not used directly —
                      we re-derive gradients from cached activations).
            reward:   Scalar reward G for this episode.
        """
        if self._last_action is None or self._last_probs is None:
            logger.warning("update() called before select_action() — skipping")
            return

        # Update baseline
        self.baseline = _BASELINE_ALPHA * reward + (1.0 - _BASELINE_ALPHA) * self.baseline
        delta = reward - self.baseline

        # Compute gradients
        grads = self.backward(self._last_action)

        # Gradient ASCENT: θ ← θ + lr * δ * ∇log π(a|s), with clipping
        for param_name, grad in grads.items():
            clipped = np.clip(delta * grad, -_GRAD_CLIP, _GRAD_CLIP)
            setattr(self, param_name, getattr(self, param_name) + _LEARNING_RATE * clipped)

        self.episode_count += 1

        # Clear cache to avoid stale use
        self._last_action = None
        self._last_probs = None
        self._last_state = None
        self._last_h1_pre = None
        self._last_h1 = None

    def action_probs(self, state: np.ndarray) -> np.ndarray:
        """Return full softmax distribution over actions (no sampling, no side-effects)."""
        s = state.astype(np.float64)
        h1 = np.maximum(0.0, self.W1 @ s + self.b1)
        logits = self.W2 @ h1 + self.b2
        return self._softmax(logits)

    # -- Serialisation --------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise parameters to a JSON-friendly dict."""
        return {
            "W1": self.W1.tolist(),
            "b1": self.b1.tolist(),
            "W2": self.W2.tolist(),
            "b2": self.b2.tolist(),
            "baseline": self.baseline,
            "episode_count": self.episode_count,
            "state_dim": self._state_dim,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "REINFORCEAgent":
        """Restore agent from a serialised dict."""
        agent = cls(state_dim=data.get("state_dim", 20))
        agent.W1 = np.array(data["W1"], dtype=np.float64)
        agent.b1 = np.array(data["b1"], dtype=np.float64)
        agent.W2 = np.array(data["W2"], dtype=np.float64)
        agent.b2 = np.array(data["b2"], dtype=np.float64)
        agent.baseline = float(data["baseline"])
        agent.episode_count = int(data["episode_count"])
        return agent
