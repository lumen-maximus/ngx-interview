output "function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.app.function_name
}

output "function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.app.arn
}

output "invoke_arn" {
  description = "Lambda invoke ARN used by API Gateway integrations"
  value       = aws_lambda_function.app.invoke_arn
}
