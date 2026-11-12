"""Required integrity checks for pinned documents and synthetic form sources.

Hash verification establishes provenance, not a normative behavior contract.
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_retained_source_hashes():
    source = ROOT / "vendor/badgeapp-m3"
    manifest = json.loads((source / "source.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == expected


def test_form_fixture_provenance_matches_retained_upstream_sources():
    forms = json.loads((ROOT / "tests/fixtures/forms/provenance.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "vendor/badgeapp-m3/source.json").read_text(encoding="utf-8"))
    assert forms["upstream_revision"] == manifest["revision"]
    for name, expected in forms["source_sha256"].items():
        assert manifest["files"][name] == expected
