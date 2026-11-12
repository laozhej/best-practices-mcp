"""Optional catalog comparison with a historical Ruby-generated fixture."""

import json
from pathlib import Path

from best_practices_mcp.contracts import validate_output
from best_practices_mcp.criteria import get_criteria

ROOT = Path(__file__).resolve().parents[2]
REVISION = "868e1677339a3fdb48851b0c2ae8862c553115eb"
COUNTS = {
    "passing": 67,
    "silver": 55,
    "gold": 23,
    "baseline-1": 24,
    "baseline-2": 19,
    "baseline-3": 21,
}


def test_all_six_levels_match_independent_ruby_source_oracle() -> None:
    oracle = json.loads(
        (ROOT / "tests/fixtures/upstream/criteria_oracle.json").read_text(encoding="utf-8")
    )
    assert oracle["source_revision"] == REVISION
    expected = {(row["level"], row["criterion_id"]): row for row in oracle["records"]}
    actual = {}
    for level, count in COUNTS.items():
        result = get_criteria(level)
        validate_output("get_criteria", result)
        assert len(result["criteria"]) == count
        for row in result["criteria"]:
            key = (level, row["criterion_id"])
            # The independent oracle retains upstream's raw flags. Public booleans
            # make the requirements entailed by those flags explicit.
            effective = dict(expected[key])
            effective["met_justification_required"] |= effective["met_url_required"]
            effective["na_allowed"] |= effective["na_justification_required"]
            assert {field: row[field] for field in effective} == effective
            actual[key] = row
    assert actual.keys() == expected.keys()
