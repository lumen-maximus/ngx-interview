data "archive_file" "lambda" {
  output_path = "${path.module}/lambda.zip"
  source_dir  = "${path.module}/../../../app"
  type        = "zip"

  excludes = ["test_handler.py", "__pycache__", "*.pyc"]
}

resource "aws_lambda_function" "app" {
  filename         = data.archive_file.lambda.output_path
  function_name    = "${var.name_prefix}-handler"
  handler          = "handler.handler"
  memory_size      = var.memory_size
  role             = var.role_arn
  runtime          = "python3.12"
  source_code_hash = data.archive_file.lambda.output_base64sha256
  tags             = var.tags
  timeout          = var.timeout

  environment {
    variables = {
      AUDIT_TABLE_NAME       = var.audit_table_name
      EVENTS_TABLE_NAME      = var.events_table_name
      ENABLE_BEDROCK_SUMMARY = tostring(var.enable_bedrock_summary)
      BEDROCK_MODEL_ID       = var.bedrock_model_id
    }
  }
}
