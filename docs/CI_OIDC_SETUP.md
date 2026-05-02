# GitHub Actions → AWS via OIDC

This repo's CI/CD workflow (`.github/workflows/terraform.yml`) uses **GitHub OIDC** to assume an
AWS IAM role at runtime. There are **no long-lived AWS access keys** stored in GitHub.

## One-time AWS setup

Run from your local machine with admin AWS credentials. Replace `<ACCOUNT_ID>` with your AWS
account ID, and confirm the repo path matches `lumen-maximus/ngx-interview`.

### 1. Create the GitHub OIDC provider (once per AWS account)

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

(If it already exists, this will error harmlessly — proceed.)

### 2. Create the IAM role with a scoped trust policy

`trust-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:lumen-maximus/ngx-interview:*"
      }
    }
  }]
}
```

```bash
aws iam create-role \
  --role-name github-actions-ngx-interview \
  --assume-role-policy-document file://trust-policy.json

# Start broad; tighten later (see "Hardening" below)
aws iam attach-role-policy \
  --role-name github-actions-ngx-interview \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

### 3. Configure the GitHub repository

In **Settings → Secrets and variables → Actions → Variables**, add:

| Name | Value |
| --- | --- |
| `AWS_ROLE_ARN` | `arn:aws:iam::<ACCOUNT_ID>:role/github-actions-ngx-interview` |
| `AWS_REGION` *(optional)* | `us-east-1` |

No secrets are required.

### 4. Re-run the workflow

The `terraform` job will now assume the role via OIDC, run
`fmt → init → validate → test → plan`, and upload the plan artifact.
Trigger `workflow_dispatch` with `apply: true` to deploy.

## Behaviour when `AWS_ROLE_ARN` is not set

The workflow detects this and:
- Still runs `python-tests`
- Still runs `terraform fmt -check` and `terraform validate` (with `-backend=false`)
- Skips `terraform test`, `plan`, and `apply`
- Emits a workflow warning explaining the missing variable

This keeps PR CI green for fork contributors without AWS access.

## Hardening (for production posture)

- Restrict the trust `sub` to a specific branch or environment, e.g.
  `repo:lumen-maximus/ngx-interview:ref:refs/heads/main` or
  `repo:lumen-maximus/ngx-interview:environment:prod`.
- Replace `AdministratorAccess` with a scoped policy covering only the services this
  stack provisions: Lambda, API Gateway, DynamoDB, IAM (PassRole limited to the Lambda
  execution role ARN), CloudWatch, SNS, and S3 + DynamoDB for remote state.
- Enable a GitHub **Environment** named `prod` with required reviewers, and gate the
  apply step with `environment: prod`.

## Why OIDC and not access keys

- No long-lived credentials in GitHub secrets — eliminates the most common AWS leak vector.
- Trust policy binds the role to this exact repo, so a leaked workflow file from another
  repo cannot assume the role.
- Each workflow run gets short-lived STS credentials with a unique session name
  (`gha-ngx-interview-<run_id>`) for clean CloudTrail attribution.
