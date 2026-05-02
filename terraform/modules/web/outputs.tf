output "bucket_name" {
  description = "S3 bucket name for web assets"
  value       = aws_s3_bucket.web.id
}

output "cloudfront_url" {
  description = "HTTPS URL of the CloudFront distribution"
  value       = "https://${aws_cloudfront_distribution.web.domain_name}"
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (used for cache invalidation)"
  value       = aws_cloudfront_distribution.web.id
}
