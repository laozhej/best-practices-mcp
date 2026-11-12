"""Contracts become real SDK objects without registering unimplemented tools."""

import json

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from best_practices_mcp import sdk_adapter
from best_practices_mcp.contracts import INPUT_MODELS, output_schema
from best_practices_mcp.errors import DomainError
from best_practices_mcp.sdk_adapter import result_bytes, tool_definition, tool_result


def test_all_tool_definitions_describe_actual_effects() -> None:
    for name in INPUT_MODELS:
        definition = tool_definition(name, f"Contract for {name}; not yet registered.")
        assert definition.annotations.read_only_hint == (name != "update_draft")
        assert definition.annotations.open_world_hint == (name in sdk_adapter.NETWORK_TOOLS)
        assert definition.annotations.destructive_hint == (name == "update_draft")
        Draft202012Validator.check_schema(definition.input_schema)
        Draft202012Validator.check_schema(definition.output_schema)


@pytest.mark.parametrize("name", INPUT_MODELS)
def test_error_channel_schema_and_json_fallback(name: str) -> None:
    payload = DomainError("invalid_document", "Invalid document.").to_payload()
    result = tool_result(name, payload)
    wire = json.loads(result_bytes(result))
    assert wire["isError"] is True
    assert wire["resultType"] == "complete"
    assert wire["structuredContent"] == json.loads(wire["content"][0]["text"]) == payload
    Draft202012Validator(output_schema(name)).validate(wire["structuredContent"])
    assert "io.modelcontextprotocol/serverInfo" in wire["_meta"]


def test_success_channel_and_exact_budget_includes_fallback(monkeypatch) -> None:
    payload = {
        "schema_version": 1,
        "draft": {"unknown": '雪\\"'},
        "issues": [],
        "serialized_size_bytes": 21,
    }
    result = tool_result("build_draft", payload)
    assert result.is_error is False
    assert json.loads(result.content[0].text) == result.structured_content
    size = len(result_bytes(result))
    monkeypatch.setattr(sdk_adapter, "RESPONSE_LIMIT_BYTES", size)
    assert len(result_bytes(tool_result("build_draft", payload))) == size
    monkeypatch.setattr(sdk_adapter, "RESPONSE_LIMIT_BYTES", size - 1)
    with pytest.raises(DomainError, match="response budget") as error:
        tool_result("build_draft", payload)
    assert error.value.code == "response_too_large"


def test_invalid_outputs_do_not_escape_the_adapter() -> None:
    with pytest.raises(ValidationError):
        tool_result("read_draft", {"schema_version": 1, "draft": {}})
