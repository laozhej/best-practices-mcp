"""Exercise M3 production handlers over MCP without storage or authenticated access."""

import asyncio
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from mcp import Client, StdioServerParameters

from best_practices_mcp.contracts import output_schema

FIXTURE = Path(__file__).parent / "fixtures/read_server.py"


def test_document_workflow_wire_results_with_missing_storage_root(tmp_path):
    root = tmp_path / "untouched-drafts"

    async def exercise():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=[str(FIXTURE.resolve())],
            cwd=tmp_path,
            env={"BESTPRACTICES_DATA_DIR": str(root)},
        )
        async with asyncio.timeout(20), Client(parameters) as client:
            calls = [
                (
                    "build_draft",
                    {
                        "draft": {"opaque": [None, True, {"x": 3}]},
                        "changes": {"description_good_status": "Unmet"},
                    },
                ),
                (
                    "validate_draft",
                    {
                        "project_id": 123,
                        "level": "passing",
                        "draft": {"description_good_status": "N/A"},
                    },
                ),
                (
                    "prepare_update_url",
                    {
                        "project_id": 123,
                        "level": "passing",
                        "draft": {"description_good_status": "Unmet"},
                    },
                ),
                (
                    "prepare_update_script",
                    {
                        "project_id": 123,
                        "level": "passing",
                        "draft": {"description_good_justification": "New ✨ text"},
                    },
                ),
            ]
            results = []
            for name, args in calls:
                result = await client.call_tool(name, args)
                assert not result.is_error, result
                payload = result.structured_content
                Draft202012Validator(output_schema(name)).validate(payload)
                assert json.loads(result.content[0].text) == payload
                results.append(payload)
            assert results[0]["draft"]["opaque"] == [None, True, {"x": 3}]
            assert results[1]["findings"]
            assert results[2]["transfer"][0]["expected_application"] == "retain_existing"
            assert results[3]["artifact"]["javascript"]
            for name in ("validate_draft", "prepare_update_url", "prepare_update_script"):
                result = await client.call_tool(name, {"project_id": 123, "level": "passing"})
                assert result.is_error
                assert result.structured_content["error"]["code"] == "draft_not_found"
            mismatch = await client.call_tool(
                "prepare_update_url", {"project_id": 123, "level": "passing", "draft": {"id": 456}}
            )
            assert mismatch.structured_content["error"]["code"] == "project_mismatch"

    asyncio.run(exercise())
    assert not root.exists()
    assert not list(tmp_path.iterdir())


def test_pure_handlers_and_missing_drafts_do_not_need_http(tmp_path):
    from best_practices_mcp.server import create_server

    async def exercise():
        server = create_server(
            data_root=tmp_path / "untouched",
            http_factory=lambda: (_ for _ in ()).throw(AssertionError("HTTP")),
        )
        for name, arguments in (
            ("build_draft", {"draft": {}, "changes": {"name": "Example"}}),
            ("validate_draft", {"project_id": 123, "level": "passing", "draft": {}}),
        ):
            assert not (await server.call_tool(name, arguments)).is_error
        for name in ("validate_draft", "prepare_update_url", "prepare_update_script"):
            result = await server.call_tool(name, {"project_id": 123, "level": "passing"})
            assert result.structured_content["error"]["code"] == "draft_not_found"

    asyncio.run(exercise())
