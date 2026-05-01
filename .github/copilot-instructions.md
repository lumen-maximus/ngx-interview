# Copilot Instructions — Platform Ops Auditor

## Context

This is a **Senior Platform Engineer coding challenge** project.

The goal is to build a minimal, clean, demoable **internal developer platform automation service** called **Platform Ops Auditor**.

GitHub Copilot Chat / Copilot cloud agent is the **AI-native development workflow** for this project.

---

## Guiding Principles

- **Prioritize clean code** — readable, minimal, well-structured.
- **Terraform quality** — modular Terraform under `terraform/modules/{data,iam,lambda,api,observability}`; keep modules small and focused.
- **Least privilege** — every IAM action and resource must be scoped as tightly as possible.
- **Strict no-wildcard IAM** — no `Action: "*"`, no `Resource: "*"`, no ARN wildcards anywhere.
- **CI/CD** — GitHub Actions must lint, validate, test, and optionally apply Terraform.
- **Observability** — CloudWatch metrics, alarm, dashboard, SNS, and DynamoDB operational events.
- **Documentation** — README and DECISIONS.md must explain every important decision.
- **Demoability** — the project must be runnable and demonstrable end-to-end.

---

## Technology Choices

### Use

- AWS Lambda (Python 3.12)
- REST API Gateway with Lambda proxy integration
- DynamoDB (PAY_PER_REQUEST, SSE, PITR)
- Terraform (HCL, no CDK, no Pulumi)
- GitHub Actions
- CloudWatch metric alarm (Lambda Errors)
- CloudWatch dashboard (Invocations, Errors, Duration, Throttles)
- SNS topic for alarm notifications
- archive_file data source to zip Lambda

### Do Not Use

- ECS, EC2, Kubernetes
- RDS or any relational database
- React or any frontend framework
- AWS Bedrock or any AI/ML service **for the base demo path** — Bedrock is allowed only behind the `enable_bedrock_summary` feature flag (default `false`) and only with `bedrock:InvokeModel` scoped to one exact model ARN
- Complex authentication (no Cognito, no OAuth)
- External paid services
- Unnecessary abstractions or frameworks

---

## IAM Rules (Strict — No Exceptions)

- No `Action: "*"` anywhere
- No `Resource: "*"` anywhere
- No ARN wildcards (e.g., `arn:aws:dynamodb:*:*:table/*`)
- Lambda execution role must reference exact DynamoDB table ARNs
- API Gateway Lambda permissions must reference exact stage/method/path ARNs
- Do not use the AWS managed `AWSLambdaBasicExecutionRole` if it introduces wildcard-style log permissions

---

## Observability Design

Because strict no-wildcard IAM is required, Lambda CloudWatch log-stream permissions cannot be granted cleanly. Instead:

- Record structured operational events in DynamoDB
- Use Lambda service metrics (not log-based metrics) for CloudWatch visibility
- Create a CloudWatch alarm on `Errors >= 1` with SNS notification
- Create a CloudWatch dashboard for Lambda Invocations, Errors, Duration, Throttles

---

## Code Style

- Python: simple functions, clear variable names, no unnecessary classes
- Terraform: alphabetical resource argument ordering where it improves readability
- Tests: unit tests using `unittest` and `unittest.mock`, no pytest plugins required
- Comments: only where logic is non-obvious

---

## When Unsure

Choose the **simplest implementation** that satisfies the challenge requirements.

Prefer:
- One Lambda function over multiple
- One DynamoDB table scan over a complex GSI query
- Small focused Terraform modules over a single sprawling root file
- Clear variable names over clever abstractions

---

## Project Structure

```
.github/
  workflows/
    terraform.yml
  copilot-instructions.md

app/
  handler.py
  requirements.txt
  test_handler.py

terraform/
  versions.tf
  providers.tf
  variables.tf
  main.tf
  outputs.tf
  modules/
    data/
    iam/
    lambda/
    api/
    observability/
  tests/
    platform_ops_auditor.tftest.hcl

docs/
  AI_WORKFLOW.md
  AI_REVIEW_CHECKLIST.md
  COPILOT_REVIEW_NOTES.md

diagrams/
  architecture.mmd

README.md
DECISIONS.md
.gitignore
```

---

## Optional Bedrock Enhancement

`POST /summarize` is an optional, **disabled-by-default** endpoint that uses Amazon Bedrock to generate an AI-written platform posture summary. When `enable_bedrock_summary = true`:
- Lambda receives `bedrock:InvokeModel` scoped to **one exact model ARN** (never `bedrock:*`, never `Resource: *`)
- The route always exists in API Gateway; only the IAM grant and Lambda behavior change
- When disabled, the endpoint returns HTTP 501 with a stable error code

Bedrock-related changes must preserve all no-wildcard IAM rules.
