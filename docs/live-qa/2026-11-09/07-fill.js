(() => {
  "use strict";
  const payload = {"fields": [{"field": "contribution_requirements_justification", "kind": "justification", "tag": "TEXTAREA", "value": "  Contribution requirements \u2014 see CONTRIBUTING.md: https://github.com/reponomics/PolicyChecks/blob/main/CONTRIBUTING.md  "}], "level": "silver", "origin": "https://www.bestpractices.dev", "project_id": 14356};
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
