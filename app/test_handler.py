"""Unit tests for Platform Ops Auditor Lambda handler."""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

# Set env vars before importing handler
os.environ["AUDIT_TABLE_NAME"] = "test-audit-table"
os.environ["EVENTS_TABLE_NAME"] = "test-events-table"
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

import handler  # noqa: E402


def _make_event(method: str, path: str, body=None) -> dict:
    if isinstance(body, dict):
        body = json.dumps(body)
    return {"httpMethod": method, "path": path, "body": body}


def _patch_tables(audit_items=None, event_items=None):
    """Return a Table factory mock that returns separate mocks per table name."""
    audit_table = MagicMock()
    events_table = MagicMock()
    audit_table.scan.return_value = {"Items": audit_items or []}
    events_table.scan.return_value = {"Items": event_items or []}

    def factory(name):
        if name == os.environ["AUDIT_TABLE_NAME"]:
            return audit_table
        return events_table

    return factory, audit_table, events_table


class TestPostAudit(unittest.TestCase):
    """Tests for POST /audit."""

    def _call(self, body):
        event = _make_event("POST", "/audit", body)
        factory, audit_table, events_table = _patch_tables()
        with patch.object(handler.dynamodb, "Table", side_effect=factory):
            result = handler.handler(event, None)
        return result, audit_table, events_table

    def test_valid_request_returns_201(self):
        body = {
            "service_name": "payments-api",
            "environment": "dev",
            "status": "healthy",
            "repository": "org/payments-api",
            "owner": "platform-team",
        }
        result, audit_table, events_table = self._call(body)
        self.assertEqual(result["statusCode"], 201)
        resp = json.loads(result["body"])
        self.assertIn("audit_id", resp)
        self.assertEqual(resp["service_name"], "payments-api")
        self.assertEqual(resp["score"], 95)
        audit_table.put_item.assert_called_once()
        events_table.put_item.assert_called_once()  # audit_created event

    def test_missing_body_returns_400(self):
        result, _, events_table = self._call(None)
        self.assertEqual(result["statusCode"], 400)
        events_table.put_item.assert_called_once()  # validation_failure event

    def test_invalid_environment_returns_400(self):
        body = {"service_name": "payments-api", "environment": "unknown", "status": "healthy"}
        result, _, _ = self._call(body)
        self.assertEqual(result["statusCode"], 400)
        resp = json.loads(result["body"])
        self.assertTrue(any("environment" in e for e in resp["errors"]))

    def test_invalid_status_returns_400(self):
        body = {"service_name": "payments-api", "environment": "dev", "status": "ok"}
        result, _, _ = self._call(body)
        self.assertEqual(result["statusCode"], 400)
        resp = json.loads(result["body"])
        self.assertTrue(any("status" in e for e in resp["errors"]))

    def test_service_name_too_short_returns_400(self):
        body = {"service_name": "ab", "environment": "dev", "status": "healthy"}
        result, _, _ = self._call(body)
        self.assertEqual(result["statusCode"], 400)

    def test_missing_service_name_returns_400(self):
        body = {"environment": "dev", "status": "healthy"}
        result, _, _ = self._call(body)
        self.assertEqual(result["statusCode"], 400)

    def test_score_without_optional_fields(self):
        body = {"service_name": "my-service", "environment": "prod", "status": "healthy"}
        result, _, _ = self._call(body)
        self.assertEqual(result["statusCode"], 201)
        resp = json.loads(result["body"])
        # 70 base + 5 (name) + 5 (env) + 5 (status) = 85
        self.assertEqual(resp["score"], 85)
        # Findings include "missing" entries when optional fields are absent
        self.assertIn("repository metadata missing", resp["findings"])
        self.assertIn("service owner missing", resp["findings"])

    def test_operational_event_stored_on_validation_failure(self):
        body = {"service_name": "ab", "environment": "dev", "status": "healthy"}
        result, _, events_table = self._call(body)
        self.assertEqual(result["statusCode"], 400)
        events_table.put_item.assert_called_once()


class TestGetSummary(unittest.TestCase):
    """Tests for GET /summary — Operational Intelligence endpoint."""

    def _call(self, audit_items, event_items=None):
        event = _make_event("GET", "/summary")
        factory, _, _ = _patch_tables(audit_items, event_items)
        with patch.object(handler.dynamodb, "Table", side_effect=factory):
            result = handler.handler(event, None)
        return result

    def test_returns_200_with_aggregates(self):
        items = [
            {
                "service_name": "alpha",
                "score": 95,
                "environment": "dev",
                "status": "healthy",
                "findings": ["service owner captured", "repository ownership captured"],
                "created_at": 1000,
            },
            {
                "service_name": "bravo",
                "score": 85,
                "environment": "prod",
                "status": "degraded",
                "findings": ["service owner missing", "repository metadata missing"],
                "created_at": 2000,
            },
        ]
        result = self._call(items)
        self.assertEqual(result["statusCode"], 200)
        resp = json.loads(result["body"])
        self.assertEqual(resp["total_services_audited"], 2)
        self.assertEqual(resp["average_score"], 90)
        self.assertEqual(resp["by_environment"], {"dev": 1, "prod": 1})
        self.assertEqual(resp["by_status"], {"healthy": 1, "degraded": 1})
        self.assertIn("top_findings", resp)
        self.assertIn("recent_operational_events", resp)
        self.assertIn("generated_at", resp)
        self.assertIn("services", resp)
        # Services sorted desc by created_at
        self.assertEqual([s["service_name"] for s in resp["services"]], ["bravo", "alpha"])

    def test_top_findings_ranked_by_frequency(self):
        items = [
            {"service_name": "a", "score": 80, "environment": "dev", "status": "healthy",
             "findings": ["service owner missing", "X"], "created_at": 1},
            {"service_name": "b", "score": 80, "environment": "dev", "status": "healthy",
             "findings": ["service owner missing", "Y"], "created_at": 2},
            {"service_name": "c", "score": 80, "environment": "dev", "status": "healthy",
             "findings": ["service owner missing"], "created_at": 3},
        ]
        result = self._call(items)
        resp = json.loads(result["body"])
        top = resp["top_findings"][0]
        self.assertEqual(top["finding"], "service owner missing")
        self.assertEqual(top["count"], 3)

    def test_services_dedupes_by_latest_audit(self):
        items = [
            {"service_name": "dupe", "score": 60, "environment": "dev", "status": "degraded",
             "findings": [], "created_at": 100},
            {"service_name": "dupe", "score": 90, "environment": "dev", "status": "healthy",
             "findings": [], "created_at": 500},
            {"service_name": "other", "score": 70, "environment": "prod", "status": "degraded",
             "findings": [], "created_at": 200},
        ]
        result = self._call(items)
        resp = json.loads(result["body"])
        # Dedup: 2 distinct services, latest audit per service used
        self.assertEqual(resp["total_services_audited"], 2)
        dupe = next(s for s in resp["services"] if s["service_name"] == "dupe")
        self.assertEqual(dupe["score"], 90)
        self.assertEqual(dupe["status"], "healthy")

    def test_recent_operational_events_sorted_desc(self):
        events = [
            {"event_type": "audit_created", "route": "/audit", "method": "POST", "created_at": 100},
            {"event_type": "validation_failure", "route": "/audit", "method": "POST", "created_at": 300},
            {"event_type": "summary_generated", "route": "/summary", "method": "GET", "created_at": 200},
        ]
        result = self._call([], event_items=events)
        resp = json.loads(result["body"])
        recent = resp["recent_operational_events"]
        # Sorted descending by created_at
        timestamps = [e["created_at"] for e in recent]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))
        self.assertEqual(recent[0]["event_type"], "validation_failure")

    def test_empty_table_returns_200(self):
        result = self._call([])
        self.assertEqual(result["statusCode"], 200)
        resp = json.loads(result["body"])
        self.assertEqual(resp["total_services_audited"], 0)
        self.assertEqual(resp["average_score"], 0)
        self.assertEqual(resp["top_findings"], [])
        self.assertEqual(resp["recent_operational_events"], [])

    def test_summary_event_is_recorded(self):
        event = _make_event("GET", "/summary")
        factory, _, events_table = _patch_tables([], [])
        with patch.object(handler.dynamodb, "Table", side_effect=factory):
            handler.handler(event, None)
        events_table.put_item.assert_called_once()


class TestUnsupportedRoutes(unittest.TestCase):
    """Tests for unsupported methods and paths."""

    def _call(self, method, path):
        event = _make_event(method, path)
        factory, _, _ = _patch_tables()
        with patch.object(handler.dynamodb, "Table", side_effect=factory):
            return handler.handler(event, None)

    def test_get_audit_returns_405(self):
        result = self._call("GET", "/audit")
        self.assertEqual(result["statusCode"], 405)

    def test_post_summary_returns_405(self):
        result = self._call("POST", "/summary")
        self.assertEqual(result["statusCode"], 405)

    def test_unknown_path_returns_405(self):
        result = self._call("GET", "/unknown")
        self.assertEqual(result["statusCode"], 405)

    def test_delete_returns_405(self):
        result = self._call("DELETE", "/audit")
        self.assertEqual(result["statusCode"], 405)


class TestGetAuditByService(unittest.TestCase):
    """Tests for GET /audit/{service_name}."""

    def _call(self, service_name, audit_items):
        event = {
            "httpMethod": "GET",
            "path": f"/audit/{service_name}",
            "pathParameters": {"service_name": service_name},
            "body": None,
        }
        factory, audit_table, events_table = _patch_tables(audit_items=audit_items)
        with patch.object(handler.dynamodb, "Table", side_effect=factory):
            result = handler.handler(event, None)
        return result, events_table

    def test_returns_200_with_history(self):
        items = [
            {"audit_id": "a1", "service_name": "ngx-payments", "score": 60,
             "environment": "prod", "status": "degraded",
             "findings": ["repository metadata missing"], "created_at": 100,
             "owner": "platform-team", "repository": "ngx/payments"},
            {"audit_id": "a2", "service_name": "ngx-payments", "score": 90,
             "environment": "prod", "status": "healthy",
             "findings": [], "created_at": 500,
             "owner": "platform-team", "repository": "ngx/payments"},
            {"audit_id": "a3", "service_name": "other", "score": 80,
             "environment": "dev", "status": "healthy",
             "findings": [], "created_at": 300},
        ]
        result, events_table = self._call("ngx-payments", items)
        self.assertEqual(result["statusCode"], 200)
        resp = json.loads(result["body"])
        self.assertEqual(resp["service_name"], "ngx-payments")
        self.assertEqual(resp["audit_count"], 2)
        # Latest is the most recent (created_at 500)
        self.assertEqual(resp["latest"]["audit_id"], "a2")
        self.assertEqual(resp["latest"]["score"], 90)
        self.assertEqual(resp["latest"]["status"], "healthy")
        # History sorted desc
        self.assertEqual([h["audit_id"] for h in resp["history"]], ["a2", "a1"])
        # audit_lookup operational event recorded
        events_table.put_item.assert_called_once()

    def test_returns_404_when_no_audits_for_service(self):
        items = [
            {"audit_id": "a1", "service_name": "ngx-other", "score": 80,
             "environment": "dev", "status": "healthy", "created_at": 100},
        ]
        result, events_table = self._call("missing-service", items)
        self.assertEqual(result["statusCode"], 404)
        resp = json.loads(result["body"])
        self.assertEqual(resp["error"], "service_not_found")
        # audit_not_found event recorded
        events_table.put_item.assert_called_once()


class TestPostSummarize(unittest.TestCase):
    """Tests for POST /summarize — optional Bedrock-powered summary."""

    def _call(self):
        event = _make_event("POST", "/summarize")
        factory, audit_table, events_table = _patch_tables(audit_items=[
            {"score": 90, "environment": "dev", "status": "healthy", "findings": ["service owner missing"]},
        ])
        with patch.object(handler.dynamodb, "Table", side_effect=factory):
            result = handler.handler(event, None)
        return result, events_table

    def test_returns_501_when_disabled(self):
        with patch.object(handler, "ENABLE_BEDROCK_SUMMARY", False):
            result, events_table = self._call()
        self.assertEqual(result["statusCode"], 501)
        resp = json.loads(result["body"])
        self.assertEqual(resp["error"], "bedrock_disabled")
        # summary_disabled operational event is recorded
        events_table.put_item.assert_called_once()

    def test_returns_200_when_enabled_and_bedrock_succeeds(self):
        with patch.object(handler, "ENABLE_BEDROCK_SUMMARY", True), \
             patch.object(handler, "invoke_bedrock_model", return_value="Platform is healthy."):
            result, events_table = self._call()
        self.assertEqual(result["statusCode"], 200)
        resp = json.loads(result["body"])
        self.assertEqual(resp["summary"], "Platform is healthy.")
        self.assertIn("summary_id", resp)
        self.assertIn("model_id", resp)
        self.assertIn("generated_at", resp)
        # ai_summary_generated event recorded
        events_table.put_item.assert_called_once()

    def test_returns_500_when_bedrock_fails(self):
        with patch.object(handler, "ENABLE_BEDROCK_SUMMARY", True), \
             patch.object(handler, "invoke_bedrock_model", side_effect=RuntimeError("boom")):
            result, events_table = self._call()
        self.assertEqual(result["statusCode"], 500)
        resp = json.loads(result["body"])
        self.assertEqual(resp["error"], "ai_summary_failed")
        # Internal exception details are not exposed
        self.assertNotIn("boom", resp["message"])
        # ai_summary_failed event recorded
        events_table.put_item.assert_called_once()

    def test_build_bedrock_prompt_includes_aggregate_data(self):
        aggregate = {
            "total_services_audited": 3,
            "average_score": 85,
            "by_environment": {"dev": 2, "prod": 1},
            "by_status": {"healthy": 2, "degraded": 1},
            "top_findings": [{"finding": "service owner missing", "count": 1}],
        }
        prompt = handler.build_bedrock_prompt(aggregate)
        self.assertIn("3", prompt)
        self.assertIn("85", prompt)
        self.assertIn("service owner missing", prompt)


class TestScoreCalculation(unittest.TestCase):
    """Tests for the score helper directly."""

    def test_max_score(self):
        body = {
            "service_name": "my-api",
            "environment": "prod",
            "status": "healthy",
            "repository": "org/my-api",
            "owner": "team",
        }
        score, _ = handler._calculate_score(body)
        self.assertEqual(score, 95)

    def test_min_score(self):
        body = {"service_name": "ab", "environment": "invalid", "status": "invalid"}
        score, findings = handler._calculate_score(body)
        self.assertEqual(score, 70)
        self.assertIn("repository metadata missing", findings)
        self.assertIn("service owner missing", findings)

    def test_partial_score_no_optional(self):
        body = {"service_name": "my-api", "environment": "dev", "status": "healthy"}
        score, _ = handler._calculate_score(body)
        self.assertEqual(score, 85)


class TestParseBody(unittest.TestCase):
    """Tests for the JSON body parser."""

    def test_valid_json(self):
        event = {"body": '{"key": "val"}'}
        body, err = handler._parse_body(event)
        self.assertIsNone(err)
        assert body is not None
        self.assertEqual(body["key"], "val")

    def test_invalid_json(self):
        event = {"body": "not-json"}
        body, err = handler._parse_body(event)
        self.assertIsNone(body)
        self.assertIsNotNone(err)

    def test_empty_body(self):
        event = {"body": None}
        body, err = handler._parse_body(event)
        self.assertEqual(body, {})
        self.assertIsNone(err)

    def test_non_object_json(self):
        event = {"body": "[1, 2, 3]"}
        body, err = handler._parse_body(event)
        self.assertIsNone(body)
        self.assertIsNotNone(err)


class TestAggregation(unittest.TestCase):
    """Tests for aggregation helpers in isolation."""

    def test_aggregate_audits_empty(self):
        agg = handler._aggregate_audits([])
        self.assertEqual(agg["total_services_audited"], 0)
        self.assertEqual(agg["average_score"], 0)
        self.assertEqual(agg["top_findings"], [])
        self.assertEqual(agg["services"], [])

    def test_aggregate_audits_counts(self):
        items = [
            {"service_name": "a", "score": 90, "environment": "dev", "status": "healthy",
             "findings": ["a", "b"], "created_at": 1},
            {"service_name": "b", "score": 80, "environment": "dev", "status": "degraded",
             "findings": ["a"], "created_at": 2},
        ]
        agg = handler._aggregate_audits(items)
        self.assertEqual(agg["total_services_audited"], 2)
        self.assertEqual(agg["average_score"], 85)
        self.assertEqual(agg["by_environment"], {"dev": 2})
        self.assertEqual(agg["by_status"], {"healthy": 1, "degraded": 1})
        self.assertEqual(agg["top_findings"][0]["finding"], "a")
        self.assertEqual(agg["top_findings"][0]["count"], 2)


if __name__ == "__main__":
    unittest.main()
