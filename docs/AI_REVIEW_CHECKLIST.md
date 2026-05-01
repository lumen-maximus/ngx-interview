# AI Review Checklist

Use this checklist when reviewing any Copilot-generated change to Platform Ops Auditor. Every item must be verified before merge.

## IAM hygiene

- [ ] No `"Action": "*"` anywhere in any IAM policy
- [ ] No `"Resource": "*"` anywhere in any IAM policy
- [ ] No ARN wildcards (e.g. `arn:aws:dynamodb:*:*:table/*`, `arn:aws:logs:*:*:log-group:/aws/lambda/*:*`)
- [ ] Lambda execution role does **not** attach the AWS managed `AWSLambdaBasicExecutionRole`
- [ ] DynamoDB permissions reference exact table ARNs from the `data` module outputs
- [ ] API Gateway → Lambda permissions reference exact `{stage}/{method}/{path}` source ARNs
- [ ] Optional Bedrock permission, if enabled, is scoped to **one** exact `bedrock-runtime` model ARN — never `bedrock:*` and never `Resource: *`
- [ ] No `bedrock:ListFoundationModels` or other discovery permissions are granted

## Secrets & configuration

- [ ] No hardcoded AWS credentials anywhere in code or Terraform
- [ ] No hardcoded API keys, tokens, or passwords
- [ ] All Terraform-only variables have sensible defaults
- [ ] AWS credentials in CI come **only** from `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` GitHub secrets

## Validation & error handling

- [ ] Every API endpoint validates input shape and returns HTTP 400 with a structured error on failure
- [ ] Internal exceptions are **never** propagated to API callers (HTTP 500 returns a generic message)
- [ ] Validation failures, unsupported routes, and unexpected errors are recorded as structured operational events in DynamoDB
- [ ] `POST /summarize` returns HTTP 501 with a stable error code when Bedrock is disabled
- [ ] `POST /summarize` returns HTTP 500 with a generic message on Bedrock failure (no raw stack traces)

## Tests

- [ ] Python unit tests cover happy path, validation failures, unsupported routes, and operational event side-effects for every endpoint
- [ ] Terraform tests cover: no-wildcard IAM, exact API permission scoping, Bedrock enable/disable behavior
- [ ] All tests pass locally before review

## CI/CD

- [ ] `.github/workflows/terraform.yml` runs `fmt -check`, `init`, `validate`, `test`, `plan` on every PR
- [ ] `terraform apply` is gated to `workflow_dispatch` with explicit `apply: true`
- [ ] Python unit-test job is required on every PR
- [ ] Workflow has explicit `permissions: contents: read`

## Documentation

- [ ] README demo path (`curl POST /audit`, `curl GET /summary`, validation failure, `POST /summarize` disabled) is accurate against current code
- [ ] DECISIONS.md reflects current architecture choices
- [ ] `diagrams/architecture.mmd` reflects current resources (including optional Bedrock)
- [ ] Any new module has its own `variables.tf` and `outputs.tf`

## Architecture discipline

- [ ] No new architecture introduced beyond the documented scope
- [ ] No ECS, EC2, Kubernetes, RDS, React, Cognito, OAuth
- [ ] No external paid services (beyond AWS itself)
- [ ] No spec frameworks (no OpenSpec)
- [ ] No "fancy" abstractions that don't earn their complexity for an MVP
