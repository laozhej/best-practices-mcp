"""Offline stored-mode host demo using disposable storage and real MCP sessions."""

import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_session(temporary: Path, commands: list[str]) -> str:
    server = shlex.join([sys.executable, str(ROOT / "tests/fixtures/read_server.py")])
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "examples/host.py"),
            "--server-command",
            server,
            "--mode",
            "stored",
            "--data-dir",
            str(temporary / "server-data"),
        ],
        input="\n".join(commands) + "\n",
        text=True,
        encoding="utf-8",
        capture_output=True,
        cwd=ROOT,
        timeout=45,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"Host demo failed: {completed.stderr}")
    return completed.stdout


def first_session(temporary: Path) -> str:
    """Create via first edit, reject one patch, and generate without validation."""
    return run_session(
        temporary,
        [
            "find",
            "123",
            "123",
            "edit",
            "name",
            "Stored fixture — café Ω",
            "level",
            "passing",
            "edit",
            "description_good_status",
            "Met",
            "export",
            "document",
            str(temporary / "before.json"),
            "edit",
            "description_good_status",
            "not-a-status",
            "export",
            "document",
            str(temporary / "after-rejection.json"),
            "url",
            "",
            "",
            "export",
            "url",
            str(temporary / "proposal-url.txt"),
            "script",
            "",
            "export",
            "script",
            str(temporary / "fill.js"),
            "validate",
            "quit",
        ],
    )


def second_session(temporary: Path) -> str:
    """Restart, resume a complete document, and isolate two selected projects."""
    return run_session(
        temporary,
        [
            "find",
            "123",
            "123",
            "read",
            "export",
            "document",
            str(temporary / "resumed.json"),
            "find",
            "ambiguous",
            "456",
            "read",
            "edit",
            "name",
            "Separate fixture",
            "export",
            "document",
            str(temporary / "other-project.json"),
            "find",
            "123",
            "123",
            "export",
            "document",
            str(temporary / "returned.json"),
            "quit",
        ],
    )


def verify_exports(temporary: Path, first: str, second: str) -> dict:
    """Check host exports and public results; never inspect server-owned files."""
    expected = {"name": "Stored fixture — café Ω", "description_good_status": "Met"}
    documents = ("before.json", "after-rejection.json", "resumed.json", "returned.json")
    for name in documents:
        if json.loads((temporary / name).read_bytes()) != expected:
            raise RuntimeError(f"Unexpected full document export: {name}")
    if json.loads((temporary / "other-project.json").read_bytes()) != {"name": "Separate fixture"}:
        raise RuntimeError("Project isolation failed.")
    if "invalid_field" not in first or '"created": true' not in first:
        raise RuntimeError("Creation/rejection evidence is missing.")
    if "draft_not_found" not in second:
        raise RuntimeError("Missing second-project read was not reported.")
    for name in ("proposal-url.txt", "fill.js"):
        if not (temporary / name).read_bytes():
            raise RuntimeError(f"Missing artifact export: {name}")
    return {
        "first_edit_without_read": "passed",
        "invalid_patch_preserves_document": "passed",
        "restart_resume": "passed",
        "project_isolation": "passed",
        "complete_document_export": "passed",
        "stored_artifact_generation_without_validation": "passed",
        "network": "offline synthetic fixture transport only",
        "storage": "temporary directory removed after demo",
    }


def main() -> None:
    output = ROOT / "build" / "qa" / "M4" / "demo"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        first = first_session(temporary)
        second = second_session(temporary)
        summary = verify_exports(temporary, first, second)
        for name in (
            "before.json",
            "after-rejection.json",
            "resumed.json",
            "returned.json",
            "other-project.json",
            "proposal-url.txt",
            "fill.js",
        ):
            (output / name).write_bytes((temporary / name).read_bytes())
        # Keep reproducible logs free of machine-specific disposable root paths.
        (output / "sessions.txt").write_text(
            (first + "\n--- restarted server ---\n" + second).replace(
                str(temporary), "<temporary>"
            ),
            encoding="utf-8",
        )
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("Synthetic exports and session log: build/qa/M4/demo/")


if __name__ == "__main__":
    main()
