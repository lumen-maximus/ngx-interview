variable "name_prefix" {
  description = "Prefix used to name observability resources"
  type        = string
}

variable "lambda_function_name" {
  description = "Lambda function name to monitor"
  type        = string
}

variable "aws_region" {
  description = "AWS region for CloudWatch dashboard widgets"
  type        = string
}

variable "tags" {
  description = "Tags applied to observability resources"
  type        = map(string)
  default     = {}
}
