"""
Seed realistic NGX platform services into DynamoDB for demo purposes.
Usage: AWS_PROFILE=ngx-interview python3 scripts/seed_data.py
"""
import boto3
import uuid
import time
import random

TABLE = "platform-ops-auditor-dev-audits"
REGION = "us-east-1"

# Realistic NGX services — spread across envs, statuses, teams
SERVICES = [
    # prod — core money-path services
    {
        "service_name": "ngx-payments-gateway",
        "environment": "prod",
        "status": "healthy",
        "repository": "ngx/payments-gateway",
        "owner": "payments-team",
        "score": 94,
        "findings": [
            "all SLOs within threshold",
            "readiness probe configured",
            "runbook linked in service registry",
            "owner tag present",
            "circuit breaker enabled",
        ],
    },
    {
        "service_name": "ngx-auth-service",
        "environment": "prod",
        "status": "healthy",
        "repository": "ngx/auth-service",
        "owner": "platform-team",
        "score": 91,
        "findings": [
            "JWT validation enforced",
            "rate-limiting active",
            "owner tag present",
            "readiness probe configured",
        ],
    },
    {
        "service_name": "ngx-api-gateway",
        "environment": "prod",
        "status": "healthy",
        "repository": "ngx/api-gateway",
        "owner": "platform-team",
        "score": 96,
        "findings": [
            "WAF rules attached",
            "request throttling enabled",
            "all SLOs within threshold",
            "owner tag present",
        ],
    },
    {
        "service_name": "ngx-notification-service",
        "environment": "prod",
        "status": "healthy",
        "repository": "ngx/notification-service",
        "owner": "comms-team",
        "score": 87,
        "findings": [
            "dead-letter queue configured",
            "owner tag present",
            "retry policy set",
        ],
    },
    {
        "service_name": "ngx-user-profile-api",
        "environment": "prod",
        "status": "healthy",
        "repository": "ngx/user-profile-api",
        "owner": "identity-team",
        "score": 89,
        "findings": [
            "PII fields encrypted at rest",
            "owner tag present",
            "readiness probe configured",
        ],
    },
    {
        "service_name": "ngx-reporting-service",
        "environment": "prod",
        "status": "degraded",
        "repository": "ngx/reporting-service",
        "owner": "data-team",
        "score": 57,
        "findings": [
            "p99 latency exceeding SLO by 340ms",
            "missing readiness probe",
            "no circuit breaker configured",
            "owner tag present",
        ],
    },
    {
        "service_name": "ngx-search-indexer",
        "environment": "prod",
        "status": "degraded",
        "repository": "ngx/search-indexer",
        "owner": "search-team",
        "score": 61,
        "findings": [
            "index lag >5 min on 2 shards",
            "no SLO defined",
            "owner tag present",
            "readiness probe configured",
        ],
    },
    {
        "service_name": "ngx-legacy-billing",
        "environment": "prod",
        "status": "unhealthy",
        "repository": "ngx/legacy-billing",
        "owner": "billing-team",
        "score": 28,
        "findings": [
            "no readiness probe",
            "no runbook",
            "missing owner tag",
            "3 open P1 incidents",
            "no SLO defined",
            "no circuit breaker",
        ],
    },
    # staging
    {
        "service_name": "ngx-checkout-service",
        "environment": "staging",
        "status": "healthy",
        "repository": "ngx/checkout-service",
        "owner": "commerce-team",
        "score": 88,
        "findings": [
            "integration tests passing",
            "owner tag present",
            "readiness probe configured",
        ],
    },
    {
        "service_name": "ngx-fraud-detector",
        "environment": "staging",
        "status": "healthy",
        "repository": "ngx/fraud-detector",
        "owner": "risk-team",
        "score": 83,
        "findings": [
            "model version pinned",
            "feature drift monitoring enabled",
            "owner tag present",
        ],
    },
    {
        "service_name": "ngx-webhook-dispatcher",
        "environment": "staging",
        "status": "healthy",
        "repository": "ngx/webhook-dispatcher",
        "owner": "platform-team",
        "score": 85,
        "findings": [
            "retry queue configured",
            "HMAC signature verification present",
            "owner tag present",
        ],
    },
    {
        "service_name": "ngx-inventory-api",
        "environment": "staging",
        "status": "degraded",
        "repository": "ngx/inventory-api",
        "owner": "supply-team",
        "score": 54,
        "findings": [
            "intermittent 503s under load test",
            "no circuit breaker",
            "missing owner tag",
            "SLO not defined",
        ],
    },
    {
        "service_name": "ngx-order-orchestrator",
        "environment": "staging",
        "status": "healthy",
        "repository": "ngx/order-orchestrator",
        "owner": "commerce-team",
        "score": 80,
        "findings": [
            "saga pattern implemented",
            "dead-letter queue configured",
            "owner tag present",
        ],
    },
    # dev
    {
        "service_name": "ngx-feature-flags",
        "environment": "dev",
        "status": "healthy",
        "repository": "ngx/feature-flags",
        "owner": "platform-team",
        "score": 90,
        "findings": [
            "SDK version up-to-date",
            "owner tag present",
            "rollout rules validated",
        ],
    },
    {
        "service_name": "ngx-analytics-pipeline",
        "environment": "dev",
        "status": "healthy",
        "repository": "ngx/analytics-pipeline",
        "owner": "data-team",
        "score": 76,
        "findings": [
            "schema registry linked",
            "owner tag present",
            "no SLO defined",
        ],
    },
    {
        "service_name": "ngx-config-service",
        "environment": "dev",
        "status": "degraded",
        "repository": "ngx/config-service",
        "owner": "platform-team",
        "score": 47,
        "findings": [
            "hot-reload failure on 2 replicas",
            "no readiness probe",
            "missing circuit breaker",
            "no SLO defined",
        ],
    },
    {
        "service_name": "ngx-ml-scoring-api",
        "environment": "dev",
        "status": "unhealthy",
        "repository": "ngx/ml-scoring-api",
        "owner": "ml-team",
        "score": 31,
        "findings": [
            "model artifact missing",
            "no owner tag",
            "no readiness probe",
            "no runbook",
            "unresolved dependency on ngx-feature-flags@canary",
        ],
    },
    {
        "service_name": "ngx-event-bus",
        "environment": "dev",
        "status": "healthy",
        "repository": "ngx/event-bus",
        "owner": "platform-team",
        "score": 82,
        "findings": [
            "schema validation enabled",
            "consumer lag monitoring active",
            "owner tag present",
        ],
    },
]

# Stagger timestamps so recent_operational_events list looks realistic
BASE_TS = int(time.time())


def seed():
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table = dynamodb.Table(TABLE)

    print(f"Seeding {len(SERVICES)} services into {TABLE} ...")
    for i, svc in enumerate(SERVICES):
        item = {
            "audit_id":    str(uuid.uuid4()),
            "service_name": svc["service_name"],
            "environment": svc["environment"],
            "status":      svc["status"],
            "score":       svc["score"],
            "findings":    svc["findings"],
            "repository":  svc["repository"],
            "owner":       svc["owner"],
            # Stagger over the last 6 hours
            "created_at":  BASE_TS - (len(SERVICES) - i) * 1280 + random.randint(-60, 60),
        }
        table.put_item(Item=item)
        print(f"  ✓ {svc['service_name']} ({svc['environment']}, {svc['status']}, score={svc['score']})")

    print(f"\nDone. {len(SERVICES)} records written.")


if __name__ == "__main__":
    seed()
