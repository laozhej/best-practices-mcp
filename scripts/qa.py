"""Run offline milestone checks and render a small, local owner-QA report."""

from __future__ import annotations

import argparse
import hashlib
import html
import importlib.metadata
import json
import platform
import re
import subprocess
import sys
import time
import webbrowser
from datetime import UTC, datetime
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parents[1]
MILESTONES = tuple(f"M{i}" for i in range(7))
SUITES = {
    "M0": ("check", "example"),
    "M6": ("check", "catalog-check", "workflow-check", "lock-check", "test-package"),
    "M1": ("check", "test-contract", "test-catalog", "test-protocol", "test-package", "test-qa"),
    "M2": ("check", "test-network", "test-api", "test-host", "test-protocol", "test-package"),
    "M5": (
        "check",
        "test-coverage",
        "test-package",
        "catalog-check",
        "test-upstream",
        "demo-m3",
        "demo-m4",
    ),
    "M4": (
        "check",
        "test-contract",
        "test-storage",
        "test-documents",
        "test-host",
        "test-protocol",
        "test-package",
        "test-qa",
        "demo-m4",
    ),
    "M3": (
        "check",
        "test-contract",
        "test-documents",
        "test-upstream",
        "test-host",
        "test-protocol",
        "test-package",
        "test-qa",
        "demo-m3",
    ),
}


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def source_fingerprint(root: Path) -> str:
    """Ignore report/docs-only edits; include tracked and new implementation inputs."""
    names = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    digest = hashlib.sha256()
    for name in sorted(set(names.split("\0"))):
        path = root / name
        relevant = name.split("/", 1)[0] in {"src", "tests", "scripts", "vendor", "examples"}
        relevant |= name.startswith(".github/")
        relevant |= name in {
            "Makefile",
            "pyproject.toml",
            "MANIFEST.in",
            "package.json",
            "package-lock.json",
            ".nvmrc",
            "uv.lock",
            ".tool-versions",
            "codecov.yml",
            "LICENSE",
            "THIRD_PARTY_NOTICES.md",
        }
        if relevant and path.is_file():
            digest.update(name.encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def tool_version(command: list[str]) -> str:
    try:
        return subprocess.check_output(
            command, text=True, stderr=subprocess.DEVNULL, timeout=5
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "not installed"


def environment() -> dict[str, str]:
    versions = {}
    for package in ("mcp", "pydantic"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not installed"
    jsdom = ROOT / "node_modules" / "jsdom" / "package.json"
    return {
        "python": platform.python_version(),
        "os": f"{platform.system()} {platform.release()}",
        "mcp_sdk": versions["mcp"],
        "pydantic": versions["pydantic"],
        "node": tool_version(["node", "--version"]),
        "jsdom": json.loads(jsdom.read_text())["version"] if jsdom.exists() else "not installed",
    }


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sanitize(text: str, root: Path) -> str:
    """Local logs are transient; still remove local account paths and URL queries."""
    text = text.replace(str(root), "<repo>").replace(str(Path.home()), "<home>")
    return re.sub(r"(https?://[^\s?]+)\?[^\s]+", r"\1?<redacted>", text)


def run_check(root: Path, milestone: str, target: str) -> dict:
    command = ["make", target, f"PYTHON={sys.executable}"]
    started = now()
    clock = time.monotonic()
    try:
        completed = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=600)
        code, output = completed.returncode, completed.stdout + completed.stderr
    except (OSError, subprocess.TimeoutExpired) as error:
        code, output = 1, f"Check could not complete: {type(error).__name__}"
    log = root / "build" / "qa" / milestone / f"{target}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(sanitize(output, root), encoding="utf-8")
    # Keep evidence free of answer bodies and paths: only status/counts, never raw failures.
    counts = re.findall(r"\b\d+ (?:passed|failed|skipped|errors?)\b", output)
    return {
        "target": target,
        "command": f"make {target}",
        "status": "passed" if code == 0 else "failed",
        "exit_code": code,
        "started_at": started,
        "finished_at": now(),
        "duration_seconds": round(time.monotonic() - clock, 2),
        "result": ", ".join(dict.fromkeys(counts)) or f"Command exited {code}.",
        "transient_log": log.relative_to(root).as_posix(),
    }


def run_suite(root: Path, milestone: str) -> int:
    if milestone not in SUITES:
        print(f"{milestone}: verification suite is not implemented.", file=sys.stderr)
        return 2
    before = source_fingerprint(root)
    evidence = {
        "origin": "current_run",
        "milestone": milestone,
        "tested_commit": git(root, "rev-parse", "HEAD"),
        "dirty_worktree": bool(git(root, "status", "--porcelain")),
        "source_fingerprint": before,
        "environment": environment(),
        "started_at": now(),
        "checks": [],
    }
    for target in SUITES[milestone]:
        result = run_check(root, milestone, target)
        evidence["checks"].append(result)
        print(f"{target}: {result['status']} ({result['duration_seconds']}s)", flush=True)
    evidence["finished_at"] = now()
    evidence["source_changed_during_run"] = before != source_fingerprint(root)
    save_json(root / "build" / "qa" / milestone / "results.json", evidence)
    failed = any(check["status"] != "passed" for check in evidence["checks"])
    return int(failed or evidence["source_changed_during_run"])


def load_evidence(root: Path, milestone: str) -> tuple[dict, str | None]:
    base = root / "build" / "qa" / milestone
    for name in ("results.json", "baseline.json"):
        path = base / name
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8")), f"{milestone}/{name}"
    return {}, None


def manual_commitment(title: str) -> dict:
    return {
        "title": title,
        "manual": {"status": "not run", "result": "", "evidence": ""},
    }


def default_notes(milestone: str) -> dict:
    """Start new reports without inheriting any historical review or acceptance."""
    commitments = [
        {"title": f"Local verification: {target}", "target": target} for target in SUITES[milestone]
    ]
    if milestone == "M6":
        commitments += [
            manual_commitment(title)
            for title in (
                "Extraction: curated documents, verified archive and screenshot selection review",
                "Release: exact wheel and sdist qualification in fresh environments",
                "Release: new-repository CI matrix and release/security service configuration",
                "Release: public repository and approved PyPI Trusted Publisher environment",
                "Release: published beta installation QA and separate stable release validation",
            )
        ]
    return {
        "title": f"{milestone} current-checkout verification",
        "summary": (
            "This report records checks against the current checkout. It does not reproduce "
            "historical milestone approvals or authorize publication."
        ),
        "prerequisites": (
            "Run from the repository root after make setup and make setup-dom. "
            "M6 additionally requires actionlint on PATH (or ACTIONLINT configured). "
            "Commands use the project's venv and synthetic data; no BadgeApp saves occur."
        ),
        "commitments": commitments,
        "verification": [
            {
                "command": f"make qa MILESTONE={milestone}",
                "expected": "Local checks pass with recorded results; manual gates stay separate.",
                "duration": "Typically a few minutes",
                "effects": "Writes temporary test/build files and local evidence under build/qa",
            },
            {
                "command": (
                    f"make qa-report MILESTONE={milestone}\nmake qa-open MILESTONE={milestone}"
                ),
                "expected": "Display current evidence, pending commitments and recorded reviews.",
                "duration": "A few seconds",
                "effects": "Writes HTML and opens the local report; does not rerun checks",
            },
        ],
        "decisions": [],
        "questions": ["Record unresolved questions and supporting review evidence in local notes."],
        "limitations": [
            "Local checks do not establish remote CI readiness or published-package behavior.",
            "Release setup and publication checks may follow clean-repository extraction; "
            "their pending status does not by itself block extraction.",
            "Historical milestone records remain in docs/planning/initial-implementation/.",
        ],
        "next_steps": (
            f"Edit build/qa/{milestone}/notes.json with decisions, remaining questions and "
            "actual review/verification evidence, then regenerate this report."
        ),
        "review": {
            "implementer": "Record completion after validation.",
            "independent_status": "not yet reviewed",
            "independent": "No review recorded for this run.",
            "owner": "not yet reviewed",
        },
    }


def load_notes(root: Path, milestone: str) -> dict:
    path = root / "build" / "qa" / milestone / "notes.json"
    if not path.exists():
        save_json(path, default_notes(milestone))
    return json.loads(path.read_text(encoding="utf-8"))


def freshness(root: Path, evidence: dict) -> str:
    if not evidence:
        return "not run"
    if evidence.get("origin") == "historical":
        return "historical — not re-run"
    if evidence.get("source_changed_during_run"):
        return "stale — implementation changed during checks"
    if evidence.get("source_fingerprint") != source_fingerprint(root):
        return "stale — implementation changed after checks"
    return "current for implementation inputs"


def commitment_rows(notes: dict, evidence: dict, state: str) -> list[dict]:
    checks = {item["target"]: item for item in evidence.get("checks", [])}
    rows = []
    for item in notes["commitments"]:
        row = {**item, "status": "not run", "result": "No recorded evidence."}
        if target := item.get("target"):
            row.update({key: checks.get(target, row)[key] for key in ("status", "result")})
        elif manual := item.get("manual"):
            if manual.get("evidence") and manual.get("result"):
                row.update(status=manual["status"], result=manual["result"])
        if state.startswith("stale") and row["status"] == "passed":
            row.update(status="not run", result=f"Previous pass is {state}; rerun required.")
        rows.append(row)
    return rows


def verification_failure(rows: list[dict], state: str) -> str | None:
    if any(row["status"] == "failed" for row in rows):
        return "not passed — required verification failed"
    if state == "not run" or state.startswith("stale"):
        return "not passed — evidence missing or stale"
    if not rows or any(row["status"] not in {"passed", "not applicable"} for row in rows):
        return "not passed — required verification incomplete"
    return None


def gate_status(notes: dict, rows: list[dict], state: str) -> str:
    required = [row for row in rows if row.get("required", True)]
    if failure := verification_failure(required, state):
        return failure
    if notes["review"]["independent_status"] != "approved":
        return "awaiting independent review"
    return "historical approval — not revalidated" if state.startswith("historical") else "passed"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def table(headers: tuple[str, ...], rows: list[tuple]) -> str:
    heading = "".join(f"<th scope='col'>{esc(label)}</th>" for label in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>" for row in rows
    )
    return (
        f"<div class='table-wrap'><table><thead><tr>{heading}</tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )


def bullet_list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>"


def live_qa_section(notes: dict) -> str:
    worksheet = notes.get("live_qa")
    if not worksheet:
        return ""
    cases = table(
        ("Case", "Expected edit-form behavior", "Observed result"),
        [(item["case"], item["expected"], "not run") for item in worksheet["cases"]],
    )
    return (
        "<h2>Optional live BadgeApp QA — not run</h2>"
        f"<p>{esc(worksheet['boundary'])}</p>"
        "<p>Record private project details locally; this report contains no authenticated data.</p>"
        + bullet_list(worksheet["steps"])
        + cases
    )


def render_sections(notes: dict, evidence: dict, rows: list[dict]) -> dict[str, str]:
    commitments = table(
        ("Commitment", "Status", "Check", "Observed result", "Evidence reference"),
        [
            (
                r["title"],
                r["status"],
                r.get("target", "manual review"),
                r["result"],
                r.get("manual", {}).get("evidence", "Recorded checks below"),
            )
            for r in rows
        ],
    )
    checks = table(
        ("Command", "Exit", "Execution time", "Duration", "Observed result"),
        [
            (
                c["command"],
                c.get("exit_code", "not recorded"),
                c.get("started_at", "not recorded"),
                c.get("duration_seconds", "not recorded"),
                c["result"],
            )
            for c in evidence.get("checks", [])
        ],
    )
    steps = "".join(
        f"<li><pre><code>{esc(step['command'])}</code></pre><p>{esc(step['expected'])}</p>"
        f"<p class='muted'>{esc(step['duration'])} · {esc(step['effects'])}</p></li>"
        for step in notes["verification"]
    )
    review = notes["review"]
    return {
        "commitments": commitments,
        "live_qa": live_qa_section(notes),
        "checks": checks,
        "decisions": bullet_list(notes["decisions"]),
        "steps": f"<ol>{steps}</ol>",
        "questions": bullet_list(notes["questions"] or ["No open questions."]),
        "limitations": bullet_list(notes["limitations"]),
        "review": table(
            ("Role", "Status"),
            [
                ("Implementer", review["implementer"]),
                ("Independent review", review["independent_status"] + ": " + review["independent"]),
                ("Owner feedback", review.get("owner", "not yet reviewed")),
            ],
        ),
    }


def render_report(root: Path, milestone: str) -> Path:
    notes = load_notes(root, milestone)
    evidence, link = load_evidence(root, milestone)
    state = freshness(root, evidence)
    rows = commitment_rows(notes, evidence, state)
    sections = render_sections(notes, evidence, rows)
    previous = (
        f"<a href='M{int(milestone[1:]) - 1}.html'>Previous milestone</a> · "
        if milestone != "M0"
        and (root / "build" / "qa" / f"M{int(milestone[1:]) - 1}.html").is_file()
        else ""
    )
    evidence_link = (
        f"<a href='{esc(link)}'>Recorded evidence JSON</a>" if link else "No evidence recorded"
    )
    if (root / "build" / "qa" / milestone / "review.md").exists():
        evidence_link += f" · <a href='{esc(milestone)}/review.md'>Independent review record</a>"
    metadata = table(
        ("Evidence", "Value"),
        [
            ("Freshness", state),
            ("Tested implementation commit", evidence.get("tested_commit", "not recorded")),
            ("Dirty worktree at run", evidence.get("dirty_worktree", "not recorded")),
            ("Environment", json.dumps(evidence.get("environment", {}), sort_keys=True)),
            (
                "Evidence started / finished",
                f"{evidence.get('started_at', 'not recorded')} / "
                f"{evidence.get('finished_at', 'not recorded')}",
            ),
            ("Report rendered (UTC)", now()),
        ],
    )
    template = Template((root / "scripts" / "qa_template.html").read_text(encoding="utf-8"))
    page = template.substitute(
        milestone=esc(milestone),
        title=esc(notes["title"]),
        summary=esc(notes["summary"]),
        gate=esc(gate_status(notes, rows, state)),
        metadata=metadata,
        evidence=evidence_link,
        previous=previous,
        prerequisites=esc(notes["prerequisites"]),
        next_steps=esc(notes["next_steps"]),
        **sections,
    )
    path = root / "build" / "qa" / f"{milestone}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path


def open_report(root: Path, milestone: str) -> int:
    path = root / "build" / "qa" / f"{milestone}.html"
    if not path.is_file():
        print(f"Report missing: run make qa-report MILESTONE={milestone} first.", file=sys.stderr)
        return 1
    print(path.resolve())
    try:
        webbrowser.open(path.resolve().as_uri())
    except (webbrowser.Error, OSError):
        pass  # The printed path is the portable fallback.
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "report", "open"))
    parser.add_argument("--milestone", required=True, choices=MILESTONES)
    args = parser.parse_args()
    if args.action == "run":
        return run_suite(ROOT, args.milestone)
    if args.action == "open":
        return open_report(ROOT, args.milestone)
    try:
        print(render_report(ROOT, args.milestone))
    except (OSError, ValueError, KeyError) as error:
        print(f"Cannot render report: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
