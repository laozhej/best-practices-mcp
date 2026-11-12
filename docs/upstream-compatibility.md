# Upstream compatibility

Compatibility is based on BadgeApp revision **868e1677339a3fdb48851b0c2ae8862c553115eb**. A source pin identifies the documented and tested baseline; it does not establish which revision the live website currently runs. The server follows documented automation procedures and explicit compatibility decisions without predicting save-time behavior from internal Ruby implementation details.

## Sources and authority

The primary references are the pinned [API documentation](https://github.com/ossf/best-practices-badge/blob/868e1677339a3fdb48851b0c2ae8862c553115eb/docs/api.md), [automation proposals](https://github.com/ossf/best-practices-badge/blob/868e1677339a3fdb48851b0c2ae8862c553115eb/docs/automation-proposals.md), [automation approach](https://github.com/ossf/best-practices-badge/blob/868e1677339a3fdb48851b0c2ae8862c553115eb/docs/automation-approach.md), and [repository JSON guidance](https://github.com/ossf/best-practices-badge/blob/868e1677339a3fdb48851b0c2ae8862c553115eb/docs/bestpractices-json.md). Catalog generation uses the pinned criteria YAML and English locale; packaged provenance records source hashes and generator details.

Vendored documentation, source excerpts and fixtures support reproducibility and investigation. They do not make every upstream implementation detail normative. Required tests derive expectations from documented procedures, criteria definitions and the agreed contract. Ruby execution and comparisons with Ruby-generated fixtures are optional maintainer diagnostics; see the [testing policy](testing-policy.md) and [design boundary](design.md#follow-documented-procedures-not-internal-save-behavior).

## Routes and public observations

All network requests use GET against `https://www.bestpractices.dev`, without authentication or cookies. Public JSON routes are locale-independent; generated HTML edit links use English paths.

| Operation | Route and interpretation |
| --- | --- |
| Project lookup/progress | `/projects/{project_id}.json`; a missing ID is empty discovery or `project_not_found` for progress/generation |
| URL discovery | `/projects.json?url={query}&page={page}`; the URL is a query value, never fetched; preserve upstream candidates and their own search semantics |
| Text discovery | `/projects.json?q={query}&page={page}`; preserve returned candidate order and explicit pagination uncertainty |
| Proposal/edit link | `/en/projects/{project_id}/{level}/edit`; all six level names map directly to section names |

Query keys are sorted and spaces percent-encoded as `%20` to use the site's canonical request representation without following redirects. Discovery matching is intentionally more permissive than generator identity checks: an upstream search candidate is not discarded merely because strict repository-URL identity comparison cannot establish equality.

A public record's omitted status remains absent, not an invented `?`. A known justification omitted from a complete valid pinned public record is interpreted as blank only when predicting form transfer, reflecting the serializer's omission of blank justifications. This does not synthesize fields in progress answers or draft documents. Unexpected supplied JSON values remain visible for diagnostics. Public reads are observations, not assurances about subsequent form state or saves.

## Catalog and transfer semantics

The six supported levels are `passing`, `silver`, `gold`, `baseline-1`, `baseline-2`, and `baseline-3`. Catalog requirements are level-qualified. Explicit public flags expand upstream's logical entailments: `met_url_required` implies `met_justification_required`, and `na_justification_required` implies `na_allowed`. An omitted entailed YAML field is not absence of the requirement.

Proposal URL behavior follows the documented status-first, justification-second matrix. A differing unforced status retains the saved status and blocks its paired justification even if that justification is forced. An equal status does not block its justification. Forcing an unchanged status still transfers the force effect to a changed supplied justification before no-op pruning. Exact override field names keep host intent explicit.

Original text is preserved in drafts and encoded URLs. The agreed form-transfer normalization trims leading/trailing NUL, horizontal tab, LF, vertical tab, form feed, CR and ASCII space from non-status URL values; it does not use Python's broader Unicode stripping. Script assignment preserves supplied strings exactly. Advisory justification predicates are separate and do not strip text before checking it. Full rules and the documented disagreement over URL `?` resets are in [transfer rules](transfer-rules.md).

The form-fill script is a guarded project feature, not an upstream-supported API. It checks exact production origin, project ID and section; preflights intended controls; then replaces specified values without submitting. Its fixed controls are verified against controlled synthetic forms. Neither script execution nor a URL preview establishes the final saved state.

## Updating the baseline

Review changes to the upstream documentation and criteria before changing a compatibility rule. Regenerate the catalog from identified inputs, review semantic differences and retained notices, update provenance and required regression examples, then run the relevant protocol, artifact and package checks. Investigate discrepancies against the documented contract rather than copying internal behavior automatically. Live read/form checks may supplement deterministic tests; production saves are not required acceptance checks.

BadgeApp source notices are preserved under its MIT license. Public project records carry their own attribution and license values; the MCP passes those through in observation metadata, including legacy names where supplied. Those statements describe the selected project record, not credit for using MCP. See the [third-party notices](../THIRD_PARTY_NOTICES.md) for licensing distinctions and non-affiliation.
