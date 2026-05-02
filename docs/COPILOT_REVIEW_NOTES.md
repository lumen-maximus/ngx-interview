# Copilot Review Notes

Operational notes for human reviewers about the Copilot-generated portions of Platform Ops Auditor.

## What Copilot generated

- **Lambda handler (`app/handler.py`)** — routing, validation, scoring, DynamoDB writes, structured operational events, optional Bedrock summarize endpoint
- **Python unit tests (`app/test_handler.py`)** — full coverage of happy path, validation failures, routing, operational event side-effects, and Bedrock enable/disable/failure paths
- **Terraform modules (`terraform/modules/{data,iam,lambda,api,observability}`)** — DynamoDB tables, Lambda + IAM, REST API + permissions, SNS + CloudWatch
- **Terraform tests (`terraform/tests/platform_ops_auditor.tftest.hcl`)** — assertions on no-wildcard IAM, exact API permission scoping, Bedrock enable/disable behavior, all using mocked providers
- **GitHub Actions workflow (`.github/workflows/terraform.yml`)** — `fmt-check → init → validate → test → plan → optional apply`, plus a separate Python unit-test job
- **Documentation** — README.md, DECISIONS.md, this file, `AI_WORKFLOW.md`, `AI_REVIEW_CHECKLIST.md`, architecture diagram

## What human review changed or should verify

### Verified during initial review
- IAM policy was rewritten from a managed policy reference to a hand-crafted exact-ARN policy document
- API Gateway Lambda permissions were narrowed from broad source ARNs to exact `{stage}/{method}/{path}` ARNs
- Lambda zip source was changed from `source_file` to `source_dir` so all Python files are included
- CloudWatch Logs permissions were dropped entirely in favor of DynamoDB operational events

### Verify on every change
- Run `terraform test` and confirm all 9 assertions pass
- Run `pytest app/` and confirm all 30 tests pass
- Inspect every new IAM statement for wildcards (use `AI_REVIEW_CHECKLIST.md`)
- Confirm any new API route has an exact-ARN `aws_lambda_permission` resource

## Security-sensitive areas

| Area | Risk | Mitigation |
|---|---|---|
| `_handle_post_summarize` | Bedrock costs and model availability vary by account | Disabled by default via `enable_bedrock_summary = false`; explicit human enablement required |
| `invoke_bedrock_model` | Model-specific request/response shapes drift over time | Isolated to a single helper so future model swaps are localized |
| `_store_event` | Best-effort DynamoDB write swallows exceptions | Intentional — operational event storage must never break a request |
| `_handle_post_audit` | Validates input but does not enforce uniqueness of `service_name` | Acceptable for MVP; uniqueness would require a GSI |
| `handler` top-level `except` | Catches `Exception` to prevent leaking stack traces | Returns generic HTTP 500; details are logged to DynamoDB events |

## Known tradeoffs

- **DynamoDB Scan on every `GET /summary`** — acceptable at MVP scale (low hundreds of audit records). Adding a GSI on `created_at` would be a performance improvement at higher scale.
- **No CloudWatch Logs** — a deliberate trade-off for strict no-wildcard IAM. Diagnostics rely on DynamoDB operational events and Lambda service metrics.
- **No request-side authentication** — out of scope for the MVP; would be added via API Gateway API keys or IAM authorizer in a real deployment.
- **Lambda ZIP packaging via `archive_file`** — fast and simple. A real deployment would likely use container images and ECR for larger dependency trees.

## Why Bedrock is optional and disabled by default

1. **Account variance** — Bedrock model access is gated per-account and per-model. A reviewer cloning this repo into an arbitrary AWS account cannot guarantee `amazon.nova-lite-v1:0` is enabled.
2. **Cost** — Even small Bedrock calls are billable. The MVP must demo for free.
3. **API contract stability** — The `/summarize` route is always created in API Gateway; only the IAM grant and behavior change. This keeps deployment idempotent regardless of feature flag state.
4. **Strict IAM** — Granting `bedrock:InvokeModel` only when needed keeps the steady-state IAM policy minimal.

## How the AI workflow could be improved in a future iteration

- Add a Copilot reviewer (`gh copilot review`) gated CI step that flags wildcards, missing tests, and missing observability before human review
- Maintain a `prompts/` directory with versioned, reusable Copilot prompts for common refactors
- Surface `AI_REVIEW_CHECKLIST.md` to Copilot as required reading so generations self-correct against banned patterns
- Add eval harness (CodeQL, `tflint`, `checkov`) that gates Copilot-generated diffs before merge
- Track Copilot acceptance rate and rejection reasons in PR comments to refine `copilot-instructions.md` over time

---

## Post-merge iteration log (session 2)

These notes document the second Copilot-assisted iteration session, which focused on browser
compatibility fixes, UI/UX enhancement, and data realism.

### Issues addressed

| Problem | Root cause | AI-assisted fix |
|---|---|---|
| CORS blocked on all API calls | Lambda responses missing `Access-Control-Allow-Origin`; no OPTIONS preflight handlers | Added CORS headers to `_response()` in `handler.py`; added MOCK OPTIONS method/integration/response resources to all three API Gateway routes |
| Favicon 404 | No icon file shipped with console | Created `web/favicon.svg` (SVG bar-chart icon) |
| Browser Topics API noise | Chrome extension noise — unrelated to service code | No fix required; documented |
| Summary looked empty | Only 9 seed records, generic names | Seeded 18 realistic NGX-branded services across prod/staging/dev with realistic scores, owners, findings |

### UI/UX enhancements (Copilot agent spec → implementation)

Copilot `ui-ux-designer` subagent reviewed the static console and returned a 28-point
specification. All changes were applied in a single session:

- API status pill (connected / unreachable) with live health probe on load
- Animated score bar after every `POST /audit` submission
- Skeleton loaders on all stat values and list items until data arrives
- Live pulsing dot on Operational Summary heading
- Score-based colour tinting on stat blocks (green ≥ 80, amber ≥ 50, red < 50)
- Status-coloured list counts (`healthy` green / `degraded` amber / `unhealthy` red)
- Environment dots (grey = dev, amber = staging, blue = prod)
- Fade-up entrance animation on first summary load
- Monospace AI hint code block in the 501 Bedrock-disabled response
- NGX badge in header, updated placeholders throughout, footer timestamp

### Course corrections during session 2

| Copilot default | Human correction |
|---|---|
| `create_file` for existing files | Used terminal heredoc (`cat > file << 'EOF'`) — Copilot adapted without retry |
| Attempted `git stash` with large working tree | Blocked by memory rule; used direct checkout instead |
| Suggested merging `test` into `main` via direct push | Warned this would auto-close the open PR; human confirmed; PR auto-closed (GitHub platform behaviour, not agent error) |
| `gh pr edit --base test` to retarget PR | GitHub rejected: branches identical; agent correctly pivoted to creating a new PR |

### Key takeaway

The most useful AI behaviour in session 2 was **spec → implementation fidelity**: the
`ui-ux-designer` agent produced a precise 28-point spec, and the implementation agent applied
all 28 changes correctly in a single pass with no hallucinated element IDs or broken selectors.
The weakest point was **git state reasoning** — the agent lacked visibility into GitHub's
merge-detection heuristics and needed human guidance on PR lifecycle.
