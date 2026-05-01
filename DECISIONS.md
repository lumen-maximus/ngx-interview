# Architecture Decision Records — Platform Ops Auditor

---

## 1. Why Lambda + REST API Gateway + DynamoDB

**Lambda** was chosen because the service is event-driven and stateless. Each API call is a discrete invocation — no persistent process is needed, and Lambda scales to zero when idle. This eliminates the operational overhead of ECS task definitions, container image builds, cluster management, and load balancer configuration.

**REST API Gateway** was chosen because it provides a managed entry point with zero infrastructure to maintain. It handles TLS termination, throttling, and routing. The Lambda proxy integration keeps the handler code in full control of the HTTP response shape.

**DynamoDB** was chosen because:
- The data model is document-oriented (audit records, operational events)
- There is no need for joins, transactions, or SQL
- PAY_PER_REQUEST billing means zero cost when idle
- DynamoDB is fully managed — no RDS maintenance, no schema migrations, no connection pooling

**ECS, EC2, Kubernetes, and RDS were explicitly rejected** because they introduce disproportionate operational surface area for a service with two API endpoints and simple storage requirements.

---

## 2. Why Option 4: Operational Intelligence Was Chosen

Option 4 (Operational Intelligence) was selected because it complements the core audit record API naturally. The `GET /summary` endpoint aggregates existing audit records and returns:

- Total services audited
- Average operational score
- Breakdown by environment
- Breakdown by status

This satisfies the challenge requirement to *aggregate and present platform operational data* without requiring additional infrastructure. The same DynamoDB table that stores audit records becomes the operational intelligence store.

The structured operational events table (validation failures, successful creations, summary generations, unsupported routes) further demonstrates operational awareness — any operational anomaly is captured and queryable.

---

## 3. Why the Scope Is Intentionally Small and Demoable

A Senior Platform Engineer interview challenge is best served by a project that is:

- **Deployable in under 5 minutes** (`terraform apply`)
- **Demonstrable in a 15-minute walkthrough** (two curl commands, a CloudWatch dashboard, a DynamoDB table view)
- **Clearly understandable** to a reviewer who reads the code for the first time

Complexity is a liability in this context. Over-engineering (adding Cognito auth, VPCs, multiple Lambda functions, event streaming) would obscure the core competencies being evaluated: infrastructure-as-code quality, IAM hygiene, observability design, and API design.

The single Lambda function, two DynamoDB tables, and two API endpoints are sufficient to demonstrate all required competencies.

---

## 4. How Strict No-Wildcard IAM Shaped the Observability Design

The requirement to avoid all IAM wildcards (`Action: *`, `Resource: *`, ARN wildcards) had a direct impact on the observability design.

**The problem with CloudWatch Logs:** Lambda automatically publishes logs to CloudWatch Logs. To allow Lambda to write logs, the standard permission is:

```json
{
  "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
  "Resource": "arn:aws:logs:*:*:log-group:/aws/lambda/*:*"
}
```

This uses a wildcard ARN (`/aws/lambda/*:*`) which violates the no-wildcard requirement.

**The alternative:** Instead of granting log-stream permissions, structured operational events are written to DynamoDB using an exact-ARN policy:

```hcl
statement {
  actions   = ["dynamodb:PutItem"]
  resources = [aws_dynamodb_table.events.arn]
}
```

This is arguably a better design anyway: operational events are queryable, structured, and persistent — unlike CloudWatch Logs which requires log parsing and has shorter retention by default.

Lambda service metrics (Invocations, Errors, Duration, Throttles) are available in the `AWS/Lambda` CloudWatch namespace **without any IAM permissions** — they are emitted by the Lambda service automatically. These are used for the CloudWatch alarm and dashboard.

---

## 5. Why Operational Events Are Stored in DynamoDB

Three reasons:

1. **IAM hygiene:** As described above, granting `logs:CreateLogStream` on wildcard log-stream ARNs violates the no-wildcard requirement. DynamoDB PutItem on an exact table ARN does not.

2. **Queryability:** Operational events in DynamoDB are structured JSON documents. A platform team can query for all `validation_failure` events, all events for a specific service, or all `unexpected_error` events. CloudWatch Logs requires a Logs Insights query with log format parsing.

3. **Durability:** DynamoDB has PITR enabled. Operational events survive Lambda function deletion, log group expiration, and account region changes.

The trade-off is DynamoDB cost for write-heavy event streams. For this MVP scale (dozens to hundreds of events per day), PAY_PER_REQUEST DynamoDB is effectively free. For high-throughput production use, a dedicated logging solution (CloudWatch Logs with exact-ARN permissions, or OpenSearch) would be more appropriate.

---

## 6. What Would Be Improved With More Time

| Area | Current | Improved |
|---|---|---|
| DynamoDB queries | Table scan on `GET /summary` | GSI on `environment` and `status` for O(1) queries |
| Summary pagination | No pagination | Cursor-based pagination for large datasets |
| CloudWatch Logs | Not enabled (IAM constraint) | Exact-ARN log group permissions after IAM review |
| SNS subscriptions | Topic created, no subscribers | Email/PagerDuty subscription via Terraform variable |
| Service score trends | Point-in-time score only | Score history with `created_at` GSI for trend analysis |
| Auth | None (intentional for MVP) | API key or IAM auth for write endpoints |
| Error detail | Generic 500 messages | Structured error codes without leaking internals |
| Terraform state | Local state | Remote state in S3 with DynamoDB lock |
