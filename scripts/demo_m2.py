"""Run the real terminal host against the offline M2 fixture server."""

import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    server = shlex.join([sys.executable, str(ROOT / "tests/fixtures/read_server.py")])
    result = subprocess.run(
        [sys.executable, str(ROOT / "examples/host.py"), "--server-command", server],
        input="find\nambiguous\n123\nlevel\npassing\ncriteria\ndescription_good\nprogress\nquit\n",
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=30,
        check=False,
    )
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
