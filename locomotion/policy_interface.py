"""Abstract base class for locomotion policies.

The interface deliberately does not mention torch, Isaac Gym, ROS, or MuJoCo.
A policy is anything that takes an observation + a command and returns an
action vector. Concrete implementations:

  - FakePolicyRunner  — returns safe zero-ish actions, for testing.
  - PolicyRunner      — loads a .pt checkpoint trained with LimX-style
                        legged_gym and runs forward() under torch.

The simulator backend (MuJoCo or real robot via ROS) is responsible for
translating the returned action vector into joint targets / torques. The
policy itself is sim-agnostic; only the action layout has to match the
backend, and that contract is documented in the policy's metadata.
"""

from __future__ import annotations

import abc
from typing import Any, Dict, Sequence


class PolicyInterface(abc.ABC):
    """Locomotion policy contract.

    Every concrete policy must report metadata describing the I/O shape and
    semantics so callers can validate compatibility without inspecting weights.
    """

    @abc.abstractmethod
    def reset(self) -> None:
        """Clear any internal state (RNN hidden state, last-action memory).

        Called between episodes. Should be cheap — no checkpoint reload.
        """

    @abc.abstractmethod
    def act(
        self,
        observation: Sequence[float],
        command: Sequence[float],
    ) -> Sequence[float]:
        """Return an action vector for the given (observation, command).

        Args:
            observation: Flat list/array of floats. Length must equal
                ``get_metadata()['obs_dim']``. The exact ordering is set by
                :class:`ObservationBuilder` and must match what the policy
                was trained on.
            command: 3-vector ``[vx, vy, yaw_rate]`` in the robot's body
                frame, normalized per the policy's training config.

        Returns:
            Action vector of length ``get_metadata()['action_dim']``. The
            interpretation (joint position delta, torque scale, etc.) is
            backend-specific and recorded in metadata['action_semantic'].
        """

    @abc.abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Describe the policy. Must include at least:

        - ``name``: human label
        - ``obs_dim``: expected length of ``observation``
        - ``action_dim``: length of returned action
        - ``command_dim``: length of ``command`` (typically 3)
        - ``action_semantic``: e.g. ``"joint_pos_delta"`` or ``"velocity"``
        - ``trained_on``: free-form note (``"fake"``, checkpoint path, etc.)
        """
