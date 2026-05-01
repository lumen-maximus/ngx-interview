output "api_base_url" {
  description = "Base invoke URL of the deployed REST API stage"
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

output "summarize_endpoint" {
  description = "POST /summarize endpoint URL (returns 501 when Bedrock is disabled)"
  value       = "${aws_api_gateway_stage.api.invoke_url}/summarize"
}

output "rest_api_id" {
  description = "REST API ID"
  value       = aws_api_gateway_rest_api.api.id
}

output "lambda_permission_source_arns" {
  description = "List of source ARNs granted to API Gateway for invoking Lambda (used by tests)"
  value = [
    aws_lambda_permission.post_audit.source_arn,
    aws_lambda_permission.get_summary.source_arn,
    aws_lambda_permission.post_summarize.source_arn,
  ]
}
