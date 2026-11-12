# Artifact transfer rules

The MCP prepares faithful proposal URLs and form-fill scripts from supplied drafts. The [server specification](specification.md) and [contracts](contracts.md) define the payloads and limits; BadgeApp determines the effects of opening a proposal URL.

## Primary references

- [Automation proposals](https://github.com/ossf/best-practices-badge/blob/868e1677339a3fdb48851b0c2ae8862c553115eb/docs/automation-proposals.md): public URL format, fields, overrides, and review flow.
- [Automation approach: decision matrix](https://github.com/ossf/best-practices-badge/blob/868e1677339a3fdb48851b0c2ae8862c553115eb/docs/automation-approach.md#the-decision-matrix): BadgeApp's status-first, justification-second precedence.
- [Repository JSON](https://github.com/ossf/best-practices-badge/blob/868e1677339a3fdb48851b0c2ae8862c553115eb/docs/bestpractices-json.md): file locations, unknown answers, and triggering import.

## Artifact contents

Every eligible supplied field is included, including values equal to the public record. Artifact generation does not compare saved answers, trim text, classify blankness, suppress unchanged values, or predict the resulting form state. The public read verifies the registered target and any supplied identity; it does not drive answer selection.

The transfer report contains one row per supplied normalized field. It identifies encoded fields and exclusions for unsupported fields, invalid transfer values, provenance, or another badge level. It does not repeat answer bodies or report whether an encoded proposal will fill, replace, retain or be blocked in the actual form. The host reviews the artifact and the rendered BadgeApp form.

| Input | Local draft | Proposal URL | MCP fill script |
| --- | --- | --- | --- |
| Missing field | No answer supplied | No field encoded | Leave control alone |
| Eligible value equal to saved answer | Preserve supplied value | Encode supplied value | Include assignment |
| Status `?` | Preserve unknown answer | Unsupported by this MCP | Leave status control alone |
| `?` plus justification | Preserve both | Encode eligible justification independently | Fill eligible justification independently |
| Justification alone | Valid partial draft | Encode only supplied justification | Fill only supplied textarea |
| Empty justification | Preserve intentional empty text | Encode empty string | Assign empty string |
| Whitespace or control characters | Preserve exact text | Percent-encode exact text | Include exact string in the assignment payload |
| Explicit override | Not an answer field | Encode requested eligible field names | No override parameter; specified controls use replacement semantics |
| Patch value `null` | Remove local field | Does not request remote deletion | Does not request remote deletion |

Values in encoded artifacts remain exact strings. How BadgeApp parses a URL value or a browser represents a control value is verified in the actual interface, not simulated from upstream implementation details.

BadgeApp's [justification-value documentation](https://github.com/ossf/best-practices-badge/blob/868e1677339a3fdb48851b0c2ae8862c553115eb/docs/automation-proposals.md#justification-values) specifies trimming leading and trailing whitespace from URL-proposed justification text. The tool description communicates this procedure; the MCP preserves the supplied text in the URL and leaves trimming to BadgeApp. The form-fill script assigns the supplied text without trimming, so the host can discuss that alternative when surrounding whitespace matters.

## Explicit overrides

Default URLs contain unforced proposals. `override_fields` accepts exact canonical supplied in-scope field names, not aliases, globs or a blanket `*`. The result's `requested_overrides` is the validated sorted, deduplicated request. `effective_overrides` contains only explicitly requested fields actually included in the URL's `overrides` parameter. Each row's `override` flag reports membership in that encoded list.

The MCP does not expand a status override into an additional justification override. It preserves the supplied status and justification along with the explicit override, so BadgeApp can apply its documented implication. It also preserves unforced supplied pairs even when an existing answer differs. The site decides whether their proposals apply.

For host guidance, BadgeApp documents that an unforced differing status can retain the existing answer and block its supplied justification, including when only the justification is forced. A status override also applies to a supplied paired justification. These are website procedures to consider when choosing overrides and reviewing the form; they are not per-field predictions returned by the MCP. See the upstream decision matrix for the complete rules.

## URL and script boundaries

Return one exact URL and its encoded UTF-8 byte length. Do not truncate, batch, retry delivery, or impose a guessed URL-length limit. The host handles display, copying and opening. The URL path is the upstream-recommended interface for external automation.

The generated console script is this project's guarded fallback; upstream does not document it as a supported automation API. It includes every eligible supplied field and replaces the specified controls independently of URL overrides. It checks the target and controls before assignment, then reports actual filled fields or execution failures. Neither artifact executes itself or saves a form.

Repository publishing and import acceptance belong to the host and BadgeApp. Local drafts and artifact generation do not enforce internal importer limits or predict importer results. A fresh public read after a separately authorized save records observed saved state.

## Unknown-status limitation

The public proposal guide describes URL `?` as an explicit reset, while the automation-approach decision matrix discards it. This MCP makes no reset promise: preserve unknown answers locally, omit them from artifacts with an explicit unsupported-field reason, and evaluate any accompanying justification independently. [Public guide](https://github.com/ossf/best-practices-badge/blob/868e1677339a3fdb48851b0c2ae8862c553115eb/docs/automation-proposals.md#status-value-semantics-query-strings-vs-json), [decision matrix](https://github.com/ossf/best-practices-badge/blob/868e1677339a3fdb48851b0c2ae8862c553115eb/docs/automation-approach.md#the-decision-matrix).

Required checks and live compatibility verification are mapped in the [testing policy](testing-policy.md).
