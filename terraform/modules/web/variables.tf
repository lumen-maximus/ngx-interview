variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "account_id" {
  description = "AWS account ID — used to make the S3 bucket name globally unique"
  type        = string
}

variable "use_cloudfront" {
  description = "Set to false to use S3 static website hosting instead of CloudFront (use on new AWS accounts where CloudFront is not yet verified)"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
