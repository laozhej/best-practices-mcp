# BadgeApp transfer rules: references and MCP choices

A concise companion to the [server specification](specification.md), not a replacement for upstream documentation. The MCP decisions below are incorporated into the specification.

## Primary references

- [Automation proposals](https://github.com/ossf/best-practices-badge/blob/main/docs/automation-proposals.md): public URL format, fields, overrides, and review flow.
- [Automation approach: decision matrix](https://github.com/ossf/best-practices-badge/blob/main/docs/automation-approach.md#the-decision-matrix): precise status-first, justification-second precedence.
- [Automation approach: controller flow](https://github.com/ossf/best-practices-badge/blob/main/docs/automation-approach.md#controller-method-map): when website automation and URL proposals run, including save behavior.
- [Repository JSON](https://github.com/ossf/best-practices-badge/blob/main/docs/bestpractices-json.md): file locations, unknown answers, and triggering import.

Compatibility observations below were checked against upstream revision `868e1677339a3fdb48851b0c2ae8862c553115eb`. Use the docs for intended behavior and explicitly approved compatibility decisions for edge cases; pinned code/tests are supporting investigation evidence, not automatic requirements. Report disagreements explicitly. Existing plugin helper limitations are not upstream requirements.

## URL precedence, condensed

Follow the upstream decision matrix in this order:

1. Only fields valid for the selected level participate. Compute override matches; forcing a status also forces its supplied justification.
2. Discard unparsable and unknown (`?`) status proposals. Justification parameters remain independently eligible.
3. Compare statuses: identical is a no-op; blank/unknown accepts a known value; a differing known value is retained unless forced.
4. A differing, unforced status blocks its accompanying justification **even when that justification is forced**.
5. Otherwise, blank justification accepts text; identical text is a no-op; existing different wording is retained unless forced. A standalone justification needs no supplied status.
6. These operations populate the edit form. They do not save the application. Save-time automation can still affect the final answer.

Unforced differing metadata is retained with a divergence indicator; unforced wording changes are silently skipped. An empty URL justification can clear existing text when forced. See the upstream [decision matrix](https://github.com/ossf/best-practices-badge/blob/868e1677339a3fdb48851b0c2ae8862c553115eb/docs/automation-approach.md#the-decision-matrix) and [standalone/coupled justification tests](https://github.com/ossf/best-practices-badge/blob/868e1677339a3fdb48851b0c2ae8862c553115eb/test/controllers/projects_controller_test.rb#L3601).

## What each mechanism means

| Input                  | Local draft                     | Proposal URL                         | Repository JSON                              | MCP fill script                             |
| ---------------------- | ------------------------------- | ------------------------------------ | -------------------------------------------- | ---------------------------------------------------- |
| Missing field          | No answer supplied              | No change requested                  | No proposal for that field                   | Leave control alone                                  |
| Status `?`             | Preserve unknown answer         | Unsupported by this MCP      | Ignored                                      | Leave status control alone                           |
| `?` plus justification | Preserve both                   | Evaluate justification independently | Justification can be processed independently | Evaluate/fill justification independently            |
| Justification alone    | Valid partial draft             | Supported; no status carrier         | Supported                                    | Fill only supplied textarea                          |
| Empty justification    | Preserve intentional empty text | Can clear with override              | Ignored                                      | Can clear specified textarea                         |
| `overrides=`           | Not an answer field             | Controls replacement and coupling    | No such mechanism                            | No such mechanism; script replaces selected controls |
| Patch value `null`     | Remove local field              | Does not request remote deletion     | Not a clearing mechanism                     | Does not request remote deletion                     |

Repository publishing and import acceptance belong to the host and BadgeApp. Local drafts and artifact generation do not enforce internal importer limits or predict importer results. See the upstream repository JSON guidance for that separate workflow.

## MCP decisions

- Preserve unknown answers locally; do not interpret draft `?` as a reset request. Do not discard an accompanying justification merely because the status is unknown.
- Default URLs to unforced proposals; accept explicit exact-field overrides, not a blanket `*` default. Report requested and effective override scope.
- Resolve coupling before removing no-op fields. Removing an unchanged status must not accidentally remove the requested force effect on its changed justification; preserve that effect with an explicit justification override. Never drop a blocked status merely to make its justification apply.
- Do not borrow or invent status values for justification-only proposals. Report omissions and expected form behavior separately from fields encoded in an artifact.
- Agreed URL-delivery boundary: return one exact URL and its encoded UTF-8 byte length. Do not truncate, batch, retry delivery, or impose a guessed URL-length limit. The host handles display, copying, and opening.

## Known documentation discrepancy

The public proposal guide describes URL `?` as an explicit reset. The automation-approach decision matrix and inspected controller instead discard it. V1 makes no reset promise and retains this as an upstream clarification/compatibility item. [Public guide](https://github.com/ossf/best-practices-badge/blob/868e1677339a3fdb48851b0c2ae8862c553115eb/docs/automation-proposals.md#status-value-semantics-query-strings-vs-json), [controller](https://github.com/ossf/best-practices-badge/blob/868e1677339a3fdb48851b0c2ae8862c553115eb/app/controllers/projects_controller.rb#L1834)


## Edit-form prediction boundary

The public proposal guide documents trimming justification edges. The agreed compatibility rule applies the pinned ASCII whitespace normalization to non-status URL values while preserving original text in the draft and encoded artifact. Required tests check documented procedures and explicit compatibility rules without executing Ruby; optional source diagnostics are described in the [testing policy](testing-policy.md).

“Retained status blocks justification” refers specifically to a **differing proposed status that is not forced**. A proposed status equal to the saved status does not block its justification; an explicit justification override can then replace existing wording. These are upstream rules, not new MCP policy.

`expected_application` describes documented edit-form proposal behavior relative to the observed public record. It does not predict Save/Submit acceptance, validation side effects, automation outcomes, or final persisted values. BadgeApp may run its own automation before the form is displayed; the actual form baseline therefore matters for live QA. After an owner-chosen save, a fresh public read records observed saved state without claiming that the MCP predicted it.

The URL path is the upstream-recommended interface for external automation. The generated console script is this project's explicitly approved guarded fallback, verified against source-derived synthetic forms; upstream does not document it as a supported automation API. Its specified controls use replacement semantics independently of URL overrides. Neither artifact executes itself or saves a form.

Required and optional checks, their authority, and the source-update review procedure are mapped in the [testing policy](testing-policy.md).
