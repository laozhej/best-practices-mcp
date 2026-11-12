"""Required URL contract examples derived from documentation, not executed Ruby.

Sources retained in vendor/badgeapp-m3/docs/:
* automation-approach.md, "The Decision Matrix": blank/equal/different values,
  default retention, forcing, and the status/justification coupling rule.
* automation-proposals.md, "URL Format", "Justification Values", and "overrides":
  edit-form proposals, raw URL encoding, and explicit override scope.

Additional accepted limits (unknown resets, exact-only overrides, ASCII strip /
Unicode blank compatibility) are covered by tests/test_proposals.py and specified
in docs/transfer-rules.md. Neither suite predicts a Save/Submit result.
"""

from urllib.parse import parse_qs, urlsplit

import pytest

from best_practices_mcp.proposals import prepare_update_url

STATUS = "description_good_status"
JUST = "description_good_justification"
OBSERVATION = {
    "project_id": 123,
    "source_url": "https://www.bestpractices.dev/projects/123.json",
    "fetched_at": "2026-11-09T00:00:00Z",
    "attribution": None,
    "license": None,
}


@pytest.mark.parametrize("field", [JUST, "description"], ids=["justification", "metadata"])
@pytest.mark.parametrize(
    "saved,proposed,forced,expected",
    [
        pytest.param("", "new text", False, "fill", id="blank-default"),
        pytest.param("", "new text", True, "fill", id="blank-forced"),
        pytest.param("old text", "new text", False, "retain_existing", id="retain-default"),
        pytest.param("old text", "new text", True, "replace", id="replace-forced"),
        pytest.param("same text", "same text", False, "unchanged", id="equal-default"),
        pytest.param("same text", "same text", True, "unchanged", id="equal-forced"),
        pytest.param("old text", "", False, "retain_existing", id="empty-default"),
        pytest.param("old text", "", True, "replace", id="empty-forced"),
    ],
)
def test_documented_nonstatus_matrix(field, saved, proposed, forced, expected):
    result = prepare_update_url(
        123, "passing", {field: proposed}, {field: saved}, OBSERVATION, [field] if forced else []
    )
    assert result["transfer"][0]["expected_application"] == expected
    if expected == "unchanged":
        assert result["artifact"] is None
    else:
        query = parse_qs(urlsplit(result["artifact"]["url"]).query, keep_blank_values=True)
        assert query == {field: [proposed], **({"overrides": [field]} if forced else {})}
        # A standalone justification requires no invented status parameter.
        assert STATUS not in query


@pytest.mark.parametrize(
    "saved_status,status_overrides,expected_status,expected_justification,effective",
    [
        pytest.param("Met", [], "unchanged", "replace", [JUST], id="equal-status-does-not-block"),
        pytest.param(
            "Unmet",
            [],
            "retain_existing",
            "blocked_by_status",
            [JUST],
            id="different-status-blocks",
        ),
        pytest.param(
            "Unmet", [STATUS], "replace", "replace", [JUST, STATUS], id="forced-status-allows"
        ),
    ],
)
def test_documented_status_coupling(
    saved_status, status_overrides, expected_status, expected_justification, effective
):
    result = prepare_update_url(
        123,
        "passing",
        {STATUS: "Met", JUST: "new wording"},
        {STATUS: saved_status, JUST: "old wording"},
        OBSERVATION,
        [JUST, *status_overrides],
    )
    rows = {row["field"]: row for row in result["transfer"]}
    assert rows[STATUS]["expected_application"] == expected_status
    assert rows[JUST]["expected_application"] == expected_justification
    assert result["effective_overrides"] == effective
    query = parse_qs(urlsplit(result["artifact"]["url"]).query)
    assert query[JUST] == ["new wording"]
    # Keep a differing status in the proposal so pruning cannot bypass coupling.
    assert (STATUS in query) == (saved_status != "Met")


@pytest.mark.parametrize(
    "level", ["passing", "silver", "gold", "baseline-1", "baseline-2", "baseline-3"]
)
def test_documented_edit_route_and_raw_url_values(level):
    text = "  café & source=https://example.org/a?b=1#fragment\n"
    result = prepare_update_url(123, level, {"description": text}, {"description": ""}, OBSERVATION)
    artifact = result["artifact"]
    url = urlsplit(artifact["url"])
    assert (url.scheme, url.netloc, url.path) == (
        "https",
        "www.bestpractices.dev",
        f"/en/projects/123/{level}/edit",
    )
    assert parse_qs(url.query) == {"description": [text]}
    assert url.fragment == ""
    assert artifact["encoded_size_bytes"] == len(artifact["url"].encode("utf-8"))
