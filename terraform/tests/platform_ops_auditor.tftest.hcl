# Platform Ops Auditor — Terraform tests
#
# These tests use Terraform's built-in test framework (terraform test).
# They apply the configuration using a mock provider so no real AWS resources
# are created. The assertions validate critical design decisions including
# strict no-wildcard IAM, DynamoDB configuration, Lambda runtime, and
# CloudWatch alarm settings.

mock_provider "aws" {}
mock_provider "archive" {}

run "dynamodb_audit_table_configuration" {
  command = plan

  assert {
    condition     = aws_dynamodb_table.audit.billing_mode == "PAY_PER_REQUEST"
    error_message = "Audit table billing mode must be PAY_PER_REQUEST"
  }

  assert {
    condition     = aws_dynamodb_table.audit.server_side_encryption[0].enabled == true
    error_message = "Audit table must have server-side encryption enabled"
  }

  assert {
    condition     = aws_dynamodb_table.audit.point_in_time_recovery[0].enabled == true
    error_message = "Audit table must have point-in-time recovery enabled"
  }
}

run "dynamodb_events_table_configuration" {
  command = plan

  assert {
    condition     = aws_dynamodb_table.events.billing_mode == "PAY_PER_REQUEST"
    error_message = "Events table billing mode must be PAY_PER_REQUEST"
  }

  assert {
    condition     = aws_dynamodb_table.events.server_side_encryption[0].enabled == true
    error_message = "Events table must have server-side encryption enabled"
  }

  assert {
    condition     = aws_dynamodb_table.events.point_in_time_recovery[0].enabled == true
    error_message = "Events table must have point-in-time recovery enabled"
  }
}

run "lambda_function_configuration" {
  command = plan

  assert {
    condition     = aws_lambda_function.app.runtime == "python3.12"
    error_message = "Lambda runtime must be python3.12"
  }

  assert {
    condition     = aws_lambda_function.app.timeout <= 10
    error_message = "Lambda timeout must be <= 10 seconds"
  }
}

run "cloudwatch_alarm_configuration" {
  command = plan

  assert {
    condition     = aws_cloudwatch_metric_alarm.lambda_errors.metric_name == "Errors"
    error_message = "CloudWatch alarm metric must be Errors"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.lambda_errors.threshold == 1
    error_message = "CloudWatch alarm threshold must be 1"
  }
}

run "cloudwatch_dashboard_exists" {
  command = plan

  assert {
    condition     = aws_cloudwatch_dashboard.main.dashboard_name != ""
    error_message = "CloudWatch dashboard must have a non-empty name"
  }
}

run "lambda_permission_post_audit_scoped" {
  command = plan

  assert {
    condition     = can(regex("/POST/audit$", aws_lambda_permission.post_audit.source_arn))
    error_message = "Lambda permission for POST /audit must be scoped to exact stage/method/path"
  }
}

run "lambda_permission_get_summary_scoped" {
  command = plan

  assert {
    condition     = can(regex("/GET/summary$", aws_lambda_permission.get_summary.source_arn))
    error_message = "Lambda permission for GET /summary must be scoped to exact stage/method/path"
  }
}

run "iam_policy_no_wildcards" {
  command = plan

  assert {
    condition     = !can(regex("\"Action\":\\s*\"\\*\"", data.aws_iam_policy_document.lambda_policy.json))
    error_message = "IAM policy must not contain Action: *"
  }

  assert {
    condition     = !can(regex("\"Resource\":\\s*\"\\*\"", data.aws_iam_policy_document.lambda_policy.json))
    error_message = "IAM policy must not contain Resource: *"
  }

  assert {
    condition     = !can(regex("arn:aws:[^\"]*:\\*:[^\"]*", data.aws_iam_policy_document.lambda_policy.json))
    error_message = "IAM policy must not contain ARN wildcards"
  }
}
