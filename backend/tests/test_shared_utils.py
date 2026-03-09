from app.nodes import shared_utils


def test_load_agent_config_returns_defaults_when_config_missing(tmp_path, monkeypatch):
    missing_config = tmp_path / "agents.yaml"
    monkeypatch.setattr(shared_utils, "_CONFIG_PATH", missing_config)

    cfg = shared_utils.load_agent_config("planner")

    assert cfg == {
        "model": shared_utils.DEFAULT_MODEL,
        "base_url": shared_utils.DEFAULT_BASE_URL,
    }


def test_load_agent_config_reads_agent_values(tmp_path, monkeypatch):
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        "planner:\n  model: planner-model\n  base_url: http://planner.local\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(shared_utils, "_CONFIG_PATH", config_path)

    cfg = shared_utils.load_agent_config("planner")

    assert cfg == {"model": "planner-model", "base_url": "http://planner.local"}


def test_extract_json_object_handles_markdown_fence():
    raw = "```json\n{\"success\": true, \"feedback\": \"ok\"}\n```"

    extracted = shared_utils.extract_json_object(raw)

    assert extracted == "{\"success\": true, \"feedback\": \"ok\"}"


def test_extract_json_object_keeps_plain_json():
    raw = "{\"task_description\":\"Ship change\"}"

    extracted = shared_utils.extract_json_object(raw)

    assert extracted == raw
