resource "aws_sns_topic" "alarms" {
  name = "${var.name_prefix}-alarms"
  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_actions       = [aws_sns_topic.alarms.arn]
  alarm_description   = "Lambda function error count >= 1"
  alarm_name          = "${var.name_prefix}-lambda-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  tags                = var.tags
  threshold           = 1
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.lambda_function_name
  }
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", var.lambda_function_name],
            ["AWS/Lambda", "Errors", "FunctionName", var.lambda_function_name],
            ["AWS/Lambda", "Duration", "FunctionName", var.lambda_function_name],
            ["AWS/Lambda", "Throttles", "FunctionName", var.lambda_function_name],
          ]
          period  = 60
          region  = var.aws_region
          stat    = "Sum"
          title  = "Platform Ops Auditor — Lambda Metrics"
          view   = "timeSeries"
        }
      }
    ]
  })
  dashboard_name = "${var.name_prefix}-dashboard"
}
