"""Classify supplied fields for artifact generation without comparing saved answers."""

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
    """Validate and deduplicate explicit override field names."""
    if type(requested) is not list:
        raise DomainError("invalid_override", "Overrides must be a list of canonical field names.")
    for field in requested:
        if type(field) is not str or field not in scope or field not in draft:
            raise DomainError("invalid_override", "Override must name a supplied in-scope field.")
    requested = sorted(set(requested))
    return requested, set(requested)


def row(field, disposition, reason, override=False):
    return {
        "field": field,
        "disposition": disposition,
        "reason": reason,
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


def transfer_rows(draft, criteria, scope, overrides):
    """Report inclusion or exclusion for every supplied normalized field."""
    definitions = field_definitions()
    rows = []
    for field in sorted(draft):
        report = _ineligible(field, draft, scope, definitions, criteria)
        if report is None:
            report = row(field, "encoded", "eligible_field", override=field in overrides)
        rows.append(report)
    return rows


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
    else:
        outcome = "no_supplied_transferable_answers"
    result.update(outcome=outcome, no_artifact_reason=None if encoded else outcome, transfer=rows)
    return encoded
