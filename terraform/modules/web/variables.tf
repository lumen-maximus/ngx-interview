variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "account_id" {
  description = "AWS account ID — used to make the S3 bucket name globally unique"
  type        = string
}

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
