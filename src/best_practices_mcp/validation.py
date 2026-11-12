"""Offline mechanical checks of represented answers using the pinned catalog."""

import re
from typing import Any

from best_practices_mcp.criteria import get_criteria
from best_practices_mcp.drafts import (
    check_identity,
    field_definitions,
    normalize_draft,
    structural_issues,
)
from best_practices_mcp.errors import DomainError

_URL = re.compile(r"https?://[^/. ]+\.[^ ]")
_CONDITIONAL_CHECKS = ["conditional_requirements"]


def usable_justification(value: Any) -> bool:
    """Match Project#justification_good? without stripping supplied text."""
    return type(value) is str and len(value) >= 5 and not value.startswith("// ")


def contains_url(value: Any) -> bool:
    """Match Project#contains_url?; this deliberately does not parse or fetch URLs."""
    return type(value) is str and not value.startswith("// ") and _URL.search(value) is not None


def _finding(criterion: dict, field: str, code: str, requirement: str, message: str) -> dict:
    return {
        "criterion_id": criterion["criterion_id"],
        "field": field,
        "code": code,
        "requirement": requirement,
        "message": message,
    }


def _requires_justification(criterion: dict, status: str) -> bool:
    # A required URL entails usable justification. Report the stronger URL
    # requirement alone, matching upstream's ordered Met checks.
    if status == "Met" and criterion["met_url_required"]:
        return False
    flag = {"Met": "met_justification_required", "N/A": "na_justification_required"}.get(status)
    return flag is not None and criterion[flag]


def _conditional_findings(criterion: dict, status: str, justification: Any) -> list[dict]:
    findings = []
    if status == "N/A" and not criterion["na_allowed"]:
        findings.append(
            _finding(
                criterion,
                criterion["status_field"],
                "na_not_allowed",
                "na_allowed",
                "This criterion does not allow N/A.",
            )
        )
    if _requires_justification(criterion, status) and not usable_justification(justification):
        findings.append(
            _finding(
                criterion,
                criterion["justification_field"],
                "missing_required_justification",
                f"{status}: justification of at least five characters, not prefixed // ",
                "Required usable justification is missing.",
            )
        )
    if status == "Met" and criterion["met_url_required"] and not contains_url(justification):
        findings.append(
            _finding(
                criterion,
                criterion["justification_field"],
                "missing_required_url",
                "met_url_required",
                "Required URL text is missing.",
            )
        )
    return findings


def _skip_reason(draft: dict, criterion: dict) -> str | None:
    field = criterion["status_field"]
    if field not in draft:
        return "status_absent"
    status = draft[field]
    if status == "?":
        return "status_unknown"
    if type(status) is not str or status not in {"Met", "Unmet", "N/A"}:
        return "status_invalid"
    return None


def _shape_findings(draft: dict, selected: dict, fields: dict) -> list[dict]:
    findings = []
    for issue in structural_issues(draft):
        definition = fields.get(issue["field"], {})
        criterion_id = definition.get("criterion_id")
        if criterion_id is not None and criterion_id not in selected:
            continue
        findings.append(
            {
                **issue,
                "criterion_id": criterion_id,
                "requirement": "recognized_field_shape" if definition else "recognized_field",
            }
        )
    return findings


def _represented(draft: dict, fields: dict) -> set[str]:
    return {
        fields[field]["criterion_id"]
        for field in draft
        if field in fields and fields[field]["criterion_id"] is not None
    }


def validate_draft(project_id: int, level: str, draft: dict[str, Any]) -> dict:
    """Report checkable findings as data, without completing missing answers."""
    if level is None:
        raise DomainError("invalid_level", "A level is required for validation.")
    catalog = get_criteria(level)
    document = normalize_draft(draft)
    identity = check_identity(project_id, document)
    selected = {criterion["criterion_id"]: criterion for criterion in catalog["criteria"]}
    fields = field_definitions()
    represented = _represented(document, fields)
    findings = _shape_findings(document, selected, fields)
    skipped = [
        {
            "criterion_id": key,
            "reason": "other_level",
            "checks": ["field_shape", *_CONDITIONAL_CHECKS],
        }
        for key in sorted(represented - selected.keys())
    ]
    checked = sorted(represented & selected.keys())
    for key in checked:
        criterion = selected[key]
        reason = _skip_reason(document, criterion)
        if reason is not None:
            skipped.append(
                {"criterion_id": key, "reason": reason, "checks": list(_CONDITIONAL_CHECKS)}
            )
        else:
            findings.extend(
                _conditional_findings(
                    criterion,
                    document[criterion["status_field"]],
                    document.get(criterion["justification_field"]),
                )
            )
    return {
        "schema_version": 1,
        "project_id": project_id,
        "level": level,
        "draft_source": {"kind": "explicit", "location": None},
        "identity": identity,
        "catalog": catalog["catalog"],
        "findings": sorted(findings, key=lambda finding: (finding["field"], finding["code"])),
        "checked_criteria": checked,
        "skipped_criteria": sorted(skipped, key=lambda item: item["criterion_id"]),
    }
