# Rasayam — AWS Deployment Guide

**Last Updated**: June 12, 2026
**Status**: Production-ready. All integrations complete and verified.

---

## Architecture

```
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

---

## Runtime Contract

| Property | Value |
|---|---|
| Startup | `sh entrypoint.sh` → collectstatic → migrate (optional) → gunicorn |
| Workers | `2 × nproc + 1`, capped at 9. Override: `WEB_CONCURRENCY` |
| Health check | `GET /health/` → 200 `{"status":"ok","checks":{"db":"ok","cache":"ok","s3":"ok"}}` |
| Static files | `collectstatic` → S3 via `S3StaticStorage`. WhiteNoise only if `AWS_STATIC_BUCKET_NAME` unset. |
| Media uploads | S3 via `S3MediaStorage` (`media/` prefix in `AWS_STORAGE_BUCKET_NAME`) |
| Migrations | `RUN_MIGRATIONS_ON_STARTUP=false` for ECS (run as one-off task). `true` OK for App Runner. |

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

# 2. Run migrations (one-off ECS task)
python manage.py migrate --noinput

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

| Scenario | Action |
|---|---|
| Bad code deploy | Redeploy previous ECR image tag in ECS task definition |
| Migration broke DB | `python manage.py migrate products 0012_...`; redeploy previous image |
| Missing env var | Update ECS task definition env; force new deployment |
