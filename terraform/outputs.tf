output "api_base_url" {
  description = "Base URL of the deployed REST API"
  value       = aws_api_gateway_stage.api.invoke_url
}

output "audit_endpoint" {
  description = "POST /audit endpoint URL"
  value       = "${aws_api_gateway_stage.api.invoke_url}/audit"
}

output "summary_endpoint" {
  description = "GET /summary endpoint URL"
  value       = "${aws_api_gateway_stage.api.invoke_url}/summary"
}

output "audit_table_name" {
  description = "DynamoDB audit records table name"
  value       = aws_dynamodb_table.audit.name
}

output "operational_events_table_name" {
  description = "DynamoDB operational events table name"
  value       = aws_dynamodb_table.events.name
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.app.function_name
}

output "sns_topic_arn" {
  description = "SNS topic ARN for Lambda alarms"
  value       = aws_sns_topic.alarms.arn
}

output "dashboard_name" {
  description = "CloudWatch dashboard name"
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}
