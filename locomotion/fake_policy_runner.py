"""A safe stand-in policy that doesn't depend on torch.

Used when:
  - No trained .pt is available yet.
  - Unit tests want a deterministic, zero-dependency runner.
  - The Hermes tool wants to validate the locomotion pipeline end-to-end
    against the existing kinematic MuJoCo backend before a real policy
    lands.

Behavior: returns a zero-action vector, but echoes the requested velocity
command through as the first three slots so the simulator backend can use
it as a kinematic velocity setpoint when no joint-level policy is wired up.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from .policy_interface import PolicyInterface


# WF_TRON1A actuated joint count = 8 (abad/hip/knee/wheel × 2 legs).
# Confirmed against robot-description/pointfoot/WF_TRON1A/xml/robot.xml.
# If a future LimX checkpoint outputs joint_pos_delta for only the 6
# non-wheel joints (excluding the continuous wheel joints), pass
# action_dim=6 at construction.
_DEFAULT_ACTION_DIM = 8


class FakePolicyRunner(PolicyInterface):
    """Returns zeros + a velocity-command echo for the backend to consume."""

    def __init__(
        self,
        action_dim: int = _DEFAULT_ACTION_DIM,
        obs_dim: int = 33,
        command_dim: int = 3,
    ) -> None:
        self._action_dim = action_dim
        self._obs_dim = obs_dim
        self._command_dim = command_dim
        self._last_command: List[float] = [0.0] * command_dim
        self._step_count = 0

    def reset(self) -> None:
        self._last_command = [0.0] * self._command_dim
        self._step_count = 0

    def act(
        self,
        observation: Sequence[float],
        command: Sequence[float],
    ) -> List[float]:
        if len(observation) != self._obs_dim:
            # Don't raise — the kinematic backend doesn't actually consume
            # the action, so a mismatch is recoverable. Just note it.
            pass
        cmd = list(command[: self._command_dim])
        while len(cmd) < self._command_dim:
            cmd.append(0.0)
        self._last_command = cmd
        self._step_count += 1
        # Action layout: [vx, vy, yaw_rate, 0, 0, ...] — first 3 slots are
        # the velocity echo so callers using a velocity-style backend can
        # forward them directly to `tron1_velocity`. Remaining slots are
        # zero, which a real policy would fill with joint targets.
        action = [0.0] * self._action_dim
        for i, v in enumerate(cmd):
            if i < self._action_dim:
                action[i] = float(v)
        return action

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "FakePolicyRunner",
            "obs_dim": self._obs_dim,
            "action_dim": self._action_dim,
            "command_dim": self._command_dim,
            "action_semantic": "velocity_echo",
            "trained_on": "fake",
            "step_count": self._step_count,
        }
