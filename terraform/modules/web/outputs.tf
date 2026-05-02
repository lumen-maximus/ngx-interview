output "bucket_name" {
  description = "S3 bucket name for web assets"
  value       = aws_s3_bucket.web.id
}

output "cloudfront_url" {
  description = "HTTPS URL of the CloudFront distribution (empty when use_cloudfront = false)"
  value       = length(aws_cloudfront_distribution.web) > 0 ? "https://${aws_cloudfront_distribution.web[0].domain_name}" : ""
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (empty when use_cloudfront = false)"
  value       = length(aws_cloudfront_distribution.web) > 0 ? aws_cloudfront_distribution.web[0].id : ""
}

output "website_url" {
  description = "S3 static website URL (non-empty only when use_cloudfront = false)"
  value       = length(aws_s3_bucket_website_configuration.web) > 0 ? "http://${aws_s3_bucket_website_configuration.web[0].website_endpoint}" : ""
}

output "console_url" {
  description = "Preferred console URL — CloudFront if available, S3 website otherwise"
  value       = length(aws_cloudfront_distribution.web) > 0 ? "https://${aws_cloudfront_distribution.web[0].domain_name}" : (length(aws_s3_bucket_website_configuration.web) > 0 ? "http://${aws_s3_bucket_website_configuration.web[0].website_endpoint}" : "")
}
