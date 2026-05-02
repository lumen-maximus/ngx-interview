# S3 bucket for static web assets
# When use_cloudfront = true:  private bucket, served only through CloudFront OAC
# When use_cloudfront = false: static website hosting enabled, public read policy
resource "aws_s3_bucket" "web" {
  bucket = "${var.name_prefix}-web-${var.account_id}"
  tags   = var.tags
}

# Block all public access when using CloudFront (OAC handles access)
resource "aws_s3_bucket_public_access_block" "web_private" {
  count  = var.use_cloudfront ? 1 : 0
  bucket = aws_s3_bucket.web.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Allow public access when using S3 static website hosting (required for public read)
resource "aws_s3_bucket_public_access_block" "web_public" {
  count  = var.use_cloudfront ? 0 : 1
  bucket = aws_s3_bucket.web.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_server_side_encryption_configuration" "web" {
  bucket = aws_s3_bucket.web.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "web" {
  bucket = aws_s3_bucket.web.id
  versioning_configuration {
    status = "Enabled"
  }
}

# ── CloudFront path (use_cloudfront = true) ────────────────────────────────────

# Origin Access Control — allows CloudFront to read the private S3 bucket
resource "aws_cloudfront_origin_access_control" "web" {
  count                             = var.use_cloudfront ? 1 : 0
  name                              = "${var.name_prefix}-oac"
  description                       = "OAC for Platform Ops Auditor static console"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# CloudFront distribution
resource "aws_cloudfront_distribution" "web" {
  count               = var.use_cloudfront ? 1 : 0
  comment             = "${var.name_prefix} static developer console"
  default_root_object = "index.html"
  enabled             = true
  price_class         = "PriceClass_100"
  tags                = var.tags

  origin {
    domain_name              = aws_s3_bucket.web.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.web[0].id
    origin_id                = "s3-${aws_s3_bucket.web.id}"
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    target_origin_id       = "s3-${aws_s3_bucket.web.id}"
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 300
    max_ttl     = 3600
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# S3 bucket policy for CloudFront OAC — no wildcard principal, exact SourceArn condition
resource "aws_s3_bucket_policy" "cloudfront" {
  count  = var.use_cloudfront ? 1 : 0
  bucket = aws_s3_bucket.web.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontOAC"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.web.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.web[0].arn
          }
        }
      }
    ]
  })
}

# ── S3 static website fallback (use_cloudfront = false) ───────────────────────

# Enable S3 static website hosting
resource "aws_s3_bucket_website_configuration" "web" {
  count  = var.use_cloudfront ? 0 : 1
  bucket = aws_s3_bucket.web.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html"
  }
}

# Public read policy — required for S3 static website hosting
resource "aws_s3_bucket_policy" "public_read" {
  count      = var.use_cloudfront ? 0 : 1
  bucket     = aws_s3_bucket.web.id
  depends_on = [aws_s3_bucket_public_access_block.web_public]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.web.arn}/*"
      }
    ]
  })
}
