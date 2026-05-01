output "api_base_url" {
  description = "Base URL of the deployed REST API"
  value       = module.api.api_base_url
}

output "audit_endpoint" {
  description = "POST /audit endpoint URL"
  value       = module.api.audit_endpoint
}

output "summary_endpoint" {
  description = "GET /summary endpoint URL"
  value       = module.api.summary_endpoint
}

output "summarize_endpoint" {
  description = "POST /summarize endpoint URL (returns 501 when Bedrock is disabled)"
  value       = module.api.summarize_endpoint
}

output "audit_table_name" {
  description = "DynamoDB audit records table name"
  value       = module.data.audit_table_name
}

output "operational_events_table_name" {
  description = "DynamoDB operational events table name"
  value       = module.data.events_table_name
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = module.lambda.function_name
}

output "sns_topic_arn" {
  description = "SNS topic ARN for Lambda alarms"
  value       = module.observability.sns_topic_arn
}

output "dashboard_name" {
  description = "CloudWatch dashboard name"
  value       = module.observability.dashboard_name
}
