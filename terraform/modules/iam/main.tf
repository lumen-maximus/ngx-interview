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
  name               = "${var.name_prefix}-lambda-role"
  tags               = var.tags
}

data "aws_iam_policy_document" "lambda_policy" {
  statement {
    actions   = ["dynamodb:PutItem"]
    effect    = "Allow"
    resources = [var.audit_table_arn, var.events_table_arn]
    sid       = "DynamoDBWrite"
  }

  statement {
    actions   = ["dynamodb:Scan"]
    effect    = "Allow"
    resources = [var.audit_table_arn, var.events_table_arn]
    sid       = "DynamoDBScan"
  }

  dynamic "statement" {
    for_each = var.enable_bedrock_summary ? [1] : []
    content {
      actions   = ["bedrock:Converse", "bedrock:InvokeModel"]
      effect    = "Allow"
      resources = [var.bedrock_model_arn]
      sid       = "BedrockInvokeModel"
    }
  }
}

# Structured representation of the policy used both by the resource above and
# by Terraform tests to verify no-wildcard intent without depending on the
# rendered JSON (which is opaque under mock providers).
locals {
  policy_resources = concat(
    [var.audit_table_arn, var.events_table_arn],
    var.enable_bedrock_summary ? [var.bedrock_model_arn] : []
  )

  policy_actions = concat(
    ["dynamodb:PutItem", "dynamodb:Scan"],
    var.enable_bedrock_summary ? ["bedrock:Converse", "bedrock:InvokeModel"] : []
  )
}

resource "aws_iam_policy" "lambda" {
  name   = "${var.name_prefix}-lambda-policy"
  policy = data.aws_iam_policy_document.lambda_policy.json
  tags   = var.tags
}

resource "aws_iam_role_policy_attachment" "lambda" {
  policy_arn = aws_iam_policy.lambda.arn
  role       = aws_iam_role.lambda.name
}
