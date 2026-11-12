"""CI evidence must preserve failures and exclude stale successful reports."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("check_coverage", ROOT / "scripts/check_coverage.py")
coverage_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage_check)


def test_supplemental_checks_require_explicit_collection(tmp_path):
    """The real pytest config excludes optional checks without making them unusable."""
    import os
    import shutil
    import subprocess

    shutil.copyfile(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    required = tmp_path / "tests" / "test_required_probe.py"
    optional = tmp_path / "tests" / "optional" / "test_optional_probe.py"
    optional.parent.mkdir(parents=True)
    required.write_text("def test_required_probe(): pass\n", encoding="utf-8")
    optional.write_text("def test_optional_probe(): pass\n", encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if not key.startswith("COVERAGE_")}
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    for arguments, included, excluded in (
        ([], "test_required_probe", "test_optional_probe"),
        (["tests"], "test_required_probe", "test_optional_probe"),
        (["tests/optional"], "test_optional_probe", "test_required_probe"),
        (["tests/optional/test_optional_probe.py"], "test_optional_probe", "test_required_probe"),
    ):
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", *arguments],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert included in result.stdout
        assert excluded not in result.stdout


def test_failed_test_run_still_reports_and_does_not_reuse_stale_totals(tmp_path, monkeypatch):
    (tmp_path / "coverage.json").write_text('{"totals":{"percent_covered":100}}')
    (tmp_path / "html").mkdir()
    (tmp_path / "html/index.html").write_text("old success")
    called = []

    def execute(args, env, log):
        called.append(args[0])
        assert Path(env["COVERAGE_FILE"]).is_absolute()
        assert Path(env["COVERAGE_RCFILE"]).is_absolute()
        return 1 if args[0] == "run" else 0

    monkeypatch.setattr(coverage_check, "command", execute)
    assert coverage_check.run(tmp_path, []) == 1
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert called == ["erase", "run", "combine", "report", "html", "xml", "json"]
    assert summary["status"] == "failed"
    assert "totals" not in summary
    assert not (tmp_path / "html/index.html").exists()


def test_report_failure_cannot_be_overridden_by_successful_tests(tmp_path, monkeypatch):
    monkeypatch.setattr(
        coverage_check,
        "command",
        lambda args, env, log: 1 if args[0] == "combine" else 0,
    )
    assert coverage_check.run(tmp_path, []) == 1
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["checks"][1] == {"stage": "run", "exit_code": 0}
    assert summary["status"] == "failed"


def test_coverage_measures_read_dispatch_inside_sdk_stdio_children(tmp_path):
    import os
    import subprocess

    report = tmp_path / "coverage"
    env = {key: value for key, value in os.environ.items() if not key.startswith("COVERAGE_")}
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/check_coverage.py"),
            "--output",
            str(report),
            "tests/test_read_tools.py",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    coverage = json.loads((report / "coverage.json").read_text(encoding="utf-8"))
    server = ROOT / "src/best_practices_mcp/server.py"
    files = {name.replace("\\", "/"): data for name, data in coverage["files"].items()}
    executed = files[server.relative_to(ROOT).as_posix()]["executed_lines"]
    expected = {
        "return get_criteria(**values)",
        "return await client.find_project(**values)",
        "return await client.get_project_progress(**values)",
    }
    dispatch_lines = {
        index
        for index, line in enumerate(server.read_text(encoding="utf-8").splitlines(), 1)
        if line.strip() in expected
    }
    assert len(dispatch_lines) == 3
    assert dispatch_lines <= set(executed)


def test_sdk_coverage_hook_is_removed_after_failure(tmp_path, monkeypatch):
    import pytest

    monkeypatch.setattr(coverage_check.sysconfig, "get_path", lambda name: str(tmp_path))
    existing = tmp_path / "existing.pth"
    existing.write_text("untouched")
    with pytest.raises(RuntimeError, match="test failure"):
        with coverage_check.forward_sdk_coverage():
            assert len(list(tmp_path.glob("*.pth"))) == 2
            raise RuntimeError("test failure")
    assert list(tmp_path.iterdir()) == [existing]
    assert existing.read_text() == "untouched"


def test_sdk_coverage_hook_does_not_change_unmeasured_processes():
    import os
    import subprocess

    env = {key: value for key, value in os.environ.items() if not key.startswith("COVERAGE_")}
    with coverage_check.forward_sdk_coverage():
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from mcp.client.stdio import DEFAULT_INHERITED_ENV_VARS as names; "
                "assert 'COVERAGE_PROCESS_CONFIG' not in names",
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
    assert result.returncode == 0, result.stderr


def test_sdk_coverage_hook_runs_after_dependency_path_initialization(tmp_path, monkeypatch):
    import os
    import subprocess

    monkeypatch.setattr(coverage_check.sysconfig, "get_path", lambda name: str(tmp_path))
    (tmp_path / "pywin32.pth").write_text(
        "import os; os.environ['BESTPRACTICES_ORDERING_PROBE'] = 'initialized'\n",
        encoding="utf-8",
    )
    probe = """
import builtins, os, site, sys
from types import SimpleNamespace
os.environ.pop('BESTPRACTICES_ORDERING_PROBE', None)
original_import = builtins.__import__
stdio = SimpleNamespace(DEFAULT_INHERITED_ENV_VARS=[])
def guarded_import(name, *args, **kwargs):
    if name == 'mcp.client.stdio':
        assert os.environ.get('BESTPRACTICES_ORDERING_PROBE') == 'initialized'
        return stdio
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
site.addsitedir(sys.argv[1])
assert stdio.DEFAULT_INHERITED_ENV_VARS == ['COVERAGE_PROCESS_CONFIG']
"""
    env = {key: value for key, value in os.environ.items() if not key.startswith("COVERAGE_")}
    env["COVERAGE_RCFILE"] = "ordering-probe"
    with coverage_check.forward_sdk_coverage():
        result = subprocess.run(
            [sys.executable, "-S", "-c", probe, str(tmp_path)],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
