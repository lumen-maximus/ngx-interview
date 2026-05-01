locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# ---------------------------------------------------------------------------
# DynamoDB — Audit Records
# ---------------------------------------------------------------------------

resource "aws_dynamodb_table" "audit" {
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "audit_id"
  name         = "${local.name_prefix}-audits"

  attribute {
    name = "audit_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}

# ---------------------------------------------------------------------------
# DynamoDB — Operational Events
# ---------------------------------------------------------------------------

resource "aws_dynamodb_table" "events" {
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "event_id"
  name         = "${local.name_prefix}-events"

  attribute {
    name = "event_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}

# ---------------------------------------------------------------------------
# Lambda — Package
# ---------------------------------------------------------------------------

data "archive_file" "lambda" {
  output_path = "${path.module}/lambda.zip"
  source_dir  = "${path.module}/../app"
  type        = "zip"

  excludes = ["test_handler.py", "__pycache__", "*.pyc"]
}

# ---------------------------------------------------------------------------
# Lambda — IAM Role
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"

    principals {
      identifiers = ["lambda.amazonaws.com"]
      type        = "Service"
    }
  }
}

resource "aws_iam_role" "lambda" {
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  name               = "${local.name_prefix}-lambda-role"
}

data "aws_iam_policy_document" "lambda_policy" {
  statement {
    actions   = ["dynamodb:PutItem"]
    effect    = "Allow"
    resources = [aws_dynamodb_table.audit.arn, aws_dynamodb_table.events.arn]
    sid       = "DynamoDBWrite"
  }

  statement {
    actions   = ["dynamodb:Scan"]
    effect    = "Allow"
    resources = [aws_dynamodb_table.audit.arn]
    sid       = "DynamoDBScan"
  }
}

resource "aws_iam_policy" "lambda" {
  name   = "${local.name_prefix}-lambda-policy"
  policy = data.aws_iam_policy_document.lambda_policy.json
}

resource "aws_iam_role_policy_attachment" "lambda" {
  policy_arn = aws_iam_policy.lambda.arn
  role       = aws_iam_role.lambda.name
}

# ---------------------------------------------------------------------------
# Lambda — Function
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "app" {
  filename         = data.archive_file.lambda.output_path
  function_name    = "${local.name_prefix}-handler"
  handler          = "handler.handler"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = 10

  environment {
    variables = {
      AUDIT_TABLE  = aws_dynamodb_table.audit.name
      EVENTS_TABLE = aws_dynamodb_table.events.name
    }
  }
}

# ---------------------------------------------------------------------------
# API Gateway — REST API
# ---------------------------------------------------------------------------

resource "aws_api_gateway_rest_api" "api" {
  description = "Platform Ops Auditor REST API"
  name        = "${local.name_prefix}-api"
}

# /audit resource
resource "aws_api_gateway_resource" "audit" {
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "audit"
  rest_api_id = aws_api_gateway_rest_api.api.id
}

# /summary resource
resource "aws_api_gateway_resource" "summary" {
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "summary"
  rest_api_id = aws_api_gateway_rest_api.api.id
}

# POST /audit method
resource "aws_api_gateway_method" "post_audit" {
  authorization = "NONE"
  http_method   = "POST"
  resource_id   = aws_api_gateway_resource.audit.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
}

# GET /summary method
resource "aws_api_gateway_method" "get_summary" {
  authorization = "NONE"
  http_method   = "GET"
  resource_id   = aws_api_gateway_resource.summary.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
}

# POST /audit integration
resource "aws_api_gateway_integration" "post_audit" {
  http_method             = aws_api_gateway_method.post_audit.http_method
  integration_http_method = "POST"
  resource_id             = aws_api_gateway_resource.audit.id
  rest_api_id             = aws_api_gateway_rest_api.api.id
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.app.invoke_arn
}

# GET /summary integration
resource "aws_api_gateway_integration" "get_summary" {
  http_method             = aws_api_gateway_method.get_summary.http_method
  integration_http_method = "POST"
  resource_id             = aws_api_gateway_resource.summary.id
  rest_api_id             = aws_api_gateway_rest_api.api.id
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.app.invoke_arn
}

# Deployment — depends on both integrations being complete
resource "aws_api_gateway_deployment" "api" {
  rest_api_id = aws_api_gateway_rest_api.api.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.audit.id,
      aws_api_gateway_resource.summary.id,
      aws_api_gateway_method.post_audit.id,
      aws_api_gateway_method.get_summary.id,
      aws_api_gateway_integration.post_audit.id,
      aws_api_gateway_integration.get_summary.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.post_audit,
    aws_api_gateway_integration.get_summary,
  ]
}

resource "aws_api_gateway_stage" "api" {
  deployment_id = aws_api_gateway_deployment.api.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
  stage_name    = var.environment
}

# ---------------------------------------------------------------------------
# Lambda permissions — scoped to exact stage/method/path ARNs
# ---------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

resource "aws_lambda_permission" "post_audit" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.app.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "arn:aws:execute-api:${var.aws_region}:${data.aws_caller_identity.current.account_id}:${aws_api_gateway_rest_api.api.id}/${var.environment}/POST/audit"
  statement_id  = "AllowPostAudit"
}

resource "aws_lambda_permission" "get_summary" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.app.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "arn:aws:execute-api:${var.aws_region}:${data.aws_caller_identity.current.account_id}:${aws_api_gateway_rest_api.api.id}/${var.environment}/GET/summary"
  statement_id  = "AllowGetSummary"
}

# ---------------------------------------------------------------------------
# SNS — Alarm Topic
# ---------------------------------------------------------------------------

resource "aws_sns_topic" "alarms" {
  name = "${local.name_prefix}-alarms"
}

# ---------------------------------------------------------------------------
# CloudWatch — Lambda Errors Alarm
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_actions       = [aws_sns_topic.alarms.arn]
  alarm_description   = "Lambda function error rate >= 1"
  alarm_name          = "${local.name_prefix}-lambda-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.app.function_name
  }
}

# ---------------------------------------------------------------------------
# CloudWatch — Dashboard
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.app.function_name],
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.app.function_name],
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.app.function_name],
            ["AWS/Lambda", "Throttles", "FunctionName", aws_lambda_function.app.function_name],
          ]
          period = 60
          stat   = "Sum"
          title  = "Platform Ops Auditor — Lambda Metrics"
          view   = "timeSeries"
        }
      }
    ]
  })
  dashboard_name = "${local.name_prefix}-dashboard"
}
