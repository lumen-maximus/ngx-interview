variable "name_prefix" {
  description = "Prefix used to name the Lambda function"
  type        = string
}

variable "role_arn" {
  description = "ARN of the Lambda execution role"
  type        = string
}

variable "audit_table_name" {
  description = "Name of the audit records DynamoDB table"
  type        = string
}

variable "events_table_name" {
  description = "Name of the operational events DynamoDB table"
  type        = string
}

variable "enable_bedrock_summary" {
  description = "Whether the optional Bedrock summarize endpoint is enabled"
  type        = bool
  default     = false
}

variable "bedrock_model_id" {
  description = "Bedrock model ID used by POST /summarize when enabled"
  type        = string
  default     = "amazon.nova-lite-v1:0"
}

variable "timeout" {
  description = "Lambda timeout in seconds (must be <= 10)"
  type        = number
  default     = 10

  validation {
    condition     = var.timeout > 0 && var.timeout <= 10
    error_message = "Lambda timeout must be between 1 and 10 seconds."
  }
}

variable "memory_size" {
  description = "Lambda memory size in MB"
  type        = number
  default     = 256
}

variable "tags" {
  description = "Tags applied to the Lambda function"
  type        = map(string)
  default     = {}
}
