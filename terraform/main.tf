data "aws_caller_identity" "current" {}

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

module "data" {
  source = "./modules/data"

  name_prefix = local.name_prefix
  tags        = local.tags
}

module "iam" {
  source = "./modules/iam"

  audit_table_arn        = module.data.audit_table_arn
  bedrock_model_arn      = var.bedrock_model_arn
  enable_bedrock_summary = var.enable_bedrock_summary
  events_table_arn       = module.data.events_table_arn
  name_prefix            = local.name_prefix
  tags                   = local.tags
}

module "lambda" {
  source = "./modules/lambda"

  audit_table_name       = module.data.audit_table_name
  bedrock_model_id       = var.bedrock_model_id
  enable_bedrock_summary = var.enable_bedrock_summary
  events_table_name      = module.data.events_table_name
  name_prefix            = local.name_prefix
  role_arn               = module.iam.role_arn
  tags                   = local.tags
}

module "api" {
  source = "./modules/api"

  account_id           = data.aws_caller_identity.current.account_id
  aws_region           = var.aws_region
  lambda_function_name = module.lambda.function_name
  lambda_invoke_arn    = module.lambda.invoke_arn
  name_prefix          = local.name_prefix
  stage_name           = var.environment
  tags                 = local.tags
}

module "observability" {
  source = "./modules/observability"

  aws_region           = var.aws_region
  lambda_function_name = module.lambda.function_name
  name_prefix          = local.name_prefix
  tags                 = local.tags
}
