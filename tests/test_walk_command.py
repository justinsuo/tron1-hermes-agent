"""Tests for the high-level tron1_walk_command tool handler.

We mock the sidecar so the test runs offline.
"""

import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest


@pytest.fixture
def tool_module(tmp_path, monkeypatch):
    """Import the tool with a temp log path and a stubbed sidecar."""
    # Make sure the repo root is on sys.path (the conftest already does
    # this; we belt-and-braces it here so this test works in isolation).
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo))

    # Force the locomotion log into the temp dir so we don't pollute $HOME.
    monkeypatch.setenv("HOME", str(tmp_path))

    # Drop any cached locomotion / hermes_tools imports so module-level
    # state (singletons) is rebuilt against the new HOME.
    for name in list(sys.modules):
        if name == "locomotion" or name.startswith("locomotion.") \
           or name == "hermes_tools.tron1_locomotion_tool":
            del sys.modules[name]

    import hermes_tools.tron1_locomotion_tool as mod
    # Reset singletons defensively.
    mod._adapter = None
    mod._runner = None
    mod._obs_builder = None
    mod._logger_obj = None
    return mod


def _fake_sidecar_pose():
    return {"x": 0.0, "y": 0.0, "z": 0.92, "yaw": 0.0}


def test_valid_command_returns_ok(tool_module):
    with mock.patch.object(tool_module, "_sidecar_pose",
                           side_effect=[_fake_sidecar_pose(),
                                        {"x": 0.4, "y": 0.0, "z": 0.92, "yaw": 0.0}]), \
         mock.patch.object(tool_module, "_sidecar_velocity",
                           return_value={"ok": True, "data": {}}):
        out = json.loads(tool_module._handle_walk_command(
            {"vx": 0.4, "duration": 1.0}
        ))
    assert out["ok"] is True
    assert out["command"]["vx"] == 0.4
    assert out["distance_moved"] == pytest.approx(0.4)
    assert out["fell"] is False


def test_unsafe_command_gets_clipped(tool_module):
    with mock.patch.object(tool_module, "_sidecar_pose",
                           return_value=_fake_sidecar_pose()), \
         mock.patch.object(tool_module, "_sidecar_velocity",
                           return_value={"ok": True, "data": {}}):
        out = json.loads(tool_module._handle_walk_command(
            {"vx": 5.0, "duration": 10.0}
        ))
    assert out["ok"] is True
    # vx was 5.0, must be clipped to 0.8 (default limit)
    assert out["command"]["vx"] == pytest.approx(0.8)
    # duration was 10, must be clipped to 2.0
    assert out["command"]["duration"] == pytest.approx(2.0)
    assert any("vx clipped" in n for n in out["command"]["clip_notes"])


def test_non_numeric_input_returns_error(tool_module):
    with mock.patch.object(tool_module, "_sidecar_pose",
                           return_value=_fake_sidecar_pose()):
        out = json.loads(tool_module._handle_walk_command(
            {"vx": "fast", "duration": 1.0}
        ))
    assert out["ok"] is False
    assert "invalid command" in out["error"]


def test_sidecar_failure_propagated(tool_module):
    with mock.patch.object(tool_module, "_sidecar_pose",
                           return_value=_fake_sidecar_pose()), \
         mock.patch.object(tool_module, "_sidecar_velocity",
                           return_value={"ok": False, "error": "sidecar unreachable"}):
        out = json.loads(tool_module._handle_walk_command(
            {"vx": 0.3, "duration": 1.0}
        ))
    assert out["ok"] is False
    assert "sidecar unreachable" in out["error"]


def test_log_file_written(tool_module, tmp_path):
    with mock.patch.object(tool_module, "_sidecar_pose",
                           side_effect=[_fake_sidecar_pose(),
                                        {"x": 0.2, "y": 0.0, "z": 0.92, "yaw": 0.0}]), \
         mock.patch.object(tool_module, "_sidecar_velocity",
                           return_value={"ok": True, "data": {}}):
        tool_module._handle_walk_command({"vx": 0.3, "duration": 1.0})
    log = tmp_path / ".tron1-locomotion-log.jsonl"
    assert log.exists()
    line = json.loads(log.read_text().splitlines()[-1])
    assert line["success"] is True
    assert line["estimated_distance"] == pytest.approx(0.2)


def test_schema_advertises_walk_command(tool_module):
    s = tool_module.TRON1_WALK_COMMAND_SCHEMA
    assert s["name"] == "tron1_walk_command"
    props = s["parameters"]["properties"]
    assert set(props) == {"vx", "vy", "yaw_rate", "duration"}
