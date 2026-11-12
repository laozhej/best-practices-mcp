# Best Practices MCP

An independent Python MCP server project for OpenSSF Best Practices BadgeApp: public criteria and progress reads, local draft editing, mechanical validation, and update artifacts for a host to hand to the user.

Maintained by Reponomics. This project is not affiliated with, sponsored by, endorsed by, or an official project of OpenSSF, the Linux Foundation, or the OpenSSF Best Practices Badge (BadgeApp) project or its contributors. Upstream references and notices identify compatibility and provenance, not endorsement. Original project code is [MIT licensed](LICENSE); see the [third-party notices](THIRD_PARTY_NOTICES.md).

The stdio server exposes nine tools: `find_project`, `get_criteria`, `get_project_progress`, `build_draft`, `read_draft`, `update_draft`, `validate_draft`, `prepare_update_url`, and `prepare_update_script`. The reference host supports explicit documents and optional project-keyed storage. Python 3.11 is the supported minimum, with native Python 3.11/3.12 checks on Linux, macOS and Windows.

## Documentation

- [Design decisions](docs/design.md) and [architecture](docs/architecture.md): responsibilities, data flow and scope boundaries.
- [Specification](docs/specification.md) and [contracts](docs/contracts.md): tool behavior, payloads, errors and operational limits.
- [Upstream compatibility](docs/upstream-compatibility.md), [transfer rules](docs/transfer-rules.md) and [schema compatibility](docs/schema-compatibility.md): documented procedures and reviewed compatibility choices.
- [Testing policy](docs/testing-policy.md), [CI setup](docs/ci.md) and [release procedure](docs/releasing.md): validation and maintenance.
- [Initial implementation records](docs/planning/initial-implementation/README.md): historical plans and reviews, separate from maintained documentation.
- [Live Chrome QA context](docs/live-qa/2026-11-09/README.md): screenshots, exercised transfer cases and their limits.

The design keeps one multi-level `.bestpractices.json` draft per registered project, optionally stored beneath a configurable data directory. Hosts may supply a document explicitly instead. Validation is level-specific and optional; missing required explanation or URL text does not gate artifact generation. Hosts own advisory work, opening URLs, executing scripts, publishing files, and saving BadgeApp forms.

## Install and run

Use Python 3.11 or newer. For isolated execution without a permanent tool installation, use [uvx](https://docs.astral.sh/uv/guides/tools/); for a persistent executable, use [pipx](https://pipx.pypa.io/stable/reference/cli.html). The package is named `best-practices-mcp`, while its executable is `bestpractices-mcp`.

<!-- x-release-please-start-version -->
```sh
uvx --from 'best-practices-mcp==0.1.0-beta.1' bestpractices-mcp --version

# Alternatively, install the executable persistently:
pipx install 'best-practices-mcp==0.1.0-beta.1'
bestpractices-mcp --version
```

An MCP host can launch the isolated tool using this configuration:

```json
{
  "mcpServers": {
    "bestpractices": {
      "command": "uvx",
      "args": ["--from", "best-practices-mcp==0.1.0-beta.1", "bestpractices-mcp"]
    }
  }
}
```
<!-- x-release-please-end -->

Use an absolute path to `uvx` if the host does not inherit your shell's PATH. For pipx, configure the absolute installed `bestpractices-mcp` executable instead. Running without `--version` starts the stdio server and waits for its host; it is not an interactive terminal interface. Node and Ruby are not required to run the server. The optional [reference terminal host](examples/host.py) is provided in the source repository and source distribution; it is not a separately installed console command.

## Develop

Use Python 3.11 or newer and a local `venv`:

```sh
make setup
nvm use
make setup-dom
make check
make example
make build
```

`make help` lists commands. `make setup` installs the package in editable mode with the development tools; no global Python installation is modified. Override `BOOTSTRAP_PYTHON` when choosing the interpreter, for example `make setup BOOTSTRAP_PYTHON=python3.12`.

`make example` launches the official MCP client, verifies nine-tool discovery and schemas, then closes without contacting BadgeApp. `make host` starts the independent terminal host; `find`, `level`, `criteria`, `progress` and `refresh` guide public reads. After explicit project selection, `new` or `import` supplies a caller-owned document; `edit`, `remove`, `show`, optional `validate`, `url`, `script`, and `export` complete document mode. URL prompts accept a selective field subset and exact overrides; script prompts accept a subset and display replacement instructions. Export preserves exact UTF-8 artifact bytes and refuses existing destinations. No model or credentials are needed. `make host-stored` (or `examples/host.py --mode stored`) opts into server-local persistence. In stored mode, `edit` can create the first draft directly, `init` explicitly creates an empty draft, and `read`/`show` resumes the complete document. Whole-document validation/generation omit `draft`; a selected subset uses a complete read and an explicit temporary document. JSON export uses `read_draft`. The host never reads server files directly or retries an uncertain mutation.

`make setup-dom` uses npm with the committed lockfile; Node 24/jsdom are development-only test dependencies and never part of the MCP runtime. Required tests follow documented upstream procedures, criteria YAML and agreed MCP compatibility rules. They execute generated scripts against synthetic source-derived forms for the approved fallback. Synthetic forms test defensive JavaScript behavior; a locally supervised live browser check separately tests actual website compatibility. See the [testing policy](docs/testing-policy.md) for authority and traceability.

The installed CLI supports:

```sh
venv/bin/bestpractices-mcp --help
venv/bin/bestpractices-mcp --version
```

Running it without arguments starts the stdio server and waits for an MCP host. Protocol traffic uses stdout; diagnostics must use stderr.

## Validate the implementation

From the repository root after `make setup`, `nvm use` and `make setup-dom`:

```sh
make check catalog-check lock-check workflow-check
make test-coverage
make test-package
make check-fresh-package
```

`make workflow-check` requires a separately installed `actionlint` on `PATH`, or an explicit `ACTIONLINT=/path/to/actionlint` Make override. Coverage reports are written under `build/coverage/`; fresh-package results and sanitized logs are written under `build/verification/`. The [release procedure](docs/releasing.md) covers exact candidate qualification, publication controls and published-package QA.

`make test-storage`, `make test-documents`, `make test-upstream`, and `make test-host` select focused storage, document, transfer/DOM and reference-host tests from the ordinary offline suite. `make smoke-live PROJECT_ID=1` separately checks public GET compatibility; it never saves anything or establishes the deployed upstream revision.

For live-form QA, follow the brief [PolicyChecks browser runbook](docs/live-browser-qa.md): resolve the intended project and level, authenticate in the browser, inspect the actual form baseline, then review and apply selected artifacts. Its first execution follows beta publication and gates stable promotion; repeat it for subsequent release candidates. Compare retention, overrides, paired fields and exact text before discarding or separately deciding to save. The [recorded Chrome cases](docs/live-qa/2026-11-09/README.md) provide examples. Artifact reports identify included and excluded fields; they do not predict the form's effects or saved values. Eligible supplied fields are always included, even when equal to the public record. A user may delegate browser actions to a host agent; the MCP itself never saves. A later explicit `refresh` reports saved observations separately. The URL interface follows upstream recommendations; the guarded console script is a project feature, not an upstream-supported API.

`make catalog-check` verifies byte-for-byte regeneration from vendored inputs. `make test-package` checks the distribution contents and an isolated installed wheel using the current environment's dependencies. Fresh-install qualification separately installs wheel and sdist into new environments.

## Installation and native Windows commands

Python 3.11 is the supported minimum targeted by the compatibility matrix. Use an isolated environment; the assessed project does not need to use Python. From this checkout, a runtime-only installation on macOS/Linux is:

```sh
python3.11 -m venv venv
venv/bin/python -m pip install .
venv/bin/python -m best_practices_mcp --version
```

The native PowerShell equivalents are:

```powershell
py -3.11 -m venv venv
.\venv\Scripts\python.exe -m pip install .
.\venv\Scripts\python.exe -m best_practices_mcp --version
```

For Windows development/QA, install `'.[dev]'` instead of `.` and install Node 24. Use these commands without requiring Make or shell activation:

```powershell
.\venv\Scripts\python.exe -m pip install -e '.[dev]'
npm ci --ignore-scripts
.\venv\Scripts\python.exe -m ruff check src tests examples scripts
.\venv\Scripts\python.exe scripts/check_coverage.py
.\venv\Scripts\python.exe scripts/check_package.py
.\venv\Scripts\python.exe scripts/check_fresh_package.py --allow-downloads --output build/verification/fresh-package.json
.\venv\Scripts\python.exe examples/host.py --discover
```

Coverage measures server-package lines and branches, including Python MCP subprocesses. A temporary hook in the development venv forwards only Coverage.py's process configuration through the SDK's filtered environment; it is removed after collection and does not modify production code. `make test-coverage` writes `build/coverage/html/index.html`, XML/JSON reports and a summary with commit/environment details. Coverage percentages complement behavioral assertions; they do not establish that uncovered paths are safe. CI retains the reports for each matrix combination.

`make check-fresh-package` explicitly permits dependency downloads and creates fresh temporary environments for wheel and sdist installation outside the checkout. It does not reuse the development environment's dependencies. Use `make test-package` for the offline package check. Dependency installation requires network access unless the required packages are cached; runtime fixture checks are offline.

## Connect a host

After `make setup`, use the absolute executable path in the host's MCP configuration:

```json
{
  "mcpServers": {
    "bestpractices": {
      "command": "/absolute/path/to/best-practices-mcp/venv/bin/bestpractices-mcp"
    }
  }
}
```

On Windows, use an absolute `venv\Scripts\bestpractices-mcp.exe` path (escape backslashes in JSON), or configure `venv\Scripts\python.exe` with arguments `["-m", "best_practices_mcp"]`.

The baseline is MCP `2026-07-28` with official Python SDK `2.3.0`. `BESTPRACTICES_DATA_DIR` optionally supplies an absolute server-local data root. Unset selects `~/Library/Application Support/bestpractices-mcp` on macOS, `$XDG_DATA_HOME/bestpractices-mcp` (absolute XDG only) or `~/.local/share/bestpractices-mcp` on Linux, and `%LOCALAPPDATA%/bestpractices-mcp` on Windows. Empty/relative overrides and existing nondirectory roots fail at startup; `~` is not expanded in overrides. Startup and read-only/document-only workflows create no storage.

Only `update_draft` writes `<root>/projects/<project_id>/.bestpractices.json`. Each project has one multi-level draft. An explicit document, including `{}`, bypasses stored files; an omitted document reads the selected project at call time. Complete reads retain unfamiliar JSON and report structural diagnostics. Updates validate source identity before patching and check full read/update result budgets before atomic replacement. New drafts use owner-only permissions where supported; existing permissions are preserved.

Updates within one server process use per-project guards. Separate servers and external editors are not coordinated: avoid simultaneous writers to the same project/root. Atomic replacement prevents partial files, not lost updates between independent writers or sudden-power-loss guarantees. Cancellation or a lost response can leave an uncertain outcome; use `read_draft` to inspect before deciding on another patch. The server never retries the mutation automatically.

For an independent stored workflow, pass a dedicated absolute root:

```sh
venv/bin/python examples/host.py --mode stored --data-dir /absolute/path/to/drafts
```

Automated tests and package probes use temporary storage, never the normal draft directory.

## Inspect the implemented tools

MCP Inspector 2.14.0 can connect to this stdio server in modern protocol mode:

```sh
npx -y @modelcontextprotocol/inspector@2.14.0 --protocol-era modern ./venv/bin/bestpractices-mcp
```

Use Node 24.22.1 or another version supported by that Inspector release. Discovery, get_criteria, build_draft, read_draft, update_draft and validate_draft are offline. update_draft mutates local storage; use a disposable absolute BESTPRACTICES_DATA_DIR for Inspector tests. find_project, get_project_progress and artifact generation make public BadgeApp GETs. No tool authenticates or submits changes. For a reproducible CLI schema check, add `--cli --method tools/list --strict --format json`. See [schema compatibility](docs/schema-compatibility.md) for official guidance and the distinction between portability lint and MCP conformance.
