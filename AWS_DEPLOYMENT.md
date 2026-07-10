# Rasayam — AWS Deployment Guide

**Last Updated**: June 12, 2026
**Status**: Production-ready. All integrations complete and verified.

---

## Architecture

```text
Internet → Route 53 → ALB (HTTPS/ACM) → ECS Fargate / App Runner
                                               │
                    ┌──────────────────────────┼──────────────────┐
                    ▼                          ▼                  ▼
             RDS PostgreSQL             S3 rasayam-static    S3 rasayam-media
             (ap-south-1)               (collectstatic)      (uploads)
                    │
             ElastiCache Redis
             (sessions + page cache)
```

### Security Group Rules

For a secure VPC architecture, construct your security groups (SG) to restrict access to the minimum required:

| Security Group | Inbound Rules | Outbound Rules | Purpose |
| --- | --- | --- | --- |
| **ALB SG** | Port 80 & 443 (from `0.0.0.0/0`) | Port 8000 (to **ECS SG**) | Public HTTPS load balancer |
| **ECS SG** | Port 8000 (from **ALB SG**) | Anywhere (`0.0.0.0/0`) | Application container instances |
| **RDS SG** | Port 5432 (from **ECS SG**) | None | Secure database storage |
| **Redis SG** | Port 6379 (from **ECS SG**) | None | Session & cache storage |

---

## Runtime Contract

|Property|Value|
|---|---|
|Startup|`sh entrypoint.sh` → collectstatic → migrate (optional) → gunicorn|
|Workers|`2 × nproc + 1`, capped at 9. Override: `WEB_CONCURRENCY`|
|Health check|`GET /health/` → 200 `{"status":"ok","checks":{"db":"ok","cache":"ok","s3":"ok"}}`|
|Static files|`collectstatic` → S3 via `S3StaticStorage`. WhiteNoise only if `AWS_STATIC_BUCKET_NAME` unset.|
|Media uploads|S3 via `S3MediaStorage` (`media/` prefix in `AWS_STORAGE_BUCKET_NAME`)|
|Migrations|`RUN_MIGRATIONS_ON_STARTUP=false` for ECS (run as one-off task). `true` OK for App Runner.|

---

## Required AWS Resources

- ECS Fargate or App Runner
- RDS PostgreSQL (ap-south-1)
- S3 `rasayam-static-prod` — static file output
- S3 `rasayam-media-prod` — uploaded images
- ElastiCache Redis — cache + session backend
- Application Load Balancer — HTTPS termination
- ACM certificate — `rasayam.com` + `www.rasayam.com`
- Route 53 — A records → ALB
- IAM task role — S3 read/write (prefer over static credentials)
- CloudWatch Logs — container log group

### IAM Task Role S3 Policy

Attach this policy to the ECS Task Execution / App Runner Role to allow S3 static & media handling:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::rasayam-static-prod",
                "arn:aws:s3:::rasayam-static-prod/*",
                "arn:aws:s3:::rasayam-media-prod",
                "arn:aws:s3:::rasayam-media-prod/*"
            ]
        }
    ]
}
```

---

## Required Environment Variables

See `.env.example` for the full list. Minimum production set:

```bash
# Django
DEBUG=False
STRICT_PRODUCTION_ENV=True
SECRET_KEY=<long random string>
ALLOWED_HOSTS=rasayam.com,www.rasayam.com,<alb-dns>.ap-south-1.elb.amazonaws.com
CSRF_TRUSTED_ORIGINS=https://rasayam.com,https://www.rasayam.com
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000

# Database
DATABASE_URL=postgres://user:pass@rds-endpoint.ap-south-1.rds.amazonaws.com:5432/rasayam

# Cache
REDIS_URL=redis://elasticache-endpoint.ap-south-1.cache.amazonaws.com:6379/0

# S3
AWS_STORAGE_BUCKET_NAME=rasayam-media-prod
AWS_STATIC_BUCKET_NAME=rasayam-static-prod
AWS_S3_REGION_NAME=ap-south-1

# Payments
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=<from Razorpay Dashboard → Webhooks>
```

---

## Deployment Steps

```bash
# 1. Build & push to ECR
docker build -t rasayam-website .
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin <account>.dkr.ecr.ap-south-1.amazonaws.com
docker tag rasayam-website <account>.dkr.ecr.ap-south-1.amazonaws.com/rasayam-website:latest
docker push <account>.dkr.ecr.ap-south-1.amazonaws.com/rasayam-website:latest

# 2. Run migrations (locally or on ECS Fargate task)
# Note: For local environment setup or local diagnostic testing:
py manage.py migrate --noinput
```

### Running Migrations on AWS ECS Fargate

Do not run migrations during the rolling container startup to avoid race conditions. Instead, run migrations as a one-off task using the AWS CLI or ECS Console:

```bash
aws ecs run-task \
  --cluster rasayam-cluster \
  --task-definition rasayam-website-task \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxxx,subnet-yyyyyy],securityGroups=[sg-ecs-id],assignPublicIp=ENABLED}" \
  --overrides "containerOverrides=[{name=rasayam-website,command=[py,manage.py,migrate,--noinput]}]"
```

```bash
# 3. Deploy new task definition / trigger App Runner redeploy

# 4. Verify
curl https://rasayam.com/health/
# {"status":"ok","checks":{"db":"ok","cache":"ok","s3":"ok"}}
```

---

## Razorpay Webhook

1. Razorpay Dashboard → Settings → Webhooks → Add endpoint
2. URL: `https://rasayam.com/webhooks/razorpay/`
3. Event: `payment.captured`
4. Copy secret → set `RAZORPAY_WEBHOOK_SECRET` in environment

Verification: HMAC-SHA256 on raw request body, compared with `X-Razorpay-Signature` via `hmac.compare_digest`.

---

## Rollback

|Scenario|Action|
|---|---|
|Bad code deploy|Redeploy previous ECR image tag in ECS task definition|
|Migration broke DB|`py manage.py migrate products 0012_...`; redeploy previous image|
|Missing env var|Update ECS task definition env; force new deployment|
