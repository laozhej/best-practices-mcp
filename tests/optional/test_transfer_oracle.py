"""Optional compatibility comparisons against Ruby-generated historical fixtures.

These checks supplement the documented contract; they do not define it or model
BadgeApp Save/Submit behavior. Run explicitly through make oracle-check.
"""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from best_practices_mcp.proposals import prepare_update_url

ROOT = Path(__file__).resolve().parents[2]
ORACLE = json.loads((ROOT / "tests/fixtures/upstream/m3_oracle.json").read_text(encoding="utf-8"))
STATUS = "description_good_status"
JUST = "description_good_justification"
OBSERVATION = {
    "project_id": 123,
    "source_url": "https://www.bestpractices.dev/projects/123.json",
    "fetched_at": "2026-11-09T00:00:00Z",
    "attribution": None,
    "license": None,
}


@pytest.mark.parametrize("case", ORACLE["cases"])
def test_url_predictions_match_pinned_controller(case):
    result = prepare_update_url(
        123, "passing", case["draft"], {"id": 123, **case["record"]}, OBSERVATION, case["overrides"]
    )
    expected = case["expected"]
    rows = {r["field"]: r for r in result["transfer"]}
    for field, old in case["record"].items():
        after = expected["saved_after"][field]
        if field == JUST and STATUS in expected["blocked_statuses"]:
            prediction = "blocked_by_status"
        elif after == old:
            proposed = case["draft"][field]
            proposed = proposed if field == STATUS else proposed.strip("\x00\t\n\v\f\r ")
            prediction = "unchanged" if proposed == old else "retain_existing"
        else:
            prediction = "fill" if old in ("", "?") else "replace"
        assert rows[field]["expected_application"] == prediction
    if result["artifact"]:
        query = parse_qs(urlsplit(result["artifact"]["url"]).query, keep_blank_values=True)
        for field in (STATUS, JUST):
            if field in query:
                assert query[field] == [case["draft"][field]]
        encoded = {r["field"] for r in rows.values() if r["disposition"] == "encoded"}
        assert result["effective_overrides"] == sorted(
            set(expected["effective_overrides"]) & encoded
        )


def test_oracle_revision_matches_retained_sources():
    manifest = json.loads((ROOT / "vendor/badgeapp-m3/source.json").read_text(encoding="utf-8"))
    assert ORACLE["revision"] == manifest["revision"]
