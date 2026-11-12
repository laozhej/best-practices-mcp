"""Optional compatibility check against Ruby-generated predicate observations."""

import json
from pathlib import Path

import pytest

from best_practices_mcp.validation import contains_url, usable_justification

_ORACLE = json.loads(
    (Path(__file__).resolve().parents[2] / "tests/fixtures/upstream/m3_oracle.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("case", _ORACLE["predicates"])
def test_independently_executed_pinned_ruby_predicates(case: dict) -> None:
    assert usable_justification(case["text"]) == case["justification_good"]
    assert contains_url(case["text"]) == case["contains_url"]
