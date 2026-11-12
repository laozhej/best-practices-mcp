"""The owner report must preserve evidence status, not manufacture acceptance."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("qa", ROOT / "scripts" / "qa.py")
assert SPEC and SPEC.loader
qa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qa)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_EDITOR", "true")
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "sample.py").write_text("value = 1\n")
    (tmp_path / "build" / "qa").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "qa_template.html").write_text(
        (ROOT / "scripts" / "qa_template.html").read_text(encoding="utf-8"), encoding="utf-8"
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "Fixture",
        ],
        cwd=tmp_path,
        check=True,
    )
    return tmp_path


def notes() -> dict:
    return {
        "title": "Synthetic report",
        "summary": "Fixture evidence only.",
        "prerequisites": "None",
        "commitments": [{"title": "Required check", "target": "check"}],
        "verification": [],
        "decisions": [],
        "questions": [],
        "limitations": [],
        "next_steps": "Review the result.",
        "review": {
            "implementer": "Fixture",
            "independent_status": "approved",
            "independent": "Fixture review",
        },
    }


def test_source_freshness_ignores_report_edits_but_detects_code(repo: Path) -> None:
    before = qa.source_fingerprint(repo)
    (repo / "build" / "qa" / "M1.html").write_text("new report")
    assert qa.source_fingerprint(repo) == before
    (repo / "src" / "sample.py").write_text("value = 2\n")
    assert qa.source_fingerprint(repo) != before
    assert qa.freshness(repo, {"source_fingerprint": before}).startswith("stale")


def test_failed_command_is_recorded_and_propagates(repo: Path, monkeypatch) -> None:
    monkeypatch.setitem(qa.SUITES, "M1", ("missing-target",))
    assert qa.run_suite(repo, "M1") == 1
    evidence, _ = qa.load_evidence(repo, "M1")
    assert evidence["checks"][0]["status"] == "failed"
    assert evidence["checks"][0]["exit_code"] != 0
    assert "make missing-target" == evidence["checks"][0]["command"]
    assert str(repo) not in json.dumps(evidence)


def test_unimplemented_milestone_cannot_succeed(repo: Path, monkeypatch) -> None:
    monkeypatch.delitem(qa.SUITES, "M6")
    assert qa.run_suite(repo, "M6") == 2
    assert not (repo / "build" / "qa" / "M6").exists()


def test_new_report_has_no_inherited_approval_or_dangling_previous_link(repo: Path) -> None:
    report = qa.render_report(repo, "M1")
    page = report.read_text(encoding="utf-8")
    assert report == repo / "build" / "qa" / "M1.html"
    assert "Previous milestone" not in page
    assert "not yet reviewed" in page
    assert "not passed — evidence missing or stale" in page
    assert (repo / "build" / "qa" / "M1" / "notes.json").is_file()
    assert not (repo / "docs" / "qa").exists()


def test_m6_local_checks_leave_release_and_review_commitments_pending(repo, monkeypatch):
    allowed = {"check", "catalog-check", "workflow-check", "lock-check", "test-package"}

    def successful_check(_root, _milestone, target):
        assert target in allowed
        return {
            "target": target,
            "status": "passed",
            "duration_seconds": 0,
            "result": "Fixture pass",
            "command": f"make {target}",
        }

    monkeypatch.setattr(qa, "run_check", successful_check)
    monkeypatch.setattr(qa, "environment", lambda: {})
    assert qa.run_suite(repo, "M6") == 0
    evidence, link = qa.load_evidence(repo, "M6")
    assert link == "M6/results.json"
    data = qa.load_notes(repo, "M6")
    data["review"]["independent_status"] = "approved"
    state = qa.freshness(repo, evidence)
    rows = qa.commitment_rows(data, evidence, state)
    assert {row["target"] for row in rows if "target" in row} == allowed
    assert all(row["status"] == "not run" for row in rows if "manual" in row)
    assert qa.gate_status(data, rows, state) == "not passed — required verification incomplete"
    assert any("does not by itself block extraction" in text for text in data["limitations"])


def test_m5_gate_runs_documented_conformance_without_optional_ruby(repo, monkeypatch):
    called = []

    def run_required(_root, _milestone, target):
        assert target != "oracle-check", "Required QA invoked an optional maintainer check"
        called.append(target)
        return {"target": target, "status": "passed", "duration_seconds": 0}

    monkeypatch.setattr(qa, "run_check", run_required)
    monkeypatch.setattr(qa, "environment", lambda: {})
    assert qa.run_suite(repo, "M5") == 0
    assert "test-upstream" in called
    evidence, _ = qa.load_evidence(repo, "M5")
    assert [check["target"] for check in evidence["checks"]] == called


def test_render_escapes_and_never_runs_checks(repo: Path, monkeypatch) -> None:
    data = notes()
    data["summary"] = '<script>alert("bad")</script>'
    qa.save_json(repo / "build" / "qa" / "M1" / "notes.json", data)
    monkeypatch.setattr(qa, "run_check", lambda *_: pytest.fail("report ran a check"))
    page = qa.render_report(repo, "M1").read_text(encoding="utf-8")
    assert "<script>" not in page
    assert "&lt;script&gt;" in page
    assert "not passed — evidence missing or stale" in page
    assert "not yet reviewed" in page
    assert "No evidence recorded" in page


def test_stale_pass_and_pending_review_do_not_pass_gate(repo: Path) -> None:
    data = notes()
    data["review"]["independent_status"] = "not yet reviewed"
    evidence = {
        "source_fingerprint": "outdated",
        "checks": [
            {"target": item["target"], "status": "passed", "result": "OK"}
            for item in data["commitments"]
            if "target" in item
        ],
    }
    state = qa.freshness(repo, evidence)
    rows = qa.commitment_rows(data, evidence, state)
    assert rows[0]["status"] == "not run"
    assert qa.gate_status(data, rows, state).startswith("not passed")
    rows = [{"status": "passed"}]
    assert (
        qa.gate_status(data, rows, "current for implementation inputs")
        == "awaiting independent review"
    )


def test_historical_baseline_is_not_presented_as_current(repo: Path) -> None:
    evidence = {
        "origin": "historical",
        "checks": [{"target": "check", "status": "passed", "result": "Recorded fixture pass"}],
    }
    data = notes()
    state = qa.freshness(repo, evidence)
    rows = qa.commitment_rows(data, evidence, state)
    assert state == "historical — not re-run"
    assert qa.gate_status(data, rows, state) == "historical approval — not revalidated"


def test_open_missing_report_fails_without_browser(repo: Path, monkeypatch) -> None:
    monkeypatch.setattr(qa.webbrowser, "open", lambda *_: pytest.fail("browser called"))
    assert qa.open_report(repo, "M1") == 1


def test_sanitizer_removes_account_paths_and_url_queries(repo: Path) -> None:
    result = qa.sanitize(
        f"{repo}/file {Path.home()}/secret https://example.org/edit?answer=secret", repo
    )
    assert str(repo) not in result
    assert str(Path.home()) not in result
    assert "answer=secret" not in result


def test_optional_check_missing_does_not_hide_required_passes() -> None:
    data = notes()
    data["review"]["independent_status"] = "approved"
    rows = [{"status": "passed"}, {"status": "not run", "required": False}]
    assert qa.gate_status(data, rows, "current for implementation inputs") == "passed"


def test_browser_failure_still_prints_local_path(repo: Path, monkeypatch, capsys) -> None:
    report = repo / "build" / "qa" / "M1.html"
    report.write_text("report")

    def unavailable(_url):
        raise OSError("No browser available")

    monkeypatch.setattr(qa.webbrowser, "open", unavailable)
    assert qa.open_report(repo, "M1") == 0
    assert str(report) in capsys.readouterr().out


def test_demo_changes_invalidate_qa_evidence(repo: Path) -> None:
    (repo / "examples").mkdir()
    demo = repo / "examples" / "host.py"
    demo.write_text("print('demo')\n")
    before = qa.source_fingerprint(repo)
    demo.write_text("raise RuntimeError('broken demo')\n")
    assert qa.freshness(repo, {"source_fingerprint": before}).startswith("stale")


@pytest.mark.parametrize(
    "name",
    [
        "package-lock.json",
        "uv.lock",
        ".tool-versions",
        "codecov.yml",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        ".github/dependabot.yml",
        ".github/release-please-config.json",
    ],
)
def test_dependency_and_release_input_changes_invalidate_evidence(repo, name):
    lock = repo / name
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("{}")
    before = qa.source_fingerprint(repo)
    lock.write_text('{"changed":true}')
    assert qa.freshness(repo, {"source_fingerprint": before}).startswith("stale")


def test_live_worksheet_stays_not_run_and_escapes_content():
    rendered = qa.live_qa_section(
        {
            "live_qa": {
                "boundary": "<script>unsafe</script>",
                "steps": ["Inspect only"],
                "cases": [{"case": "Override", "expected": "Replace form value"}],
            }
        }
    )
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "not run" in rendered
    assert qa.live_qa_section({}) == ""


def test_workflow_changes_invalidate_qa_evidence(repo):
    workflow = repo / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: checks\n", encoding="utf-8")
    before = qa.source_fingerprint(repo)
    workflow.write_text("name: changed checks\n", encoding="utf-8")
    assert qa.freshness(repo, {"source_fingerprint": before}).startswith("stale")
