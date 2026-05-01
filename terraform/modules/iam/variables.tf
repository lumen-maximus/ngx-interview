variable "name_prefix" {
  description = "Prefix used to name IAM resources"
  type        = string
}

variable "audit_table_arn" {
  description = "Exact ARN of the audit records DynamoDB table"
  type        = string
}

variable "events_table_arn" {
  description = "Exact ARN of the operational events DynamoDB table"
  type        = string
}

variable "enable_bedrock_summary" {
  description = "Whether to grant Lambda bedrock:InvokeModel on the configured model ARN"
  type        = bool
  default     = false
}

variable "bedrock_model_arn" {
  description = "Exact Bedrock foundation model ARN to grant bedrock:InvokeModel against"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags applied to IAM resources"
  type        = map(string)
  default     = {}
}
