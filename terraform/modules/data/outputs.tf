output "audit_table_name" {
  description = "Audit records table name"
  value       = aws_dynamodb_table.audit.name
}

output "audit_table_arn" {
  description = "Audit records table ARN"
  value       = aws_dynamodb_table.audit.arn
}

output "events_table_name" {
  description = "Operational events table name"
  value       = aws_dynamodb_table.events.name
}

output "events_table_arn" {
  description = "Operational events table ARN"
  value       = aws_dynamodb_table.events.arn
}
