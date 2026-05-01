resource "aws_dynamodb_table" "audit" {
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "audit_id"
  name         = "${var.name_prefix}-audits"
  tags         = var.tags

  attribute {
    name = "audit_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}

resource "aws_dynamodb_table" "events" {
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "event_id"
  name         = "${var.name_prefix}-events"
  tags         = var.tags

  attribute {
    name = "event_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}
