# Documentation

This is an independent Reponomics project, not affiliated with, sponsored by, endorsed by, or an official project of OpenSSF, the Linux Foundation, or the OpenSSF Best Practices Badge (BadgeApp) project or its contributors. References identify compatibility and provenance.

## Maintained documentation

| Document | Purpose |
| --- | --- |
| [Server specification](specification.md) | Supported behavior, nine tools and host/server responsibilities |
| [Design decisions](design.md) | Human-review boundary, deliberate exclusion of direct saves and documented-procedure authority |
| [Architecture](architecture.md) | Modules, data flow, protocol adaptation and persistence boundaries |
| [Implementation contracts](contracts.md) | Exact payloads, errors, size/network policies and edge cases |
| [Upstream compatibility](upstream-compatibility.md) | Source baseline, routes, catalog conventions and update procedure |
| [Transfer rules](transfer-rules.md) | URL precedence, overrides, omissions and script differences |
| [Schema compatibility](schema-compatibility.md) | SDK-supported schema declarations and interoperability checks |
| [Testing policy](testing-policy.md) | Required conformance checks and optional Ruby diagnostics |
| [CI and repository setup](ci.md) | Native compatibility matrix, security checks and service activation |
| [Release procedure](releasing.md) | Release Please, approvals, OIDC publication and published-package QA |

The [project README](../README.md) covers installation, host configuration and development commands. The [reference terminal host](../examples/host.py) demonstrates both explicit documents and optional server-managed storage using MCP calls.

## Historical records

[Initial implementation planning](planning/initial-implementation/README.md) preserves the original scope, review findings and dispositions, and concise milestone outcomes. These records explain development decisions; their old milestone statuses and paths do not override the maintained documentation. Detailed generated QA reports are archived privately, and new reports are generated under ignored `build/qa/`.

The [live Chrome QA record](live-qa/2026-11-09/README.md) includes the approved screenshots, associated retained proposal URLs/script, and the limits of the exercised transfer cases.
