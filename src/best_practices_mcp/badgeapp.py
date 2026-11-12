"""Public BadgeApp lookup/progress mapping; no drafts or website mutations."""

from __future__ import annotations

import copy
import json
import math
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

from best_practices_mcp.criteria import field_aliases, get_criteria
from best_practices_mcp.documents import validate_document
from best_practices_mcp.errors import DomainError
from best_practices_mcp.models import LEVELS

if TYPE_CHECKING:
    from best_practices_mcp.http import BadgeAppHTTP

ORIGIN = "https://www.bestpractices.dev"
PROJECTS_PATH = "/projects.json"
ASCII_WHITESPACE = " \t\r\n\v\f"
PERCENTAGES = dict(
    zip(
        LEVELS,
        (
            "badge_percentage_0",
            "badge_percentage_1",
            "badge_percentage_2",
            "badge_percentage_baseline_1",
            "badge_percentage_baseline_2",
            "badge_percentage_baseline_3",
        ),
        strict=True,
    )
)
SUMMARY_FIELDS = ("badge_level", "tiered_percentage", "baseline_tiered_percentage")


def _upstream(message: str, field: str | None = None) -> DomainError:
    return DomainError(
        "upstream_invalid_response",
        message,
        details={} if field is None else {"field": field},
        recovery="Retry the public read later; report a persistent upstream format change.",
    )


def _positive_integer(value: Any, field: str) -> int:
    if type(value) is not int or value <= 0:
        raise DomainError("invalid_field", f"{field} must be a positive integer.")
    return value


def _comparable_url(value: Any) -> str | None:
    if not isinstance(value, str) or any(ord(char) <= 32 for char in value):
        return None
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return None
    if parts.username is not None or parts.password is not None:
        return None
    scheme = parts.scheme.lower()
    host = parts.hostname.lower()
    host = f"[{host}]" if ":" in host else host
    if port is not None and port != {"http": 80, "https": 443}[scheme]:
        host = f"{host}:{port}"
    return urlunsplit((scheme, host, parts.path, parts.query, parts.fragment))


def _classify_query(query: str, page: int) -> tuple[str, str]:
    _positive_integer(page, "page")
    if type(query) is not str or not (query := query.strip(ASCII_WHITESPACE)):
        raise DomainError("invalid_query", "Supply a nonempty project ID, URL, or search text.")
    try:
        query.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise DomainError("invalid_query", "Query text must contain valid Unicode.") from exc
    try:
        numeric = bool(re.fullmatch(r"[0-9]+", query)) and int(query) > 0
    except ValueError as exc:
        raise DomainError("invalid_query", "The numeric identifier is too large.") from exc
    if numeric:
        if page != 1:
            raise DomainError("invalid_query", "Numeric project lookup accepts only page 1.")
        return str(int(query)), "id"
    if re.match(r"https?:", query, flags=re.IGNORECASE):
        if _comparable_url(query) is None:
            raise DomainError("invalid_query", "Use an absolute HTTP(S) URL without credentials.")
        return query, "url"
    return query, "text"


def _record(value: Any, expected_id: int | None = None) -> dict:
    if type(value) is not dict:
        raise _upstream("A project response must contain a JSON object.")
    project_id = value.get("id")
    if type(project_id) is not int or project_id <= 0:
        raise _upstream("The public project identifier is missing or invalid.", "id")
    if expected_id is not None and project_id != expected_id:
        raise DomainError(
            "project_mismatch",
            "The public record does not match the requested project.",
            details={"project_id": expected_id, "observed_project_id": project_id},
            recovery="Verify the project ID and retry the public read.",
        )
    return value


def _optional_text(record: dict, field: str) -> str | None:
    value = record.get(field)
    if value is not None and type(value) is not str:
        raise _upstream("A public project text field has an unexpected type.", field)
    return value


def _project(record: dict) -> dict:
    return {
        "project_id": record["id"],
        **{field: _optional_text(record, field) for field in ("name", "repo_url", "homepage_url")},
    }


def _match_basis(record: dict, query: str, kind: str) -> str:
    if kind != "url":
        return kind
    wanted = _comparable_url(query)
    for field in ("repo_url", "homepage_url"):
        if _comparable_url(record.get(field)) == wanted:
            return field
    # Upstream deliberately normalizes some spellings more broadly than identity checks.
    return "url_query"


def _next_link(header: str) -> list[str]:
    links = []
    for url, parameters in re.findall(r"<([^>]*)>([^<]*)", header):
        relation = re.search(r';\s*rel\s*=\s*(?:"([^"]*)"|([^\s;,]+))', parameters, re.I)
        if relation and "next" in (relation.group(1) or relation.group(2)).split():
            links.append(url)
    return links


def _next_page(url: str, source_url: str, params: dict) -> int | None:
    try:
        resolved = urljoin(source_url, url)
        parts = urlsplit(resolved)
        origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        query = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return None
    if origin != ORIGIN or parts.path != PROJECTS_PATH or parts.fragment:
        return None
    expected = {key: [str(value)] for key, value in params.items() if key != "page"}
    if {key: value for key, value in query.items() if key != "page"} != expected:
        return None
    pages = query.get("page", [])
    if len(pages) != 1 or not re.fullmatch(r"[0-9]+", pages[0]):
        return None
    try:
        page = int(pages[0])
    except ValueError:
        return None
    return page if page > params["page"] else None


def _pagination(result: Any, params: dict, empty: bool) -> tuple[int | None, bool]:
    if empty:
        return None, True
    header = next((v for k, v in result.headers.items() if k.lower() == "link"), "")
    links = _next_link(header)
    if len(links) != 1:
        return None, False
    return _next_page(links[0], result.source_url, params), False


def _normalized_record(record: dict) -> dict:
    aliases = field_aliases()
    normalized = {}
    for field, value in record.items():
        canonical = aliases.get(field, field)
        if canonical in normalized:
            before = json.dumps(normalized[canonical], sort_keys=True, allow_nan=False)
            after = json.dumps(value, sort_keys=True, allow_nan=False)
            if before != after:
                raise _upstream("Conflicting canonical and alias values in public data.", canonical)
        normalized[canonical] = value
    return normalized


def _saved_answers(record: dict, definitions: list[dict]) -> tuple[dict, list[dict]]:
    answers, criteria = {}, []
    for definition in definitions:
        status_field = definition["status_field"]
        justification_field = definition["justification_field"]
        for field in (status_field, justification_field):
            if field in record:
                answers[field] = copy.deepcopy(record[field])
        criteria.append(
            {
                "criterion_id": definition["criterion_id"],
                "status_present": status_field in record,
                "status": record.get(status_field),
                "justification_present": justification_field in record,
                "justification": record.get(justification_field),
            }
        )
    _check_answer_bounds(answers)
    return answers, criteria


def _check_answer_bounds(answers: dict) -> None:
    try:
        validate_document(answers)
    except DomainError as exc:
        if exc.code == "document_too_large":
            raise DomainError(
                "response_too_large",
                "Selected public answers exceed the document response budget.",
                recovery="Request fewer criterion IDs for the selected level.",
            ) from exc
        raise _upstream("Public answers contain unsupported JSON values or nesting.") from exc


def _summaries(record: dict) -> list[dict]:
    summaries = []
    for level, field in PERCENTAGES.items():
        value = record.get(field)
        invalid_number = type(value) is float and not math.isfinite(value)
        if value is not None and (type(value) not in (int, float) or invalid_number):
            raise _upstream("A public progress percentage has an unexpected value.", field)
        summaries.append({"level": level, "upstream_percentage": value})
    return summaries


def _observation(result: Any, record: dict) -> dict:
    return {
        "project_id": record["id"],
        "source_url": result.source_url,
        "fetched_at": result.fetched_at,
        "attribution": _optional_text(record, "project_entry_attribution"),
        "license": _optional_text(record, "project_entry_license"),
    }


class BadgeAppClient:
    """Translate public records into contract payloads using one shared HTTP adapter."""

    def __init__(self, http: BadgeAppHTTP) -> None:
        self.http = http

    async def find_project(self, query: str, page: int = 1) -> dict:
        query, kind = _classify_query(query, page)
        if kind == "id":
            return await self._find_id(query)
        params = {"url" if kind == "url" else "q": query, "page": page}
        result = await self.http.get_json(PROJECTS_PATH, params)
        if type(result.data) is not list:
            raise _upstream("Project search must return a JSON array.")
        records = [_record(value) for value in result.data]
        next_page, complete = _pagination(result, params, not records)
        return self._search_result(query, kind, page, records, result, next_page, complete)

    async def _find_id(self, query: str) -> dict:
        path = f"/projects/{query}.json"
        try:
            result = await self.http.get_json(path)
        except DomainError as exc:
            if exc.code != "project_not_found":
                raise
            return {
                "schema_version": 1,
                "query": query,
                "query_kind": "id",
                "page": 1,
                "candidates": [],
                "next_page": None,
                "pagination_complete": True,
                "observation": {
                    "source_url": exc.details.get("source_url", ORIGIN + path),
                    "fetched_at": exc.details.get("fetched_at", datetime.now(UTC).isoformat()),
                },
            }
        record = _record(result.data, int(query))
        return self._search_result(query, "id", 1, [record], result, None, True)

    @staticmethod
    def _search_result(query, kind, page, records, result, next_page, complete) -> dict:
        return {
            "schema_version": 1,
            "query": query,
            "query_kind": kind,
            "page": page,
            "candidates": [
                {"project": _project(record), "match_basis": _match_basis(record, query, kind)}
                for record in records
            ],
            "next_page": next_page,
            "pagination_complete": complete,
            "observation": {"source_url": result.source_url, "fetched_at": result.fetched_at},
        }

    async def get_project_snapshot(self, project_id: int) -> tuple[dict, dict]:
        """Read a complete public record for predictions; preserve missing statuses.

        Pinned _project.json.jbuilder deliberately omits blank justifications.
        Only this complete-record path fills those omitted known fields with "";
        the public progress result continues to report actual field presence.
        """
        _positive_integer(project_id, "project_id")
        result = await self.http.get_json(f"/projects/{project_id}.json")
        record = _normalized_record(_record(result.data, project_id))
        observation = _observation(result, record)
        for level in LEVELS:
            for definition in get_criteria(level)["criteria"]:
                record.setdefault(definition["justification_field"], "")
        return record, observation

    async def get_project_progress(
        self, project_id: int, level: str | None = None, criterion_ids: list[str] | None = None
    ) -> dict:
        _positive_integer(project_id, "project_id")
        catalog = get_criteria(level, criterion_ids)
        result = await self.http.get_json(f"/projects/{project_id}.json")
        record = _normalized_record(_record(result.data, project_id))
        answers, criteria = _saved_answers(record, catalog["criteria"])
        return {
            "schema_version": 1,
            "project": _project(record),
            "level": level,
            "summaries": _summaries(record),
            "answers": answers,
            "criteria": criteria,
            "observation": _observation(result, record),
            "catalog": catalog["catalog"],
            "summary_metadata": {
                key: copy.deepcopy(record[key]) for key in SUMMARY_FIELDS if key in record
            },
        }
