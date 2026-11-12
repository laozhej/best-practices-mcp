"""Offline document-mode host demonstration, preserving exact synthetic exports."""

import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    output = ROOT / "build" / "qa" / "M3" / "demo"
    output.mkdir(parents=True, exist_ok=True)
    server = shlex.join([sys.executable, str(ROOT / "tests/fixtures/read_server.py")])
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        commands = [
            "find",
            "ambiguous",
            "123",
            "level",
            "passing",
            "import",
            str(ROOT / "examples/m3_document.json"),
            "url",
            "",
            "",  # Generate first: optional validation has not been called.
            "url",
            "",
            "description_good_justification",
            "export",
            "url",
            str(temporary / "proposal-url.txt"),
            "script",
            "",
            "export",
            "script",
            str(temporary / "fill.js"),
            "export",
            "document",
            str(temporary / "document.json"),
            "validate",
            "quit",
        ]
        result = subprocess.run(
            [sys.executable, str(ROOT / "examples/host.py"), "--server-command", server],
            input="\n".join(commands) + "\n",
            text=True,
            encoding="utf-8",
            cwd=ROOT,
            timeout=30,
            check=False,
        )
        if result.returncode:
            raise SystemExit(result.returncode)
        for name in ("proposal-url.txt", "fill.js", "document.json"):
            data = (temporary / name).read_bytes()
            if not data:
                raise RuntimeError(f"Missing exported artifact: {name}")
            (output / name).write_bytes(data)
    print(
        "Synthetic exports (no live calls): "
        "build/qa/M3/demo/{document.json,proposal-url.txt,fill.js}"
    )


if __name__ == "__main__":
    main()
