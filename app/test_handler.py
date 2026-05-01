"""Unit tests for Platform Ops Auditor Lambda handler."""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

# Set env vars before importing handler
os.environ["AUDIT_TABLE"] = "test-audit-table"
os.environ["EVENTS_TABLE"] = "test-events-table"
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

import handler  # noqa: E402


def _make_event(method: str, path: str, body: dict | str | None = None) -> dict:
    if isinstance(body, dict):
        body = json.dumps(body)
    return {"httpMethod": method, "path": path, "body": body}


class TestPostAudit(unittest.TestCase):
    """Tests for POST /audit."""

    def _call(self, body):
        event = _make_event("POST", "/audit", body)
        with patch.object(handler.dynamodb, "Table") as mock_table_factory:
            mock_table = MagicMock()
            mock_table_factory.return_value = mock_table
            result = handler.handler(event, None)
        return result, mock_table

    def test_valid_request_returns_201(self):
        body = {
            "service_name": "payments-api",
            "environment": "dev",
            "status": "healthy",
            "repository": "org/payments-api",
            "owner": "platform-team",
        }
        result, mock_table = self._call(body)
        self.assertEqual(result["statusCode"], 201)
        resp = json.loads(result["body"])
        self.assertIn("audit_id", resp)
        self.assertEqual(resp["service_name"], "payments-api")
        self.assertEqual(resp["environment"], "dev")
        self.assertEqual(resp["status"], "healthy")
        self.assertEqual(resp["score"], 95)
        # DynamoDB PutItem should be called at least once (audit + event)
        self.assertGreaterEqual(mock_table.put_item.call_count, 1)

    def test_missing_body_returns_400(self):
        result, _ = self._call(None)
        self.assertEqual(result["statusCode"], 400)
        resp = json.loads(result["body"])
        self.assertIn("error", resp)

    def test_invalid_environment_returns_400(self):
        body = {"service_name": "payments-api", "environment": "unknown", "status": "healthy"}
        result, _ = self._call(body)
        self.assertEqual(result["statusCode"], 400)
        resp = json.loads(result["body"])
        self.assertIn("errors", resp)
        self.assertTrue(any("environment" in e for e in resp["errors"]))

    def test_invalid_status_returns_400(self):
        body = {"service_name": "payments-api", "environment": "dev", "status": "ok"}
        result, _ = self._call(body)
        self.assertEqual(result["statusCode"], 400)
        resp = json.loads(result["body"])
        self.assertIn("errors", resp)
        self.assertTrue(any("status" in e for e in resp["errors"]))

    def test_service_name_too_short_returns_400(self):
        body = {"service_name": "ab", "environment": "dev", "status": "healthy"}
        result, _ = self._call(body)
        self.assertEqual(result["statusCode"], 400)

    def test_missing_service_name_returns_400(self):
        body = {"environment": "dev", "status": "healthy"}
        result, _ = self._call(body)
        self.assertEqual(result["statusCode"], 400)

    def test_score_without_optional_fields(self):
        body = {"service_name": "my-service", "environment": "prod", "status": "healthy"}
        result, _ = self._call(body)
        self.assertEqual(result["statusCode"], 201)
        resp = json.loads(result["body"])
        # 70 base + 5 (name) + 5 (env) + 5 (status) = 85
        self.assertEqual(resp["score"], 85)

    def test_operational_event_stored_on_validation_failure(self):
        body = {"service_name": "ab", "environment": "dev", "status": "healthy"}
        event = _make_event("POST", "/audit", body)
        with patch.object(handler.dynamodb, "Table") as mock_table_factory:
            mock_table = MagicMock()
            mock_table_factory.return_value = mock_table
            result = handler.handler(event, None)
        self.assertEqual(result["statusCode"], 400)
        # _store_event calls put_item on the events table
        self.assertGreaterEqual(mock_table.put_item.call_count, 1)


class TestGetSummary(unittest.TestCase):
    """Tests for GET /summary."""

    def _call(self, scan_items):
        event = _make_event("GET", "/summary")
        with patch.object(handler.dynamodb, "Table") as mock_table_factory:
            mock_table = MagicMock()
            mock_table.scan.return_value = {"Items": scan_items}
            mock_table_factory.return_value = mock_table
            result = handler.handler(event, None)
        return result

    def test_returns_200(self):
        items = [
            {"score": 95, "environment": "dev", "status": "healthy"},
            {"score": 85, "environment": "prod", "status": "degraded"},
        ]
        result = self._call(items)
        self.assertEqual(result["statusCode"], 200)
        resp = json.loads(result["body"])
        self.assertEqual(resp["total_services_audited"], 2)
        self.assertIn("average_score", resp)
        self.assertIn("by_environment", resp)
        self.assertIn("by_status", resp)
        self.assertIn("generated_at", resp)

    def test_empty_table_returns_200(self):
        result = self._call([])
        self.assertEqual(result["statusCode"], 200)
        resp = json.loads(result["body"])
        self.assertEqual(resp["total_services_audited"], 0)
        self.assertEqual(resp["average_score"], 0)


class TestUnsupportedRoutes(unittest.TestCase):
    """Tests for unsupported methods and paths."""

    def _call(self, method, path):
        event = _make_event(method, path)
        with patch.object(handler.dynamodb, "Table") as mock_table_factory:
            mock_table = MagicMock()
            mock_table_factory.return_value = mock_table
            result = handler.handler(event, None)
        return result

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
        score, findings = handler._calculate_score(body)
        self.assertEqual(score, 95)

    def test_min_score(self):
        body = {"service_name": "ab", "environment": "invalid", "status": "invalid"}
        score, _ = handler._calculate_score(body)
        # service_name too short → no +5; bad env/status → no +5 each
        self.assertEqual(score, 70)

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


if __name__ == "__main__":
    unittest.main()
