# Rasayam — AWS Deployment Guide

**Last Updated**: June 11, 2026  
**Status**: Production-ready. All systems implemented and verified.

---

## Architecture Overview

```
Internet → Route 53 → ACM/ALB (HTTPS) → ECS Fargate / App Runner
                                              │
                       ┌──────────────────────┼──────────────────────┐
                       ▼                      ▼                      ▼
                  RDS PostgreSQL        S3 (static)          S3 (media)
                  (ap-south-1)       rasayam-static-prod   rasayam-media-prod
                       │
                  ElastiCache Redis
                  (session + page cache)
```

---

## Runtime Contract

| Property | Value |
|---|---|
| Startup command | `sh entrypoint.sh` (via Dockerfile `ENTRYPOINT`) |
| Gunicorn workers | Auto: `2 × nproc + 1`, capped at 9. Override with `WEB_CONCURRENCY`. |
| Health check | `GET /health/` → 200 OK (probes DB + cache + S3) |
| Static files | `collectstatic` → S3 via `S3StaticStorage`. WhiteNoise active only when S3 bucket unset. |
| Media uploads | S3 via `S3MediaStorage` (`media/` prefix in `AWS_STORAGE_BUCKET_NAME`) |
| Database | PostgreSQL — `DATABASE_URL` or split `DB_*` vars → RDS |
| Cache | Redis via `REDIS_URL` → ElastiCache. Falls back to local memory in dev. |
| Migrations | `RUN_MIGRATIONS_ON_STARTUP=false` for ECS (run as one-off task). `true` acceptable for App Runner. |

---

## Required AWS Resources

- **ECS Fargate** or **App Runner** — app runtime
- **RDS PostgreSQL** (ap-south-1) — primary database
- **S3 bucket** `rasayam-static-prod` — collectstatic output
- **S3 bucket** `rasayam-media-prod` — uploaded images (or same bucket with separate prefixes)
- **ElastiCache Redis** — distributed cache and session backend
- **Application Load Balancer** — HTTPS termination
- **ACM certificate** — for `rasayam.com` + `www.rasayam.com`
- **Route 53** — DNS records pointing to ALB
- **IAM task role** — S3 read/write permissions (prefer over static keys)
- **CloudWatch Logs** — container log group

---

## Required Environment Variables

See `.env.example` for the full list. Minimum production set:

```bash
# Django core
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

# S3 media
AWS_STORAGE_BUCKET_NAME=rasayam-media-prod
AWS_S3_REGION_NAME=ap-south-1

# S3 static
AWS_STATIC_BUCKET_NAME=rasayam-static-prod

# Payments
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=<from Razorpay Dashboard → Webhooks>
```

---

## Deployment Steps

```bash
# 1. Build image
docker build -t rasayam-website .

# 2. Push to ECR
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin <account>.dkr.ecr.ap-south-1.amazonaws.com
docker tag rasayam-website <account>.dkr.ecr.ap-south-1.amazonaws.com/rasayam-website:latest
docker push <account>.dkr.ecr.ap-south-1.amazonaws.com/rasayam-website:latest

# 3. Run migrations (one-off ECS task or App Runner job)
python manage.py migrate --noinput

# 4. Deploy new task definition / trigger App Runner redeploy

# 5. Verify health check
curl https://rasayam.com/health/
# Expected: {"status": "ok", "checks": {"db": "ok", "cache": "ok", "s3": "ok"}}
```

---

## Webhook Configuration (Razorpay)

1. Razorpay Dashboard → Settings → Webhooks → Add new endpoint
2. URL: `https://rasayam.com/webhooks/razorpay/`
3. Events: `payment.captured`
4. Copy the webhook secret → set as `RAZORPAY_WEBHOOK_SECRET` in environment

The endpoint verifies every request with HMAC-SHA256 before touching the database.

---

## Docker / ECS Notes

```bash
# Local test with production-like env
docker run --env-file .env.example -p 8000:8000 rasayam-website

# entrypoint.sh runs: collectstatic → optional migrate → gunicorn
# RUN_MIGRATIONS_ON_STARTUP=false for ECS (run as one-off release task)
# RUN_MIGRATIONS_ON_STARTUP=true acceptable for App Runner single-container
```

---

## Rollback

```bash
# Code-only rollback — redeploy previous ECR image tag in ECS task definition

# Database rollback (if needed)
python manage.py migrate products 0012_remove_banner_banner_active_order_idx_and_more
# Then redeploy previous image
```
