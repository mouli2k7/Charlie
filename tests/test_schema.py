"""Tests for Pydantic schema validation and whitelist enforcement."""

from charlie.schema import Action, validate_action, make_unknown


def test_valid_open_app():
    raw = {"action": "open_app", "params": {"app": "Spotify"}}
    res = validate_action(raw)
    assert res.action == "open_app"
    assert res.params["app"] == "Spotify"


def test_valid_volume_set():
    raw = {"action": "volume_set", "params": {"level": 40}}
    res = validate_action(raw)
    assert res.action == "volume_set"
    assert res.params["level"] == 40


def test_valid_media_control():
    raw = {"action": "media_control", "params": {"command": "play_pause"}}
    res = validate_action(raw)
    assert res.action == "media_control"
    assert res.params["command"] == "play_pause"


def test_non_whitelisted_action_becomes_unknown():
    raw = {"action": "delete_all_files", "params": {"path": "/Users"}}
    res = validate_action(raw)
    assert res.action == "unknown"
    assert "not in the whitelist" in res.params["reason"]


def test_dangerous_shell_command_becomes_unknown():
    raw = {"action": "exec_shell", "params": {"command": "rm -rf /"}}
    res = validate_action(raw)
    assert res.action == "unknown"


def test_volume_set_out_of_range_becomes_unknown():
    # Negative volume
    res_neg = validate_action({"action": "volume_set", "params": {"level": -5}})
    assert res_neg.action == "unknown"

    # Over 100 volume
    res_over = validate_action({"action": "volume_set", "params": {"level": 150}})
    assert res_over.action == "unknown"


def test_brightness_set_out_of_range_becomes_unknown():
    res_over = validate_action({"action": "brightness_set", "params": {"level": 120}})
    assert res_over.action == "unknown"


def test_missing_required_params_becomes_unknown():
    # open_app without 'app' parameter
    res = validate_action({"action": "open_app", "params": {}})
    assert res.action == "unknown"

    # web_search without 'query'
    res_ws = validate_action({"action": "web_search", "params": {"site": "google"}})
    assert res_ws.action == "unknown"


def test_invalid_enum_media_command_becomes_unknown():
    res = validate_action({"action": "media_control", "params": {"command": "shuffle"}})
    assert res.action == "unknown"


def test_malformed_payload_becomes_unknown():
    assert validate_action("not a dict").action == "unknown"
    assert validate_action({"action": 12345}).action == "unknown"
    assert validate_action({"action": "volume_set", "params": "not_a_dict"}).action == "unknown"


def test_make_unknown():
    unk = make_unknown("Custom reason")
    assert unk.action == "unknown"
    assert unk.params["reason"] == "Custom reason"
    assert unk.confidence == 0.0
