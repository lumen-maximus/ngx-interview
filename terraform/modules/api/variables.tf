variable "name_prefix" {
  description = "Prefix used to name API Gateway resources"
  type        = string
}

variable "stage_name" {
  description = "API Gateway stage name"
  type        = string
}

variable "aws_region" {
  description = "AWS region (used to build exact source ARNs for Lambda permissions)"
  type        = string
}

variable "account_id" {
  description = "AWS account ID (used to build exact source ARNs for Lambda permissions)"
  type        = string
}

variable "lambda_function_name" {
  description = "Lambda function name to grant API Gateway invoke permission to"
  type        = string
}

variable "lambda_invoke_arn" {
  description = "Lambda invoke ARN for AWS_PROXY integrations"
  type        = string
}

variable "tags" {
  description = "Tags applied to API Gateway resources"
  type        = map(string)
  default     = {}
}
