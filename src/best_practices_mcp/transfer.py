"""Pure transfer eligibility and application predictions, independent of validation."""

import re
from typing import Any

from best_practices_mcp.criteria import get_criteria
from best_practices_mcp.drafts import (
    METADATA_FIELDS,
    PROVENANCE_FIELDS,
    VALID_STATUSES,
    check_identity,
    field_definitions,
    normalize_draft,
)
from best_practices_mcp.errors import DomainError

RUBY_STRIP = "\x00\t\n\v\f\r "
# ActiveSupport String#blank? uses Ruby's POSIX [[:space:]] character class.
_RAILS_BLANK = re.compile(r"^[\t-\r \x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]*$")
_MISSING = object()


def transfer_context(project_id, level, draft, record, observation):
    """Resolve shared source context without performing I/O or inventing answers."""
    catalog = get_criteria(level)
    normalized = normalize_draft(draft)
    identity = check_identity(project_id, normalized, record=record, check_repo=True)
    criteria = {item["criterion_id"]: item for item in catalog["criteria"]}
    scope = set(METADATA_FIELDS)
    for item in criteria.values():
        scope.update((item["status_field"], item["justification_field"]))
    result = {
        "schema_version": 1,
        "project_id": project_id,
        "level": level,
        "catalog": catalog["catalog"],
        "draft_source": {"kind": "explicit", "location": None},
        "observation": dict(observation),
        "identity": identity,
    }
    return normalized, criteria, scope, result


def override_scope(requested, draft, scope):
    """Validate exact supplied canonical names, then propagate status forcing."""
    if type(requested) is not list:
        raise DomainError("invalid_override", "Overrides must be a list of canonical field names.")
    for field in requested:
        if type(field) is not str or field not in scope or field not in draft:
            raise DomainError("invalid_override", "Override must name a supplied in-scope field.")
    requested = sorted(set(requested))
    effective = set(requested)
    for field in requested:
        companion = field.removesuffix("_status") + "_justification"
        if field.endswith("_status") and companion in draft:
            effective.add(companion)
    return requested, effective


def row(field, disposition, reason, expected="not_applicable", override=False):
    return {
        "field": field,
        "disposition": disposition,
        "reason": reason,
        "expected_application": expected,
        "override": override,
    }


def _status_problem(value, criterion):
    if type(value) is not str:
        return "invalid_type"
    if value not in VALID_STATUSES:
        return "invalid_status"
    if value == "N/A" and not criterion["na_allowed"]:
        return "na_not_supported"
    return None


def _answer_problem(field, draft, definition, criteria):
    kind = definition["kind"]
    if kind == "status":
        return _status_problem(draft[field], criteria[definition["criterion_id"]])
    if kind == "justification":
        criterion = criteria[definition["criterion_id"]]
        status = criterion["status_field"]
        if status in draft and _status_problem(draft[status], criterion):
            return "invalid_companion_status"
    if type(draft[field]) is not str:
        return "invalid_type"
    return None


def _ineligible(field, draft, scope, definitions, criteria):
    if field in PROVENANCE_FIELDS:
        return row(field, "omitted", "provenance_not_editable")
    if field not in definitions:
        return row(field, "unsupported", "unknown_field")
    if field not in scope:
        return row(field, "outside_level", "outside_selected_level")
    problem = _answer_problem(field, draft, definitions[field], criteria)
    if problem:
        disposition = "omitted" if problem == "invalid_companion_status" else "invalid"
        return row(field, disposition, problem)
    if definitions[field]["kind"] == "status" and draft[field] == "?":
        return row(field, "unsupported", "unknown_status_not_transferred")
    return None


def _blank(value):
    return value is None or (type(value) is str and _RAILS_BLANK.fullmatch(value) is not None)


def _known_saved(value, kind):
    if kind == "status":
        return value is None or (type(value) is str and value in VALID_STATUSES | {""})
    return value is None or type(value) is str


def _base_prediction(proposed, saved, kind, forced, mode):
    if not _known_saved(saved, kind):
        return "unknown"
    if proposed == saved:
        return "unchanged"
    if _blank(saved) or (kind == "status" and saved == "?"):
        return "fill"
    if mode == "script" or forced:
        return "replace"
    return "retain_existing"


def _companion_prediction(field, draft, record, effective, definitions):
    status = field.removesuffix("_justification") + "_status"
    if status not in draft or draft[status] == "?":
        return None
    return _base_prediction(
        draft[status],
        record.get(status, _MISSING),
        definitions[status]["kind"],
        status in effective,
        "url",
    )


def _prediction(field, draft, record, effective, definitions, mode):
    kind = definitions[field]["kind"]
    proposed = draft[field]
    if mode == "url" and kind != "status":
        proposed = proposed.strip(RUBY_STRIP)
    base = _base_prediction(proposed, record.get(field, _MISSING), kind, field in effective, mode)
    if mode == "url" and kind == "justification":
        companion = _companion_prediction(field, draft, record, effective, definitions)
        if companion == "retain_existing":
            return "blocked_by_status"
        if companion == "unknown":
            return "unknown"
    return base


def transfer_rows(draft, record, criteria, scope, effective, mode):
    """Describe every supplied field, retaining blocked proposals as proposals."""
    definitions = field_definitions()
    rows = []
    for field in sorted(draft):
        report = _ineligible(field, draft, scope, definitions, criteria)
        if report is None:
            expected = _prediction(field, draft, record, effective, definitions, mode)
            disposition = "unchanged" if expected == "unchanged" else "encoded"
            reason = _application_reason(field, draft, definitions, expected, mode)
            report = row(field, disposition, reason, expected)
        report["override"] = field in effective
        rows.append(report)
    return rows


def _application_reason(field, draft, definitions, expected, mode):
    reason = "identical_saved_value" if expected == "unchanged" else f"proposal_{expected}"
    if mode == "url" and definitions[field]["kind"] != "status":
        if draft[field] != draft[field].strip(RUBY_STRIP):
            reason += "; upstream_strips_ascii_edges"
    return reason


def finish_result(result: dict[str, Any], rows):
    requested = [item for item in rows if item["field"] not in PROVENANCE_FIELDS]
    encoded = any(item["disposition"] == "encoded" for item in requested)
    omitted = any(
        item["disposition"] in {"unsupported", "invalid", "omitted"} for item in requested
    )
    if encoded:
        outcome = "partial" if omitted else "complete"
    elif omitted:
        outcome = "no_transferable_changes"
    elif any(item["disposition"] == "unchanged" for item in requested):
        outcome = "no_changes"
    else:
        outcome = "no_supplied_transferable_answers"
    result.update(outcome=outcome, no_artifact_reason=None if encoded else outcome, transfer=rows)
    return encoded
