"""Pure URL eligibility, override coupling, encoding and prediction contracts."""

from copy import deepcopy
from urllib.parse import parse_qs, urlsplit

import pytest

from best_practices_mcp.criteria import get_criteria
from best_practices_mcp.errors import DomainError
from best_practices_mcp.models import PrepareURLResult
from best_practices_mcp.proposals import prepare_update_url

OBSERVATION = {
    "project_id": 123,
    "source_url": "https://www.bestpractices.dev/projects/123.json",
    "fetched_at": "2026-11-09T00:00:00Z",
    "attribution": None,
    "license": None,
}
STATUS = "description_good_status"
JUST = "description_good_justification"


def prepare(draft, record=None, overrides=None, level="passing"):
    result = prepare_update_url(123, level, draft, record or {}, OBSERVATION, overrides)
    PrepareURLResult.model_validate(result)
    return result


def reports(result):
    return {item["field"]: item for item in result["transfer"]}


def params(result):
    return parse_qs(urlsplit(result["artifact"]["url"]).query, keep_blank_values=True)


@pytest.mark.parametrize(
    ("draft", "record", "outcome"),
    [
        ({STATUS: "Met"}, {}, "complete"),
        ({STATUS: "Met", "extra": 1}, {}, "partial"),
        ({STATUS: "Met"}, {STATUS: "Met"}, "no_changes"),
        ({STATUS: "?"}, {STATUS: "?"}, "no_transferable_changes"),
        ({}, {}, "no_supplied_transferable_answers"),
        ({"id": 123}, {}, "no_supplied_transferable_answers"),
        ({"access_continuity_status": 12}, {}, "no_supplied_transferable_answers"),
    ],
)
def test_outcomes(draft, record, outcome):
    result = prepare(draft, record)
    assert result["outcome"] == outcome
    assert (result["artifact"] is not None) == (outcome in {"complete", "partial"})
    assert result["no_artifact_reason"] == (None if result["artifact"] else outcome)


@pytest.mark.parametrize(
    ("saved", "forced", "expected"),
    [
        ("?", False, "fill"),
        ("", False, "fill"),
        (None, False, "fill"),
        ("Unmet", False, "retain_existing"),
        ("Unmet", True, "replace"),
        ("Met", True, "unchanged"),
        ("nonsense", True, "unknown"),
        (3, False, "unknown"),
    ],
)
def test_status_predictions(saved, forced, expected):
    result = prepare({STATUS: "Met"}, {STATUS: saved}, [STATUS] if forced else [])
    assert reports(result)[STATUS]["expected_application"] == expected


def test_missing_status_and_text_are_unknown_in_pure_generator():
    result = prepare({STATUS: "Met", JUST: "explanation", "name": "new"})
    assert {row["expected_application"] for row in result["transfer"]} == {"unknown"}


def test_status_override_propagates_before_status_pruning():
    result = prepare({STATUS: "Met", JUST: "new"}, {STATUS: "Met", JUST: "old"}, [STATUS, STATUS])
    assert result["requested_overrides"] == [STATUS]
    assert result["effective_overrides"] == [JUST]
    assert params(result) == {JUST: ["new"], "overrides": [JUST]}
    assert reports(result)[JUST]["expected_application"] == "replace"
    assert not reports(result)[STATUS]["override"]


def test_justification_override_cannot_bypass_blocked_status():
    result = prepare({STATUS: "Met", JUST: "new"}, {STATUS: "Unmet", JUST: "old"}, [JUST])
    assert reports(result)[STATUS]["expected_application"] == "retain_existing"
    assert reports(result)[JUST]["expected_application"] == "blocked_by_status"
    assert params(result)[STATUS] == ["Met"]
    assert params(result)[JUST] == ["new"]


@pytest.mark.parametrize(
    "override", ["*", "id", "repo_url", "absent", "access_continuity_status", "description_good"]
)
def test_overrides_reject_non_supplied_or_noncanonical_scope(override):
    with pytest.raises(DomainError, match="Override") as error:
        prepare({STATUS: "Met"}, overrides=[override])
    assert error.value.code == "invalid_override"


def test_overrides_reject_alias_even_when_draft_alias_normalized():
    alias = "OSPS-AC-01.01_status"
    with pytest.raises(DomainError) as error:
        prepare({alias: "Met"}, overrides=[alias], level="baseline-1")
    assert error.value.code == "invalid_override"


@pytest.mark.parametrize("status", [None, [], True, 1, "bad", "N/A"])
def test_invalid_status_omits_companion_without_validation_gate(status):
    result = prepare({STATUS: status, JUST: "standalone", "name": "new"})
    assert reports(result)[STATUS]["disposition"] == "invalid"
    assert reports(result)[JUST]["reason"] == "invalid_companion_status"
    assert result["outcome"] == "partial"
    assert params(result) == {"name": ["new"]}


def test_unknown_status_does_not_block_valid_justification():
    result = prepare({STATUS: "?", JUST: "standalone"}, {JUST: ""})
    assert result["outcome"] == "partial"
    assert reports(result)[JUST]["expected_application"] == "fill"
    assert params(result) == {JUST: ["standalone"]}


def test_bad_justification_does_not_block_status_or_apply_evidence_validation():
    result = prepare({STATUS: "Met", JUST: None}, {STATUS: "?"})
    assert result["outcome"] == "partial"
    assert params(result) == {STATUS: ["Met"]}


@pytest.mark.parametrize(
    ("value", "saved", "expected"),
    [
        (" \tnew\r\n", "old", "retain_existing"),
        (" \tnew\r\n", "new", "unchanged"),
        ("\x00new\x00", "new", "unchanged"),
        ("\u00a0new\u00a0", "new", "retain_existing"),
        ("new", "\u00a0", "fill"),
        ("", "", "unchanged"),
    ],
)
def test_ruby_strip_and_rails_blank_predictions(value, saved, expected):
    result = prepare({JUST: value}, {JUST: saved})
    assert reports(result)[JUST]["expected_application"] == expected
    if result["artifact"]:
        assert params(result)[JUST] == [value]


def test_raw_unicode_reserved_and_empty_values_are_encoded_exactly_once():
    text = ' é +&=%20?/#\n"; alert(1); //'
    result = prepare(
        {JUST: text, "description": ""}, {JUST: "old", "description": "old"}, [JUST, "description"]
    )
    url = result["artifact"]["url"]
    assert params(result)[JUST] == [text]
    assert params(result)["description"] == [""]
    assert "%20" in url and "+" not in url
    assert result["artifact"]["encoded_size_bytes"] == len(url.encode())


def test_all_metadata_fields_available_at_all_levels():
    draft = {name: "new" for name in ("name", "description", "license", "implementation_languages")}
    for level in get_criteria()["levels"]:
        result = prepare(draft, level=level)
        assert result["outcome"] == "complete"
        assert set(params(result)) == set(draft)


def test_long_valid_values_are_neither_truncated_nor_advisory_gated():
    text = "x" * 50000
    result = prepare({JUST: text})
    assert params(result)[JUST] == [text]


def test_inputs_are_not_mutated_and_provenance_is_never_encoded():
    draft = {"id": 123, "repo_url": "https://example.com/repo", STATUS: "Met", "extra": [1]}
    original = deepcopy(draft)
    record = {"repo_url": "https://example.com/repo"}
    result = prepare(draft, record)
    assert draft == original
    assert params(result) == {STATUS: ["Met"]}
    assert result["identity"]["repo_check"] == "matched"
    assert [row["field"] for row in result["transfer"]] == sorted(draft)


def test_identity_mismatch_stops_artifact():
    with pytest.raises(DomainError) as error:
        prepare({"id": 124, STATUS: "Met"})
    assert error.value.code == "project_mismatch"
