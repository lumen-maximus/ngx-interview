"""
Platform Ops Auditor — Lambda handler.

Routes:
  POST /audit     — validate service metadata, calculate score, store audit record
  GET  /summary   — aggregate audit records and operational events for Operational Intelligence
  POST /summarize — optional Amazon Bedrock-generated platform posture summary (disabled by default)
"""

import json
import os
import time
import uuid
from collections import Counter

import boto3

# ---------------------------------------------------------------------------
# Configuration (read at cold start)
# ---------------------------------------------------------------------------

# Support both legacy (AUDIT_TABLE) and current (AUDIT_TABLE_NAME) names so the
# handler is resilient to env-variable renames during refactoring.
AUDIT_TABLE = os.environ.get("AUDIT_TABLE_NAME") or os.environ.get("AUDIT_TABLE", "")
EVENTS_TABLE = os.environ.get("EVENTS_TABLE_NAME") or os.environ.get("EVENTS_TABLE", "")

ENABLE_BEDROCK_SUMMARY = os.environ.get("ENABLE_BEDROCK_SUMMARY", "false").lower() == "true"
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
BEDROCK_STUB = os.environ.get("BEDROCK_STUB", "false").lower() == "true"

VALID_ENVIRONMENTS = {"dev", "staging", "prod"}
VALID_STATUSES = {"healthy", "degraded", "unhealthy"}

RECENT_EVENTS_LIMIT = 5
TOP_FINDINGS_LIMIT = 5

dynamodb = boto3.resource("dynamodb")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(body),
    }


def _parse_body(event: dict) -> tuple[dict | None, str | None]:
    """Return (parsed_body, error_message). Returns ({}, None) for empty body."""
    raw = event.get("body") or ""
    if not raw:
        return {}, None
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None, "Request body must be a JSON object"
        return parsed, None
    except (json.JSONDecodeError, ValueError):
        return None, "Invalid JSON in request body"


def _validate_audit(body: dict) -> list[str]:
    """Return a list of validation error messages (empty list means valid)."""
    errors = []

    service_name = body.get("service_name")
    if service_name is None:
        errors.append("service_name is required")
    elif not isinstance(service_name, str):
        errors.append("service_name must be a string")
    elif not (3 <= len(service_name) <= 100):
        errors.append("service_name must be between 3 and 100 characters")

    environment = body.get("environment")
    if environment is None:
        errors.append("environment is required")
    elif environment not in VALID_ENVIRONMENTS:
        errors.append(f"environment must be one of {sorted(VALID_ENVIRONMENTS)}")

    status = body.get("status")
    if status is None:
        errors.append("status is required")
    elif status not in VALID_STATUSES:
        errors.append(f"status must be one of {sorted(VALID_STATUSES)}")

    repository = body.get("repository")
    if repository is not None and not isinstance(repository, str):
        errors.append("repository must be a string if provided")

    owner = body.get("owner")
    if owner is not None and not isinstance(owner, str):
        errors.append("owner must be a string if provided")

    return errors


def _calculate_score(body: dict) -> tuple[int, list[str]]:
    """Return (score, findings) for an audit submission."""
    score = 70
    findings = []

    if body.get("service_name") and isinstance(body["service_name"], str) and 3 <= len(body["service_name"]) <= 100:
        score += 5
        findings.append("service name validated")

    if body.get("environment") in VALID_ENVIRONMENTS:
        score += 5
        findings.append("environment classified")

    if body.get("status") in VALID_STATUSES:
        score += 5
        findings.append("status captured")

    if body.get("repository") and isinstance(body.get("repository"), str):
        score += 5
        findings.append("repository ownership captured")
    else:
        findings.append("repository metadata missing")

    if body.get("owner") and isinstance(body.get("owner"), str):
        score += 5
        findings.append("service owner captured")
    else:
        findings.append("service owner missing")

    findings.append("service metadata captured")

    return score, findings


def _store_event(
    event_type: str,
    route: str,
    method: str,
    message: str,
    related_audit_id: str | None = None,
) -> None:
    """Write a structured operational event to DynamoDB. Silently ignored on failure."""
    if not EVENTS_TABLE:
        return
    try:
        item = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "route": route,
            "method": method,
            "message": message,
            "created_at": int(time.time()),
        }
        if related_audit_id:
            item["related_audit_id"] = related_audit_id
        dynamodb.Table(EVENTS_TABLE).put_item(Item=item)
    except Exception:  # noqa: BLE001
        # Operational event storage is best-effort; never break a request.
        pass


# ---------------------------------------------------------------------------
# Aggregation (used by GET /summary and POST /summarize)
# ---------------------------------------------------------------------------


def _scan_all(table_name: str) -> list[dict]:
    """Scan an entire DynamoDB table, following pagination tokens. MVP scale only."""
    table = dynamodb.Table(table_name)
    items: list[dict] = []
    response = table.scan()
    items.extend(response.get("Items", []))
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))
    return items


def _aggregate_audits(audit_items: list[dict]) -> dict:
    """Compute aggregate statistics and a deduped service catalog.

    `services` contains the most-recent audit per `service_name`, so the
    developer console can render a real catalog (not just counts).
    `total_services_audited` reflects the number of distinct services so
    repeated audits of the same service don't inflate the headline number.
    """
    by_environment: dict[str, int] = {}
    by_status: dict[str, int] = {}
    finding_counter: Counter[str] = Counter()
    latest_per_service: dict[str, dict] = {}

    for item in audit_items:
        for finding in item.get("findings", []) or []:
            if isinstance(finding, str):
                finding_counter[finding] += 1

        name = item.get("service_name")
        if not isinstance(name, str) or not name:
            continue
        created = int(item.get("created_at", 0) or 0)
        existing = latest_per_service.get(name)
        if existing is None or created >= int(existing.get("created_at", 0) or 0):
            latest_per_service[name] = item

    services: list[dict] = []
    for item in latest_per_service.values():
        env = item.get("environment", "unknown")
        st = item.get("status", "unknown")
        by_environment[env] = by_environment.get(env, 0) + 1
        by_status[st] = by_status.get(st, 0) + 1
        services.append(
            {
                "service_name": item.get("service_name", ""),
                "environment": env,
                "status": st,
                "score": int(item.get("score", 0) or 0),
                "owner": item.get("owner", "") or "",
                "repository": item.get("repository", "") or "",
                "audit_id": item.get("audit_id", ""),
                "created_at": int(item.get("created_at", 0) or 0),
                "findings_count": len(item.get("findings", []) or []),
            }
        )

    services.sort(key=lambda s: s["created_at"], reverse=True)

    total = len(services)
    avg_score = round(sum(s["score"] for s in services) / total) if total else 0

    top_findings = [
        {"finding": f, "count": c}
        for f, c in finding_counter.most_common(TOP_FINDINGS_LIMIT)
    ]

    return {
        "total_services_audited": total,
        "average_score": avg_score,
        "by_environment": by_environment,
        "by_status": by_status,
        "top_findings": top_findings,
        "services": services,
    }


def _recent_operational_events(events: list[dict], limit: int = RECENT_EVENTS_LIMIT) -> list[dict]:
    """Return the most recent operational events sorted by created_at descending."""
    sorted_events = sorted(
        events,
        key=lambda e: int(e.get("created_at", 0)),
        reverse=True,
    )
    return [
        {
            "event_type": e.get("event_type", ""),
            "route": e.get("route", ""),
            "method": e.get("method", ""),
            "message": e.get("message", ""),
            "related_audit_id": e.get("related_audit_id", ""),
            "created_at": int(e.get("created_at", 0)),
        }
        for e in sorted_events[:limit]
    ]


# ---------------------------------------------------------------------------
# Bedrock helpers (only invoked when ENABLE_BEDROCK_SUMMARY is true)
# ---------------------------------------------------------------------------


def build_bedrock_prompt(aggregate: dict) -> str:
    """Build a concise natural-language prompt from aggregate operational data."""
    findings_for_prompt = [
        f["finding"] if isinstance(f, dict) else f
        for f in aggregate.get("top_findings", [])
    ]
    return (
        "You are a platform engineering assistant. "
        "Write a short (under 120 words) operational posture summary for the platform "
        "based on the following aggregated audit data:\n"
        f"- Total services audited: {aggregate['total_services_audited']}\n"
        f"- Average operational score: {aggregate['average_score']}\n"
        f"- Services by environment: {json.dumps(aggregate['by_environment'])}\n"
        f"- Services by status: {json.dumps(aggregate['by_status'])}\n"
        f"- Top findings: {json.dumps(findings_for_prompt)}\n"
        "Be concise and actionable. Highlight risk areas if any."
    )


def invoke_bedrock_model(prompt: str, model_id: str) -> str:
    """Invoke a Bedrock foundation model and return the generated text.

    Uses the Converse API which is the recommended path for Amazon Nova and
    cross-region inference profiles. BEDROCK_STUB bypasses the real call for
    demo/test environments where account-level Bedrock access is pending.
    """
    if BEDROCK_STUB:
        return (
            "Platform posture summary (stub): 9 services audited across dev, staging, and prod. "
            "Overall health is mixed — prod services score 95/100, staging shows degraded "
            "connectivity on 2 services (score 60-70), and dev has 1 unhealthy service (score 40). "
            "Top risk: dependency_check findings in staging. Recommend immediate review of "
            "network policies and dependency versions before next production release."
        )
    client = boto3.client("bedrock-runtime")
    response = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 400, "temperature": 0.2},
    )
    return response["output"]["message"]["content"][0]["text"]


def summarize_platform_posture() -> dict:
    """Aggregate audit records and request a Bedrock-generated summary."""
    audit_items = _scan_all(AUDIT_TABLE)
    aggregate = _aggregate_audits(audit_items)
    prompt = build_bedrock_prompt(aggregate)
    summary_text = invoke_bedrock_model(prompt, BEDROCK_MODEL_ID)
    return {
        "summary_id": str(uuid.uuid4()),
        "summary": summary_text,
        "model_id": BEDROCK_MODEL_ID,
        "generated_at": int(time.time()),
    }


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _handle_post_audit(event: dict) -> dict:
    body, parse_error = _parse_body(event)
    if parse_error:
        _store_event("validation_failure", "/audit", "POST", parse_error)
        return _response(400, {"error": parse_error})

    if not body:
        msg = "Request body is required"
        _store_event("validation_failure", "/audit", "POST", msg)
        return _response(400, {"error": msg})

    errors = _validate_audit(body)
    if errors:
        msg = "; ".join(errors)
        _store_event("validation_failure", "/audit", "POST", msg)
        return _response(400, {"errors": errors})

    score, findings = _calculate_score(body)
    audit_id = str(uuid.uuid4())
    created_at = int(time.time())

    item = {
        "audit_id": audit_id,
        "service_name": body["service_name"],
        "environment": body["environment"],
        "status": body["status"],
        "repository": body.get("repository", ""),
        "owner": body.get("owner", ""),
        "score": score,
        "findings": findings,
        "created_at": created_at,
    }

    dynamodb.Table(AUDIT_TABLE).put_item(Item=item)

    _store_event(
        "audit_created",
        "/audit",
        "POST",
        f"Audit created for service '{body['service_name']}'",
        related_audit_id=audit_id,
    )

    return _response(
        201,
        {
            "audit_id": audit_id,
            "service_name": body["service_name"],
            "environment": body["environment"],
            "status": body["status"],
            "score": score,
            "findings": findings,
        },
    )


def _handle_get_summary(event: dict) -> dict:  # noqa: ARG001
    audit_items = _scan_all(AUDIT_TABLE)
    event_items = _scan_all(EVENTS_TABLE) if EVENTS_TABLE else []

    aggregate = _aggregate_audits(audit_items)
    recent_events = _recent_operational_events(event_items)

    _store_event(
        "summary_generated",
        "/summary",
        "GET",
        f"Summary generated over {aggregate['total_services_audited']} audit records",
    )

    return _response(
        200,
        {
            **aggregate,
            "recent_operational_events": recent_events,
            "generated_at": int(time.time()),
        },
    )


def _handle_get_audit_by_service(service_name: str) -> dict:
    """Return all audit records for a single service, newest first.

    Uses a Scan with a server-side FilterExpression because the table is keyed
    by `audit_id` (no GSI on `service_name`). For the demo dataset this is
    perfectly cheap; in production a `service_name`-indexed GSI would be
    preferable.
    """
    if not service_name:
        return _response(400, {"error": "service_name path parameter is required"})

    # Demo dataset is small (<100 records); a client-side filter on Scan keeps
    # the implementation simple and avoids needing a `service_name` GSI.
    # See DECISIONS.md for the GSI vs Scan trade-off.
    all_audits = _scan_all(AUDIT_TABLE)
    items = [i for i in all_audits if i.get("service_name") == service_name]
    items.sort(key=lambda i: int(i.get("created_at", 0) or 0), reverse=True)

    if not items:
        _store_event(
            "audit_not_found",
            f"/audit/{service_name}",
            "GET",
            f"No audits recorded for service '{service_name}'",
        )
        return _response(
            404,
            {
                "error": "service_not_found",
                "message": f"No audits recorded for service '{service_name}'",
            },
        )

    latest = items[0]
    history = [
        {
            "audit_id": i.get("audit_id", ""),
            "created_at": int(i.get("created_at", 0) or 0),
            "environment": i.get("environment", ""),
            "status": i.get("status", ""),
            "score": int(i.get("score", 0) or 0),
            "findings": list(i.get("findings", []) or []),
        }
        for i in items
    ]

    _store_event(
        "audit_lookup",
        f"/audit/{service_name}",
        "GET",
        f"Returned {len(items)} audit record(s) for service '{service_name}'",
    )

    return _response(
        200,
        {
            "service_name": service_name,
            "latest": {
                "audit_id": latest.get("audit_id", ""),
                "environment": latest.get("environment", ""),
                "status": latest.get("status", ""),
                "score": int(latest.get("score", 0) or 0),
                "repository": latest.get("repository", "") or "",
                "owner": latest.get("owner", "") or "",
                "findings": list(latest.get("findings", []) or []),
                "created_at": int(latest.get("created_at", 0) or 0),
            },
            "audit_count": len(items),
            "history": history,
        },
    )


def _handle_post_summarize(event: dict) -> dict:  # noqa: ARG001
    if not ENABLE_BEDROCK_SUMMARY:
        _store_event(
            "summary_disabled",
            "/summarize",
            "POST",
            "AI summary requested but Bedrock is disabled for this deployment",
        )
        return _response(
            501,
            {
                "error": "bedrock_disabled",
                "message": "AI summary is disabled for this deployment",
            },
        )

    try:
        result = summarize_platform_posture()
        _store_event(
            "ai_summary_generated",
            "/summarize",
            "POST",
            f"AI summary generated using model {result['model_id']}",
        )
        return _response(200, result)
    except Exception:  # noqa: BLE001
        _store_event(
            "ai_summary_failed",
            "/summarize",
            "POST",
            "Bedrock invocation failed while generating platform summary",
        )
        return _response(
            500,
            {
                "error": "ai_summary_failed",
                "message": "failed to generate platform summary",
            },
        )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def handler(event: dict, context: object) -> dict:  # noqa: ARG001
    method = event.get("httpMethod", "")
    path = event.get("path", "")
    path_parameters = event.get("pathParameters") or {}

    try:
        if method == "POST" and path == "/audit":
            return _handle_post_audit(event)

        if method == "GET" and path == "/summary":
            return _handle_get_summary(event)

        if method == "GET" and path_parameters.get("service_name"):
            return _handle_get_audit_by_service(path_parameters["service_name"])

        if method == "POST" and path == "/summarize":
            return _handle_post_summarize(event)

        msg = f"Unsupported route: {method} {path}"
        _store_event("unsupported_route", path or "/", method or "UNKNOWN", msg)
        return _response(405, {"error": msg})

    except Exception:  # noqa: BLE001
        _store_event("unexpected_error", path or "/", method or "UNKNOWN", "Unexpected internal error")
        return _response(500, {"error": "Internal server error"})
