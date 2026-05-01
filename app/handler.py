"""
Platform Ops Auditor — Lambda handler.

Routes:
  POST /audit  — validate service metadata, calculate score, store audit record
  GET  /summary — aggregate audit records and return operational intelligence
"""

import json
import os
import time
import uuid

import boto3

AUDIT_TABLE = os.environ.get("AUDIT_TABLE", "")
EVENTS_TABLE = os.environ.get("EVENTS_TABLE", "")

VALID_ENVIRONMENTS = {"dev", "staging", "prod"}
VALID_STATUSES = {"healthy", "degraded", "unhealthy"}

dynamodb = boto3.resource("dynamodb")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
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
    """Return (score, findings)."""
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

    if body.get("owner") and isinstance(body.get("owner"), str):
        score += 5
        findings.append("service owner captured")

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
        pass


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
    response = dynamodb.Table(AUDIT_TABLE).scan()
    items = response.get("Items", [])

    total = len(items)
    avg_score = round(sum(int(i.get("score", 0)) for i in items) / total) if total else 0

    by_environment: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for item in items:
        env = item.get("environment", "unknown")
        by_environment[env] = by_environment.get(env, 0) + 1
        st = item.get("status", "unknown")
        by_status[st] = by_status.get(st, 0) + 1

    _store_event("summary_generated", "/summary", "GET", f"Summary generated over {total} audit records")

    return _response(
        200,
        {
            "total_services_audited": total,
            "average_score": avg_score,
            "by_environment": by_environment,
            "by_status": by_status,
            "generated_at": int(time.time()),
        },
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def handler(event: dict, context: object) -> dict:  # noqa: ARG001
    method = event.get("httpMethod", "")
    path = event.get("path", "")

    try:
        if method == "POST" and path == "/audit":
            return _handle_post_audit(event)

        if method == "GET" and path == "/summary":
            return _handle_get_summary(event)

        msg = f"Unsupported route: {method} {path}"
        _store_event("unsupported_route", path or "/", method or "UNKNOWN", msg)
        return _response(405, {"error": msg})

    except Exception as exc:  # noqa: BLE001
        _store_event("unexpected_error", path or "/", method or "UNKNOWN", "Unexpected internal error")
        return _response(500, {"error": "Internal server error"})
