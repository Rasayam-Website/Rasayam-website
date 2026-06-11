# Rasayam — Production Deployment Checklist

**Last Updated**: June 11, 2026  
**Status**: ✅ All pre-deployment work complete. Ready for AWS push.

---

## Pre-Flight: Code & Database

- [x] All Python files compile without errors
- [x] `python manage.py check` → 0 issues
- [x] Migration 0013 applied (OTPToken table)
- [x] Migration 0014 applied (Product.stock, Order.shipping_address, Order.transaction_id)
- [x] All 33 packages pinned in `requirements.txt`
- [x] `django-storages[boto3]==1.14.6` installed

---

## Pre-Flight: Environment Variables

Copy `.env.example` and fill every value before deploying.

- [ ] `SECRET_KEY` — long random string, never reuse dev key
- [ ] `DEBUG=False`
- [ ] `STRICT_PRODUCTION_ENV=True`
- [ ] `ALLOWED_HOSTS` — domain + ALB DNS
- [ ] `CSRF_TRUSTED_ORIGINS` — `https://rasayam.com,https://www.rasayam.com`
- [ ] `SECURE_SSL_REDIRECT=True`
- [ ] `SECURE_HSTS_SECONDS=31536000`
- [ ] `DATABASE_URL` — RDS PostgreSQL connection string
- [ ] `REDIS_URL` — ElastiCache endpoint
- [ ] `AWS_STORAGE_BUCKET_NAME` — media S3 bucket
- [ ] `AWS_STATIC_BUCKET_NAME` — static S3 bucket (can be same bucket)
- [ ] `AWS_S3_REGION_NAME=ap-south-1`
- [ ] `RAZORPAY_KEY_ID` — live key (starts `rzp_live_`)
- [ ] `RAZORPAY_KEY_SECRET`
- [ ] `RAZORPAY_WEBHOOK_SECRET` — from Razorpay Dashboard → Webhooks

---

## AWS Infrastructure Setup

- [ ] RDS PostgreSQL instance created (ap-south-1, Multi-AZ recommended)
- [ ] S3 bucket `rasayam-media-prod` created, CORS policy set
- [ ] S3 bucket `rasayam-static-prod` created, public-read for `static/*`
- [ ] ElastiCache Redis cluster created
- [ ] ECR repository created: `rasayam-website`
- [ ] ECS cluster + task definition created (or App Runner service)
- [ ] IAM task role with S3 read/write policy attached to ECS task
- [ ] ALB created, target group pointing to ECS service on port 8000
- [ ] ACM certificate issued for `rasayam.com` + `www.rasayam.com`
- [ ] Route 53 A records → ALB DNS

---

## Deployment Sequence

```bash
# 1. Build & push image
docker build -t rasayam-website .
docker tag rasayam-website <ecr-uri>:latest
docker push <ecr-uri>:latest

# 2. Run migrations (one-off ECS task)
python manage.py migrate --noinput

# 3. Deploy new ECS task revision (or trigger App Runner redeploy)
```

---

## Post-Deployment Verification

```bash
# Health check (must return 200 with all three checks ok)
curl https://rasayam.com/health/
# {"status":"ok","checks":{"db":"ok","cache":"ok","s3":"ok"}}

# Smoke tests
curl -L https://rasayam.com/              # Homepage
curl -L https://rasayam.com/shop/         # Shop
curl -L https://rasayam.com/search?q=saree  # Search
curl -L https://rasayam.com/admin/        # Admin login page
```

- [ ] `/health/` returns `{"status":"ok"}` with all checks green
- [ ] Homepage loads with banners and products
- [ ] Product detail page loads with gallery images from S3
- [ ] Cart add/update/remove works (JSON API)
- [ ] OTP login flow completes end-to-end
- [ ] Checkout creates order, Razorpay payment page opens
- [ ] Webhook endpoint reachable at `POST /webhooks/razorpay/`
- [ ] Admin panel loads at `/admin/`
- [ ] Static assets served from S3 URL (not `/static/`)
- [ ] No 5xx errors in CloudWatch Logs for first 10 minutes

---

## Razorpay Webhook Setup

- [ ] Dashboard → Settings → Webhooks → Add endpoint: `https://rasayam.com/webhooks/razorpay/`
- [ ] Events: `payment.captured` ✓
- [ ] Copy webhook secret → set `RAZORPAY_WEBHOOK_SECRET` in environment
- [ ] Test with Razorpay test payment → confirm order flips to `Paid` in admin

---

## Rollback Plan

| Scenario | Action |
|---|---|
| Bad code deploy | Redeploy previous ECR image tag in ECS |
| Migration broke DB | `python manage.py migrate products 0012_...`; redeploy previous image |
| Env var missing | Update ECS task definition env; force new deployment |
