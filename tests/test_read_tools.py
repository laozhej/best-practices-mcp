"""Exercise production read handlers and advertised contracts over real MCP stdio."""

import asyncio
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from mcp import Client, StdioServerParameters

from best_practices_mcp.contracts import input_schema, output_schema
from best_practices_mcp.server import IMPLEMENTED_TOOLS

FIXTURE_SERVER = Path(__file__).parent / "fixtures" / "read_server.py"


def test_read_workflow_wire_results_and_catalog_schemas(tmp_path: Path) -> None:
    async def exercise():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=[str(FIXTURE_SERVER.resolve())],
            cwd=tmp_path,
            env={"BESTPRACTICES_DATA_DIR": str(tmp_path / "drafts")},
        )
        async with asyncio.timeout(15), Client(parameters, read_timeout_seconds=5) as client:
            listed = (await client.list_tools()).tools
            assert [tool.name for tool in listed] == sorted(IMPLEMENTED_TOOLS)
            for tool in listed:
                assert tool.input_schema == input_schema(tool.name)
                assert tool.output_schema == output_schema(tool.name)
                assert tool.annotations.read_only_hint is (tool.name != "update_draft")
            calls = [
                ("get_criteria", {}),
                ("find_project", {"query": "ambiguous"}),
                ("get_project_progress", {"project_id": 123, "level": "passing"}),
                ("get_criteria", {"level": "passing", "criterion_ids": ["unknown"]}),
                ("get_project_progress", {"project_id": 999}),
                ("find_project", {"query": "rate-limited"}),
            ]
            results = []
            for name, arguments in calls:
                result = await client.call_tool(name, arguments)
                payload = result.structured_content
                Draft202012Validator(output_schema(name)).validate(payload)
                assert json.loads(result.content[0].text) == payload
                results.append(result)
            assert len(results[0].structured_content["levels"]) == 6
            assert len(results[1].structured_content["candidates"]) == 2
            assert results[2].structured_content["answers"]["description_good_status"] == "Met"
            assert results[2].structured_content["observation"]["license"] == "CC-BY-3.0+"
            assert [r.structured_content["error"]["code"] for r in results[3:]] == [
                "invalid_criterion",
                "project_not_found",
                "rate_limited",
            ]
            assert all(r.is_error for r in results[3:])
            bad = await client.call_tool("get_project_progress", {"project_id": True})
            assert bad.is_error
            assert "input_value" not in bad.content[0].text
            assert [t.name for t in (await client.list_tools()).tools] == sorted(IMPLEMENTED_TOOLS)

    asyncio.run(exercise())
    assert not list(tmp_path.iterdir())


def test_offline_catalog_and_invalid_inputs_need_no_network(tmp_path: Path) -> None:
    script = tmp_path / "network_forbidden.py"
    script.write_text(
        "import asyncio, socket\n"
        "async def main():\n"
        "    def deny(*args, **kwargs): raise RuntimeError('network forbidden')\n"
        "    socket.create_connection = deny\n"
        "    socket.socket.connect = deny\n"
        "    socket.socket.connect_ex = deny\n"
        "    with socket.socket() as probe:\n"
        "        try: probe.connect(('192.0.2.1', 443))\n"
        "        except RuntimeError as error: assert str(error) == 'network forbidden'\n"
        "        else: raise AssertionError('external connect was permitted')\n"
        "    from best_practices_mcp.server import create_server\n"
        "    await create_server().run_stdio_async()\n"
        # Windows ProactorEventLoop needs its internal socketpair during creation.
        # Create that loop first, then deny every connect throughout application use.
        "asyncio.run(main())\n",
        encoding="utf-8",
    )

    async def exercise():
        async with (
            asyncio.timeout(10),
            Client(
                StdioServerParameters(command=sys.executable, args=[str(script)]),
                read_timeout_seconds=5,
            ) as client,
        ):
            result = await client.call_tool("get_criteria", {"level": "silver"})
            assert not result.is_error
            assert result.structured_content["criteria"]
            invalid = await client.call_tool("find_project", {"query": None})
            assert invalid.is_error

    asyncio.run(exercise())
