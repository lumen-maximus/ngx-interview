output "role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda.arn
}

output "role_name" {
  description = "Name of the Lambda execution role"
  value       = aws_iam_role.lambda.name
}

output "policy_json" {
  description = "Rendered Lambda IAM policy JSON"
  value       = data.aws_iam_policy_document.lambda_policy.json
}

output "policy_resources" {
  description = "All resource ARNs granted in the Lambda policy (used by tests to assert no wildcards)"
  value       = local.policy_resources
}

output "policy_actions" {
  description = "All actions granted in the Lambda policy (used by tests to assert no wildcards)"
  value       = local.policy_actions
}
