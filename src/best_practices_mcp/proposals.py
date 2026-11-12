"""Prepare one deterministic URL using BadgeApp's documented query proposal route."""

from urllib.parse import quote, urlencode

from best_practices_mcp.transfer import (
    finish_result,
    override_scope,
    transfer_context,
    transfer_rows,
)

ORIGIN = "https://www.bestpractices.dev"


def prepare_update_url(project_id, level, draft, record, observation, override_fields=None):
    """Encode raw draft text; prediction alone models upstream normalization."""
    draft, criteria, scope, result = transfer_context(project_id, level, draft, record, observation)
    requested, effective = override_scope(
        [] if override_fields is None else override_fields, draft, scope
    )
    rows = transfer_rows(draft, record, criteria, scope, effective, "url")
    effective.intersection_update(
        item["field"] for item in rows if item["disposition"] == "encoded"
    )
    for item in rows:
        item["override"] = item["field"] in effective
    result.update(
        requested_overrides=requested, effective_overrides=sorted(effective), artifact=None
    )
    if finish_result(result, rows):
        params = {
            item["field"]: draft[item["field"]] for item in rows if item["disposition"] == "encoded"
        }
        if effective:
            params["overrides"] = ",".join(sorted(effective))
        query = urlencode(sorted(params.items()), quote_via=quote)
        url = f"{ORIGIN}/en/projects/{project_id}/{level}/edit?{query}"
        result["artifact"] = {"url": url, "encoded_size_bytes": len(url.encode("utf-8"))}
    return result
