"""Generate bounded form-filling JavaScript for owner review and execution."""

import json

from best_practices_mcp.drafts import field_definitions
from best_practices_mcp.proposals import ORIGIN
from best_practices_mcp.transfer import finish_result, transfer_context, transfer_rows

# Executable source is fixed. All caller-controlled values enter through JSON data.
_TEMPLATE = r"""(() => {
  "use strict";
  const payload = __PAYLOAD__;
  const report = {
    outcome: "preflight_failed", filled_fields: [], missing_fields: [],
    failed_field: null, message: "No controls changed."
  };
  const permittedPaths = [
    `/projects/${payload.project_id}/${payload.level}/edit`,
    `/en/projects/${payload.project_id}/${payload.level}/edit`
  ];
  const path = location.pathname.replace(/\/$/, "");
  if (location.origin !== payload.origin || !permittedPaths.includes(path)) {
    report.message = "Wrong origin, project, level, or edit route; no controls changed.";
    return report;
  }
  function editable(control) {
    return !control.disabled && !control.readOnly && !control.matches(":disabled");
  }
  function findControl(item) {
    const matches = Array.from(document.getElementsByName(`project[${item.field}]`));
    if (item.kind === "status") {
      const validGroup = matches.every(control =>
        control.tagName === "INPUT" && control.type === "radio");
      const targets = matches.filter(control => control.value === item.value);
      if (!validGroup || targets.length !== 1 || !editable(targets[0])) return null;
      return targets[0];
    }
    if (matches.length !== 1) return null;
    const control = matches[0];
    const correctType = item.tag === "TEXTAREA"
      ? control.tagName === "TEXTAREA"
      : control.tagName === "INPUT" && control.type === "text";
    return correctType && editable(control) ? control : null;
  }
  const operations = [];
  try {
    for (const item of payload.fields) {
      const control = findControl(item);
      if (control) operations.push({item, control});
      else report.missing_fields.push(item.field);
    }
  } catch (_) {
    report.message = "Control inspection failed; no controls changed.";
    return report;
  }
  if (report.missing_fields.length) {
    report.message = "Missing or invalid controls; no controls changed.";
    return report;
  }
  for (const {item, control} of operations) {
    try {
      if (item.kind === "status") control.checked = true;
      else control.value = item.value;
      // Include assigned fields even if dispatch subsequently fails: changes are not rolled back.
      report.filled_fields.push(item.field);
      control.dispatchEvent(new Event("input", {bubbles: true}));
      control.dispatchEvent(new Event("change", {bubbles: true}));
    } catch (_) {
      report.outcome = "runtime_failed";
      report.failed_field = item.field;
      report.message = "Assignment or dispatch failed; prior changes may remain. Review the form.";
      return report;
    }
  }
  report.outcome = "filled";
  report.message = "Controls filled; review the form and save manually. Nothing was submitted.";
  return report;
})()
"""


def _script_field(field, value, definitions):
    kind = definitions[field]["kind"]
    return {
        "field": field,
        "kind": kind,
        "tag": "TEXTAREA" if kind == "justification" or field == "description" else "INPUT",
        "value": value,
    }


def prepare_update_script(project_id, level, draft, record, observation):
    """Return a deterministic script, never execute it or interact with a browser."""
    draft, criteria, scope, result = transfer_context(project_id, level, draft, record, observation)
    rows = transfer_rows(draft, record, criteria, scope, set(), "script")
    result["artifact"] = None
    if not finish_result(result, rows):
        return result
    definitions = field_definitions()
    fields = [
        _script_field(item["field"], draft[item["field"]], definitions)
        for item in rows
        if item["disposition"] == "encoded"
    ]
    payload = {"origin": ORIGIN, "project_id": project_id, "level": level, "fields": fields}
    source = _TEMPLATE.replace(
        "__PAYLOAD__", json.dumps(payload, ensure_ascii=True, sort_keys=True)
    )
    result["artifact"] = {
        "javascript": source,
        "suggested_filename": f"bestpractices-{project_id}-{level}.js",
        "instructions": (
            "Authenticate in BadgeApp, open the matching project and level edit form, inspect this "
            "script, and run it in the browser console. Review every filled control and save "
            "manually. Execution replaces existing values of the specified controls, independently "
            "of URL override settings. The script performs no network requests or submission. "
            "A runtime failure "
            "does not roll back assignments; inspect filled_fields and failed_field. Browser event "
            "listener exceptions may be reported only by the browser and are not certified by "
            "the returned report."
        ),
        "encoded_size_bytes": len(source.encode("utf-8")),
    }
    return result
