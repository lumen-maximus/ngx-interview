# Architectural Decisions

## 1. Why Lambda + REST API Gateway + DynamoDB was chosen over ECS / RDS / Kubernetes

The project is an MVP for an internal developer platform automation service. Traffic is low and bursty: developers submit audits ad-hoc, and the platform team queries summaries on demand. This shape is exactly what serverless was designed for.

- **Lambda** — scale-to-zero, no idle cost, sub-second cold starts at this code size, no infrastructure to maintain.
- **REST API Gateway** — managed HTTPS endpoint with built-in throttling and Lambda proxy integration. No load balancer, no VPC, no certificate management.
- **DynamoDB** — fully managed, PAY_PER_REQUEST billing means zero idle cost, server-side encryption and point-in-time recovery available out of the box. The data model is document-shaped (audit records and operational events) — DynamoDB suits it without requiring a schema or joins.

ECS would mean managing task definitions, an ALB, autoscaling rules, and idle compute cost. EC2 would compound that with patching. Kubernetes would add a control plane, RBAC, network policies, and a much larger blast radius for an MVP. RDS would require a VPC, security groups, parameter groups, multi-AZ tradeoffs, and a relational schema that doesn't earn its complexity for a pair of denormalised tables.

For a real production platform handling thousands of services with complex querying needs, ECS + RDS would be defensible. For this demo, they would be overbuilding.

## 2. Why Option 4 (Operational Intelligence) was chosen as the official additional challenge

The project is, by definition, a platform automation service. Operational intelligence — aggregating signals across many services into actionable summaries — is **the** value proposition of an internal platform. Choosing Option 4 lets the additional challenge reinforce, rather than dilute, the project's core purpose.

`GET /summary` aggregates audit records (totals, averages, environment/status breakdowns, top findings) and reads recent operational events. That is platform engineering work in miniature: take many low-level signals and produce a single high-level posture view.

## 3. Why the scope is intentionally small and demoable

A coding challenge is judged on whether the candidate can ship a working, defensible, hardened system end-to-end — not on lines of code. Every additional feature (user auth, multi-region, custom domains, blue/green deploys) would multiply the surface area for review without materially improving what's being demonstrated.

The MVP fits in a single PR, deploys with one `terraform apply`, demos in five `curl` commands, and is fully covered by 30 Python unit tests + 9 Terraform tests. That is the right scope for a 2–4 hour interview deliverable.

## 4. How strict no-wildcard IAM shaped the observability design

Strict no-wildcard IAM forbids `Action: "*"`, `Resource: "*"`, ARN wildcards, and any policy fragment using `arn:aws:logs:*:*:log-group:/aws/lambda/*:*`. CloudWatch Logs requires wildcard log-stream ARNs (you can't predict log stream names at deploy time), so the Lambda execution role does **not** include any `logs:*` permissions.

That decision cascaded into observability:

- Lambda **service** metrics (Invocations, Errors, Duration, Throttles) are emitted by the Lambda service itself — no IAM needed
- A CloudWatch alarm on `Errors >= 1` notifies an SNS topic
- A CloudWatch dashboard visualises all four service metrics
- Operational events that *would* normally go to logs (validation failures, unsupported routes, unexpected errors, summary generation) are written as structured items to a dedicated DynamoDB table with exact-ARN `PutItem`

The result: full operational awareness without a single wildcard IAM grant.

## 5. Why operational events are stored in DynamoDB instead of CloudWatch Logs

CloudWatch Logs would require either:
- The AWS managed `AWSLambdaBasicExecutionRole` (which uses `arn:aws:logs:*:*:*` wildcards), or
- A custom policy with `logs:CreateLogStream` and `logs:PutLogEvents` on `arn:aws:logs:{region}:{account}:log-group:/aws/lambda/{fn}:*` (still a log-stream wildcard)

Neither is acceptable under strict no-wildcard IAM. DynamoDB sidesteps the problem entirely:

- `dynamodb:PutItem` is granted on **one exact table ARN**
- Events are durable, queryable, and structured (vs unstructured log lines)
- The same table powers `GET /summary`'s `recent_operational_events` field — observability data becomes platform intelligence
- DynamoDB has built-in TTL if retention becomes a concern

The tradeoff: no real-time tail experience like `aws logs tail`. For a platform automation service this is acceptable; live debugging is rare and `Scan` over a small events table is fast.

## 6. What Option 1 practices were borrowed and why RDS / full KMS complexity was avoided

Option 1 practices borrowed:
- **Terraform modules** — `modules/{data,iam,lambda,api,observability}` with clean inputs and outputs
- **Terraform tests** — `terraform test` with mock providers, asserting the design's hard constraints
- **DynamoDB encryption at rest + PITR** — both tables
- **API Gateway HTTPS + AWS SDK HTTPS** — encryption in transit
- **CloudWatch dashboard** — visualised metrics
- **Managed scaling** — Lambda concurrency + DynamoDB on-demand

What was not borrowed:
- **RDS** — there is no relational data; adding RDS just to claim Option 1 would be infrastructure theatre
- **Customer-managed KMS keys** — clean no-wildcard CMK policies are non-trivial. KMS key policies typically need either `kms:*` for the root account or carefully constructed condition keys. Implementing CMKs *and* maintaining strict no-wildcard hygiene is real work that doesn't fit MVP scope. Documented as a future improvement.
- **Manual autoscaling configuration** — Lambda and DynamoDB on-demand handle scaling automatically; explicit autoscaling policies would be redundant complexity

The project explicitly does **not** claim full Option 1 completion. It borrows the practices that genuinely improve the project for an MVP.

## 7. What Option 2 practices were borrowed and why Bedrock is optional

Option 2 practices borrowed:
- **Staged AI workflow** — generate MVP → harden security → strengthen operational intelligence → add optional AI maturity → final review
- **AI review checklist** — explicit gates against wildcard IAM, missing tests, missing observability
- **Copilot review notes** — documented what Copilot generated, where it was course-corrected, and known tradeoffs
- **Optional Bedrock-powered `POST /summarize`** — an AI summary of platform posture

Bedrock is optional and disabled by default for four reasons:

1. **Account variance** — Bedrock model access is gated per-account. A reviewer cloning this repo into an arbitrary AWS account cannot guarantee `amazon.nova-lite-v1:0` is enabled.
2. **Cost** — Even small Bedrock calls are billable. The MVP must demo for free.
3. **API contract stability** — The `/summarize` route is always created in API Gateway; only the IAM grant and the Lambda's behavior change. This keeps deployment idempotent regardless of feature flag state.
4. **Strict IAM** — Granting `bedrock:InvokeModel` only when needed keeps the steady-state IAM policy minimal. When enabled, the grant is scoped to **one** exact model ARN — never `bedrock:*`, never `Resource: *`.

The project explicitly does **not** claim full Option 2 completion unless Bedrock is enabled and demonstrated.

## 8. What would be improved with more time

- **GSI on `environment` and `status`** — replace `Scan` in `GET /summary` with targeted `Query` calls for higher scale
- **Pagination** — return audit records in pages with cursor-based iteration
- **Customer-managed KMS keys** — for both DynamoDB tables and SNS topic, with a tightly scoped key policy
- **API key or IAM authorizer** — for write endpoints (`POST /audit`, `POST /summarize`)
- **WAF in front of API Gateway** — basic rate limiting and geo blocks
- **`tflint` and `checkov` in CI** — additional Terraform quality gates beyond `validate` + `test`
- **Container image packaging** — replace `archive_file` zip with ECR-backed Lambda for richer dependency support
- **OpenTelemetry traces** — written to DynamoDB or X-Ray for distributed tracing without log-stream IAM
- **AI-assisted CI** — Copilot reviewer that flags wildcards and missing tests before human review
- **Multi-region deployment** — DynamoDB Global Tables + per-region API Gateway + Route 53 latency routing
- **SNS subscriptions via Terraform variable** — let the deployer specify email/PagerDuty/Slack endpoints declaratively

## 9. Static developer console: plain HTML over React, S3 + CloudFront over containers

**Decision:** Ship a static `web/` console (plain HTML, CSS, vanilla JS) hosted on S3 + CloudFront with Origin Access Control. No React, no build pipeline, no authentication.

**Alternatives considered:**

| Option | Why rejected |
|--------|-------------|
| React / Next.js | Introduces npm, Webpack/Vite, a build step, and hundreds of transitive dependencies — all for a single-page internal tool. Adds CI complexity with no commensurate value for a demo. |
| ECS-hosted frontend | Adds a container image build, an ALB, and a task definition. The static files have no server-side logic; a CDN is cheaper, faster, and simpler. |
| Cognito auth | The primary audience is internal platform engineers in a demo context. Auth is listed as "do not add" in the project brief. It can be layered on later with CloudFront signed URLs or a Cognito hosted UI. |
| Single-page app inside API Gateway | Would require binary media type support and CORS tweaks. Terraform module complexity outweighs the saving of one CloudFront resource. |

**Why S3 + CloudFront + OAC:**

- S3 bucket is private. The public access block is fully enabled. CloudFront OAC is the only allowed principal via a `StringEquals AWS:SourceArn` condition — no wildcard principal, no `s3:*`.
- CloudFront gives HTTPS by default (redirect HTTP → HTTPS), edge caching, and a globally stable URL.
- The entire infra is wrapped in `count = var.enable_static_console ? 1 : 0` so it is opt-in. No web infrastructure is created unless the flag is set.
- GitHub Actions syncs `web/` after `terraform apply` and creates a CloudFront invalidation — deploy is fully automated, consistent with the immutable infrastructure principle.

**Why auth was omitted for MVP scope:** The console calls only `GET /summary` (read) and `POST /audit` / `POST /summarize` (write). For a demo, the blast radius of unauthenticated writes is a handful of DynamoDB items. For production, the recommended path is CloudFront signed URLs with a Lambda@Edge authorizer or an API Gateway API key — both can be added without changing the static files or the Lambda handler.
