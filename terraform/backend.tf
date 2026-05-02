terraform {
  backend "s3" {
    bucket         = "ngx-interview-tfstate-830146370919"
    key            = "ngx-interview/platform-ops-auditor.tfstate"
    region         = "us-east-1"
    dynamodb_table = "ngx-interview-tflock"
    encrypt        = true
  }
}
