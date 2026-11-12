"""Execute returned JavaScript against source-derived forms using a real DOM."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from best_practices_mcp.models import PrepareScriptResult
from best_practices_mcp.scripts import prepare_update_script

FORMS = Path(__file__).parent / "fixtures" / "forms"
MANIFEST = json.loads((FORMS / "provenance.json").read_text(encoding="utf-8"))
OBSERVATION = {
    "project_id": 123,
    "source_url": "https://www.bestpractices.dev/projects/123.json",
    "fetched_at": "2026-11-09T00:00:00Z",
    "attribution": None,
    "license": None,
}


def prepare(draft, record=None, level="passing"):
    result = prepare_update_script(123, level, draft, record or {}, OBSERVATION)
    PrepareScriptResult.model_validate(result)
    return result


def execute(result, *, url=None, mutations=None, html=None):
    node = os.environ.get("NODE") or shutil.which("node")
    assert node, "Node 24 is required for the M3 DOM acceptance gate."
    level = result["level"]
    payload = {
        "javascript": result["artifact"]["javascript"],
        "html": html or (FORMS / f"{level}.html").read_text(encoding="utf-8"),
        "url": url or f"https://www.bestpractices.dev/en/projects/123/{level}/edit",
        "mutations": mutations or [],
    }
    process = subprocess.run(
        [node, str(FORMS / "run_script.mjs")],
        input=json.dumps(payload),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    return json.loads(process.stdout)


@pytest.mark.parametrize("level", MANIFEST["levels"])
def test_each_source_derived_form_fills_all_metadata_and_selected_criterion(level):
    criterion = MANIFEST["levels"][level]["criterion_id"]
    draft = {name: "new" for name in ("name", "description", "license", "implementation_languages")}
    draft.update({f"{criterion}_status": "Met", f"{criterion}_justification": "explanation"})
    result = prepare(draft, level=level)
    actual = execute(result)
    assert actual["report"]["outcome"] == "filled"
    assert actual["report"]["filled_fields"] == sorted(draft)
    assert len(actual["events"]) == len(draft) * 2
    for control in actual["after"]:
        field = control["name"][8:-1]
        if field.endswith("_status"):
            assert control["checked"] == (control["value"] == "Met")
        else:
            assert control["value"] == draft[field]


@pytest.mark.parametrize(
    "path",
    [
        "/en/projects/123/passing/edit",
        "/projects/123/passing/edit",
        "/projects/123/passing/edit/",
        "/en/projects/123/passing/edit/?x=1#foo",
    ],
)
def test_exact_supported_routes(path):
    actual = execute(prepare({"name": "new"}), url="https://www.bestpractices.dev" + path)
    assert actual["report"]["outcome"] == "filled"


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/en/projects/123/passing/edit",
        "http://www.bestpractices.dev/en/projects/123/passing/edit",
        "https://www.bestpractices.dev:444/en/projects/123/passing/edit",
        "https://www.bestpractices.dev/en/projects/124/passing/edit",
        "https://www.bestpractices.dev/en/projects/123/silver/edit",
        "https://www.bestpractices.dev/fr/projects/123/passing/edit",
        "https://www.bestpractices.dev/en/projects/123/passing",
        "https://www.bestpractices.dev/en/projects/0123/passing/edit",
        "https://www.bestpractices.dev/en/projects/123/passing/edit//",
    ],
)
def test_wrong_route_preflight_never_mutates(url):
    actual = execute(prepare({"name": "new"}), url=url)
    assert actual["report"]["outcome"] == "preflight_failed"
    assert actual["before"] == actual["after"]
    assert actual["events"] == []


@pytest.mark.parametrize("action", ["remove", "disable", "readonly", "duplicate", "wrong_type"])
def test_one_bad_control_stops_every_assignment(action):
    actual = execute(
        prepare({"description": "new", "name": "new"}),
        mutations=[{"field": "name", "action": action}],
    )
    assert actual["report"]["outcome"] == "preflight_failed"
    assert actual["report"]["missing_fields"] == ["name"]
    assert actual["before"] == actual["after"]
    assert actual["events"] == []


def test_disabled_fieldset_is_detected():
    html = '<fieldset disabled><input name="project[name]" value="old"></fieldset>'
    actual = execute(prepare({"name": "new"}), html=html)
    assert actual["report"]["outcome"] == "preflight_failed"
    assert actual["before"] == actual["after"]


@pytest.mark.parametrize(
    "html",
    [
        '<input type="radio" name="project[build_status]" value="Unmet">',
        '<input type="radio" name="project[build_status]" value="Met">'
        '<input type="radio" name="project[build_status]" value="Met">',
        '<input type="text" name="project[build_status]" value="Met">',
        '<input type="radio" name="project[build_status]" value="Met" disabled>',
        '<input type="text" name="project[build_justification]" value="old">',
    ],
)
def test_wrong_or_ambiguous_criterion_controls_fail(html):
    field = "build_justification" if "justification" in html else "build_status"
    actual = execute(prepare({field: "new" if "justification" in field else "Met"}), html=html)
    assert actual["report"]["outcome"] == "preflight_failed"
    assert actual["before"] == actual["after"]


@pytest.mark.parametrize(
    ("action", "filled"),
    [
        ("throw_assignment", ["description"]),
        ("throw_dispatch", ["description", "name"]),
    ],
)
def test_direct_runtime_failures_report_partial_assignments_honestly(action, filled):
    actual = execute(
        prepare({"description": "new", "name": "new"}),
        mutations=[{"field": "name", "action": action}],
    )
    assert actual["report"]["outcome"] == "runtime_failed"
    assert actual["report"]["filled_fields"] == filled
    assert actual["report"]["failed_field"] == "name"
    assert actual["before"] != actual["after"]


def test_text_is_data_and_no_trim_is_applied():
    text = '\t "; globalThis.escaped = true; //\n</script>é\u2028\u2029 '
    result = prepare({"description": text}, {"description": "old"})
    actual = execute(result)
    assert actual["report"]["outcome"] == "filled"
    description = next(item for item in actual["after"] if item["name"] == "project[description]")
    assert description["value"] == text
    assert result["artifact"]["encoded_size_bytes"] == len(
        result["artifact"]["javascript"].encode()
    )
    assert result == prepare({"description": text}, {"description": "old"})


def test_script_replaces_values_without_url_override_and_can_clear_justification():
    draft = {"build_status": "Met", "build_justification": ""}
    result = prepare(draft, {"build_status": "Unmet", "build_justification": "old"})
    assert {item["expected_application"] for item in result["transfer"]} == {"replace"}
    assert "Execution replaces existing values" in result["artifact"]["instructions"]
    assert "independently of URL override settings" in result["artifact"]["instructions"]
    actual = execute(result)
    assert actual["report"]["outcome"] == "filled"
    assert (
        next(item for item in actual["after"] if item["name"] == "project[build_justification]")[
            "value"
        ]
        == ""
    )


@pytest.mark.parametrize(
    ("draft", "record", "outcome"),
    [
        ({}, {}, "no_supplied_transferable_answers"),
        ({"name": "old"}, {"name": "old"}, "no_changes"),
        ({"build_status": "?"}, {}, "no_transferable_changes"),
        ({"name": "new", "build_status": "?"}, {}, "partial"),
        ({"name": "new"}, {}, "complete"),
    ],
)
def test_scripts_share_all_five_outcomes(draft, record, outcome):
    result = prepare(draft, record)
    assert result["outcome"] == outcome
    assert (result["artifact"] is not None) == (outcome in {"complete", "partial"})
