# Platform Ops Auditor — Terraform tests
#
# Uses Terraform's built-in test framework with mocked AWS / archive providers,
# so no real cloud resources are created. Assertions enforce critical design
# decisions including strict no-wildcard IAM, Lambda configuration, exact
# API Gateway permissions, and a tightly-scoped Bedrock InvokeModel grant.

mock_provider "aws" {
  # Provide minimal valid JSON for any aws_iam_policy_document data source so
  # downstream resource validation (e.g. assume_role_policy) accepts the value.
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":\"sts:AssumeRole\",\"Principal\":{\"Service\":\"lambda.amazonaws.com\"}}]}"
    }
  }

  mock_data "aws_caller_identity" {
    defaults = {
      account_id = "123456789012"
    }
  }

  # Provide valid-shaped ARNs/IDs for resources whose attributes feed into
  # other resources' validation (e.g. policy_arn, role, lambda_invoke_arn).
  mock_resource "aws_iam_role" {
    defaults = {
      arn = "arn:aws:iam::123456789012:role/mock-role"
    }
  }

  mock_resource "aws_iam_policy" {
    defaults = {
      arn = "arn:aws:iam::123456789012:policy/mock-policy"
    }
  }

  mock_resource "aws_dynamodb_table" {
    defaults = {
      arn = "arn:aws:dynamodb:us-east-1:123456789012:table/mock-table"
    }
  }

  mock_resource "aws_lambda_function" {
    defaults = {
      arn        = "arn:aws:lambda:us-east-1:123456789012:function:mock-fn"
      invoke_arn = "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:mock-fn/invocations"
    }
  }

  mock_resource "aws_api_gateway_rest_api" {
    defaults = {
      id               = "abc123def4"
      root_resource_id = "rootid"
    }
  }

  mock_resource "aws_sns_topic" {
    defaults = {
      arn = "arn:aws:sns:us-east-1:123456789012:mock-topic"
    }
  }
}

mock_provider "archive" {}

# ---------------------------------------------------------------------------
# Default configuration: Bedrock disabled
# ---------------------------------------------------------------------------

run "data_module_creates_both_tables" {
  command = apply

  assert {
    condition     = module.data.audit_table_name != "" && module.data.events_table_name != ""
    error_message = "Both audit and events tables must be created"
  }
}

run "iam_policy_actions_have_no_wildcards" {
  command = apply

  assert {
    condition     = alltrue([for a in module.iam.policy_actions : !can(regex("\\*", a))])
    error_message = "IAM policy actions must not contain '*' (Action wildcard)"
  }
}

run "iam_policy_resources_have_no_wildcards" {
  command = apply

  assert {
    condition     = alltrue([for r in module.iam.policy_resources : !can(regex("\\*", r))])
    error_message = "IAM policy resources must not contain '*' (Resource or ARN wildcard)"
  }
}

run "iam_policy_excludes_bedrock_when_disabled" {
  command = apply

  variables {
    enable_bedrock_summary = false
  }

  assert {
    condition     = !contains(module.iam.policy_actions, "bedrock:InvokeModel")
    error_message = "Bedrock permission must not appear when enable_bedrock_summary is false"
  }
}

run "lambda_module_outputs_function_name" {
  command = apply

  assert {
    condition     = module.lambda.function_name != ""
    error_message = "Lambda function name must be set"
  }
}

run "observability_resources_present" {
  command = apply

  assert {
    condition     = module.observability.sns_topic_arn != ""
    error_message = "SNS topic must be created for alarm notifications"
  }

  assert {
    condition     = module.observability.dashboard_name != ""
    error_message = "CloudWatch dashboard must be created"
  }

  assert {
    condition     = module.observability.alarm_name != ""
    error_message = "CloudWatch alarm must be created"
  }
}

run "api_endpoints_present" {
  command = apply

  assert {
    condition     = module.api.audit_endpoint != "" && module.api.summary_endpoint != "" && module.api.summarize_endpoint != ""
    error_message = "All three API endpoints must be exposed (audit, summary, summarize)"
  }
}

run "api_lambda_permissions_scoped_to_exact_paths" {
  command = apply

  assert {
    condition     = length([for arn in module.api.lambda_permission_source_arns : arn if can(regex("/POST/audit$", arn))]) == 1
    error_message = "Lambda permission for POST /audit must be scoped to exact stage/method/path"
  }

  assert {
    condition     = length([for arn in module.api.lambda_permission_source_arns : arn if can(regex("/GET/summary$", arn))]) == 1
    error_message = "Lambda permission for GET /summary must be scoped to exact stage/method/path"
  }

  assert {
    condition     = length([for arn in module.api.lambda_permission_source_arns : arn if can(regex("/POST/summarize$", arn))]) == 1
    error_message = "Lambda permission for POST /summarize must be scoped to exact stage/method/path"
  }

  assert {
    condition     = alltrue([for arn in module.api.lambda_permission_source_arns : !can(regex("\\*", arn))])
    error_message = "API Gateway Lambda permission source ARNs must not contain wildcards"
  }
}

# ---------------------------------------------------------------------------
# Bedrock-enabled configuration
# ---------------------------------------------------------------------------

run "bedrock_enabled_grants_invoke_model_only" {
  command = apply

  variables {
    enable_bedrock_summary = true
    bedrock_model_arn      = "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0"
  }

  assert {
    condition     = contains(module.iam.policy_actions, "bedrock:InvokeModel")
    error_message = "bedrock:InvokeModel must be granted when enable_bedrock_summary is true"
  }

  assert {
    condition     = contains(module.iam.policy_resources, "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0")
    error_message = "Bedrock permission must be scoped to the exact configured model ARN"
  }

  assert {
    condition     = alltrue([for a in module.iam.policy_actions : !can(regex("\\*", a))])
    error_message = "IAM policy actions must not contain '*' even when Bedrock is enabled"
  }

  assert {
    condition     = alltrue([for r in module.iam.policy_resources : !can(regex("\\*", r))])
    error_message = "IAM policy resources must not contain '*' even when Bedrock is enabled"
  }
}
