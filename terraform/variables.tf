variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used as a prefix for resource naming"
  type        = string
  default     = "platform-ops-auditor"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "enable_bedrock_summary" {
  description = "Enable the optional POST /summarize endpoint backed by Amazon Bedrock"
  type        = bool
  default     = false
}

variable "bedrock_model_id" {
  description = "Bedrock model ID used by POST /summarize when enabled"
  type        = string
  default     = "amazon.nova-lite-v1:0"
}

variable "bedrock_stub" {
  description = "Return a canned stub response instead of calling Bedrock (for accounts pending access)"
  type        = bool
  default     = false
}

variable "bedrock_model_arn" {
  description = "Exact Bedrock foundation model ARN granted to Lambda when enable_bedrock_summary is true"
  type        = string
  default     = "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0"
}

variable "enable_static_console" {
  description = "Deploy the optional S3 + CloudFront static developer console"
  type        = bool
  default     = false
}
