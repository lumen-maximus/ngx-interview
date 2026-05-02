resource "aws_api_gateway_rest_api" "api" {
  description = "Platform Ops Auditor REST API"
  name        = "${var.name_prefix}-api"
  tags        = var.tags
}

# ---------------------------------------------------------------------------
# /audit
# ---------------------------------------------------------------------------

resource "aws_api_gateway_resource" "audit" {
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "audit"
  rest_api_id = aws_api_gateway_rest_api.api.id
}

resource "aws_api_gateway_method" "post_audit" {
  authorization = "NONE"
  http_method   = "POST"
  resource_id   = aws_api_gateway_resource.audit.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
}

resource "aws_api_gateway_integration" "post_audit" {
  http_method             = aws_api_gateway_method.post_audit.http_method
  integration_http_method = "POST"
  resource_id             = aws_api_gateway_resource.audit.id
  rest_api_id             = aws_api_gateway_rest_api.api.id
  type                    = "AWS_PROXY"
  uri                     = var.lambda_invoke_arn
}

# CORS preflight for /audit
resource "aws_api_gateway_method" "options_audit" {
  authorization = "NONE"
  http_method   = "OPTIONS"
  resource_id   = aws_api_gateway_resource.audit.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
}

resource "aws_api_gateway_integration" "options_audit" {
  http_method = aws_api_gateway_method.options_audit.http_method
  resource_id = aws_api_gateway_resource.audit.id
  rest_api_id = aws_api_gateway_rest_api.api.id
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_audit" {
  http_method = aws_api_gateway_method.options_audit.http_method
  resource_id = aws_api_gateway_resource.audit.id
  rest_api_id = aws_api_gateway_rest_api.api.id
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_audit" {
  http_method = aws_api_gateway_method.options_audit.http_method
  resource_id = aws_api_gateway_resource.audit.id
  rest_api_id = aws_api_gateway_rest_api.api.id
  status_code = aws_api_gateway_method_response.options_audit.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
  depends_on = [aws_api_gateway_integration.options_audit]
}

# ---------------------------------------------------------------------------
# /summary
# ---------------------------------------------------------------------------

resource "aws_api_gateway_resource" "summary" {
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "summary"
  rest_api_id = aws_api_gateway_rest_api.api.id
}

resource "aws_api_gateway_method" "get_summary" {
  authorization = "NONE"
  http_method   = "GET"
  resource_id   = aws_api_gateway_resource.summary.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
}

resource "aws_api_gateway_integration" "get_summary" {
  http_method             = aws_api_gateway_method.get_summary.http_method
  integration_http_method = "POST"
  resource_id             = aws_api_gateway_resource.summary.id
  rest_api_id             = aws_api_gateway_rest_api.api.id
  type                    = "AWS_PROXY"
  uri                     = var.lambda_invoke_arn
}

# CORS preflight for /summary
resource "aws_api_gateway_method" "options_summary" {
  authorization = "NONE"
  http_method   = "OPTIONS"
  resource_id   = aws_api_gateway_resource.summary.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
}

resource "aws_api_gateway_integration" "options_summary" {
  http_method = aws_api_gateway_method.options_summary.http_method
  resource_id = aws_api_gateway_resource.summary.id
  rest_api_id = aws_api_gateway_rest_api.api.id
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_summary" {
  http_method = aws_api_gateway_method.options_summary.http_method
  resource_id = aws_api_gateway_resource.summary.id
  rest_api_id = aws_api_gateway_rest_api.api.id
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_summary" {
  http_method = aws_api_gateway_method.options_summary.http_method
  resource_id = aws_api_gateway_resource.summary.id
  rest_api_id = aws_api_gateway_rest_api.api.id
  status_code = aws_api_gateway_method_response.options_summary.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,GET'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
  depends_on = [aws_api_gateway_integration.options_summary]
}

# ---------------------------------------------------------------------------
# /summarize (always created so the API contract is stable; Lambda returns 501
# when ENABLE_BEDROCK_SUMMARY is false)
# ---------------------------------------------------------------------------

resource "aws_api_gateway_resource" "summarize" {
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "summarize"
  rest_api_id = aws_api_gateway_rest_api.api.id
}

resource "aws_api_gateway_method" "post_summarize" {
  authorization = "NONE"
  http_method   = "POST"
  resource_id   = aws_api_gateway_resource.summarize.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
}

resource "aws_api_gateway_integration" "post_summarize" {
  http_method             = aws_api_gateway_method.post_summarize.http_method
  integration_http_method = "POST"
  resource_id             = aws_api_gateway_resource.summarize.id
  rest_api_id             = aws_api_gateway_rest_api.api.id
  type                    = "AWS_PROXY"
  uri                     = var.lambda_invoke_arn
}

# CORS preflight for /summarize
resource "aws_api_gateway_method" "options_summarize" {
  authorization = "NONE"
  http_method   = "OPTIONS"
  resource_id   = aws_api_gateway_resource.summarize.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
}

resource "aws_api_gateway_integration" "options_summarize" {
  http_method = aws_api_gateway_method.options_summarize.http_method
  resource_id = aws_api_gateway_resource.summarize.id
  rest_api_id = aws_api_gateway_rest_api.api.id
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_summarize" {
  http_method = aws_api_gateway_method.options_summarize.http_method
  resource_id = aws_api_gateway_resource.summarize.id
  rest_api_id = aws_api_gateway_rest_api.api.id
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_summarize" {
  http_method = aws_api_gateway_method.options_summarize.http_method
  resource_id = aws_api_gateway_resource.summarize.id
  rest_api_id = aws_api_gateway_rest_api.api.id
  status_code = aws_api_gateway_method_response.options_summarize.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
  depends_on = [aws_api_gateway_integration.options_summarize]
}

# ---------------------------------------------------------------------------
# Deployment + Stage
# ---------------------------------------------------------------------------

resource "aws_api_gateway_deployment" "api" {
  rest_api_id = aws_api_gateway_rest_api.api.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.audit.id,
      aws_api_gateway_resource.summary.id,
      aws_api_gateway_resource.summarize.id,
      aws_api_gateway_method.post_audit.id,
      aws_api_gateway_method.get_summary.id,
      aws_api_gateway_method.post_summarize.id,
      aws_api_gateway_method.options_audit.id,
      aws_api_gateway_method.options_summary.id,
      aws_api_gateway_method.options_summarize.id,
      aws_api_gateway_integration.post_audit.id,
      aws_api_gateway_integration.get_summary.id,
      aws_api_gateway_integration.post_summarize.id,
      aws_api_gateway_integration.options_audit.id,
      aws_api_gateway_integration.options_summary.id,
      aws_api_gateway_integration.options_summarize.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.post_audit,
    aws_api_gateway_integration.get_summary,
    aws_api_gateway_integration.post_summarize,
    aws_api_gateway_integration_response.options_audit,
    aws_api_gateway_integration_response.options_summary,
    aws_api_gateway_integration_response.options_summarize,
  ]
}

resource "aws_api_gateway_stage" "api" {
  deployment_id = aws_api_gateway_deployment.api.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
  stage_name    = var.stage_name
  tags          = var.tags
}

# ---------------------------------------------------------------------------
# Lambda permissions — exact stage/method/path ARNs (no wildcards)
# ---------------------------------------------------------------------------

locals {
  source_arn_prefix = "arn:aws:execute-api:${var.aws_region}:${var.account_id}:${aws_api_gateway_rest_api.api.id}"
}

resource "aws_lambda_permission" "post_audit" {
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${local.source_arn_prefix}/${var.stage_name}/POST/audit"
  statement_id  = "AllowPostAudit"
}

resource "aws_lambda_permission" "get_summary" {
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${local.source_arn_prefix}/${var.stage_name}/GET/summary"
  statement_id  = "AllowGetSummary"
}

resource "aws_lambda_permission" "post_summarize" {
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${local.source_arn_prefix}/${var.stage_name}/POST/summarize"
  statement_id  = "AllowPostSummarize"
}
