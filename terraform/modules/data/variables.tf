variable "name_prefix" {
  description = "Prefix used to name DynamoDB tables"
  type        = string
}

variable "tags" {
  description = "Tags applied to DynamoDB tables"
  type        = map(string)
  default     = {}
}
