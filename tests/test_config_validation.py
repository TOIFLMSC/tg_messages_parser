import yaml
import pytest

from app.config import ConfigError, load_config


def _base_config(tasks):
    return {
        "telegram": {
            "api_id": 123,
            "api_hash": "hash",
            "session_name": "sess",
        },
        "storage": {
            "state_dir": "./state",
            "hash_ttl_hours": 24,
            "cleanup_interval_minutes": 10,
        },
        "runtime": {
            "default_interactive_task_selection": True,
            "debug": False,
        },
        "tasks": tasks,
    }


def _write_config(tmp_path, data):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


def test_missing_output_mode_is_error(tmp_path):
    cfg = _base_config(
        [
            {
                "name": "t1",
                "enabled": True,
                "interval_seconds": 5,
                "sources": ["@src"],
                "output": {"target": "@dst"},
                "filters": {"mode": "or", "keywords": [], "link_patterns": []},
            }
        ]
    )
    path = _write_config(tmp_path, cfg)
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert "tasks[0].output.mode" in str(exc.value) or "must include mode" in str(
        exc.value
    )


def test_invalid_output_mode_is_error(tmp_path):
    cfg = _base_config(
        [
            {
                "name": "t1",
                "enabled": True,
                "interval_seconds": 5,
                "sources": ["@src"],
                "output": {"mode": "invalid", "target": "@dst"},
                "filters": {"mode": "or", "keywords": [], "link_patterns": []},
            }
        ]
    )
    path = _write_config(tmp_path, cfg)
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert "tasks[0].output.mode" in str(exc.value)


def test_bot_mode_requires_token(tmp_path):
    cfg = _base_config(
        [
            {
                "name": "t1",
                "enabled": True,
                "interval_seconds": 5,
                "sources": ["@src"],
                "output": {"mode": "bot", "target": "-100123"},
                "filters": {"mode": "or", "keywords": [], "link_patterns": []},
            }
        ]
    )
    path = _write_config(tmp_path, cfg)
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert "tasks[0].output.bot_token" in str(exc.value)


def test_bot_mode_valid(tmp_path):
    cfg = _base_config(
        [
            {
                "name": "t1",
                "enabled": True,
                "interval_seconds": 5,
                "sources": ["@src"],
                "output": {
                    "mode": "bot",
                    "bot_token": "123:ABC",
                    "target": "-100123",
                },
                "filters": {"mode": "or", "keywords": [], "link_patterns": []},
            }
        ]
    )
    path = _write_config(tmp_path, cfg)
    config = load_config(path)
    assert config.tasks[0].output.mode == "bot"


def test_user_mode_valid(tmp_path):
    cfg = _base_config(
        [
            {
                "name": "t1",
                "enabled": True,
                "interval_seconds": 5,
                "sources": ["@src"],
                "output": {"mode": "user", "target": "@dst"},
                "filters": {"mode": "or", "keywords": [], "link_patterns": []},
            }
        ]
    )
    path = _write_config(tmp_path, cfg)
    config = load_config(path)
    assert config.tasks[0].output.mode == "user"


@pytest.mark.parametrize("value", [0, -1])
def test_invalid_interval_seconds(tmp_path, value):
    cfg = _base_config(
        [
            {
                "name": "t1",
                "enabled": True,
                "interval_seconds": value,
                "sources": ["@src"],
                "output": {"mode": "user", "target": "@dst"},
                "filters": {"mode": "or", "keywords": [], "link_patterns": []},
            }
        ]
    )
    path = _write_config(tmp_path, cfg)
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert "tasks[0].interval_seconds" in str(exc.value)


def test_interval_seconds_type_error(tmp_path):
    cfg = _base_config(
        [
            {
                "name": "t1",
                "enabled": True,
                "interval_seconds": "5",
                "sources": ["@src"],
                "output": {"mode": "user", "target": "@dst"},
                "filters": {"mode": "or", "keywords": [], "link_patterns": []},
            }
        ]
    )
    path = _write_config(tmp_path, cfg)
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert "tasks[0].interval_seconds" in str(exc.value)
