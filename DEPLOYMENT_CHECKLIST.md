# Rasayam — Production Deployment Checklist

**Last Updated**: June 12, 2026
**Status**: ✅ All pre-deployment work complete. Ready for AWS push.

---

## Pre-Flight: Code & Database

- [x] `py manage.py check` → 0 issues
- [x] Migration 0013 applied — OTPToken table ✅ COMPLETE
- [x] Migration 0014 applied — Product.stock, Order.shipping_address, Order.transaction_id ✅ COMPLETE
- [x] Migration 0015 applied — alter Order.transaction_id ✅ COMPLETE
- [x] Migration 0016 applied — unique phone_number constraint on CustomerProfile ✅ COMPLETE
- [x] OTP login with 5-min expiry + 5-attempt lockout ✅ COMPLETE
- [x] Session-backed guest cart with merge-on-login ✅ COMPLETE
- [x] Razorpay webhook receiver (HMAC-SHA256) ✅ COMPLETE
- [x] All 33 packages pinned in `requirements.txt`

---

## Environment Variables

Copy `.env.example` and fill every value before deploying.

- [ ] `SECRET_KEY`
- [ ] `DEBUG=False`
- [ ] `STRICT_PRODUCTION_ENV=True`
- [ ] `ALLOWED_HOSTS` — domain + ALB DNS
- [ ] `CSRF_TRUSTED_ORIGINS`
- [ ] `SECURE_SSL_REDIRECT=True`
- [ ] `SECURE_HSTS_SECONDS=31536000`
- [ ] `DATABASE_URL` — RDS PostgreSQL
- [ ] `REDIS_URL` — ElastiCache
- [ ] `AWS_STORAGE_BUCKET_NAME` — media S3 bucket
- [ ] `AWS_STATIC_BUCKET_NAME` — static S3 bucket
- [ ] `AWS_S3_REGION_NAME=ap-south-1`
- [ ] `RAZORPAY_KEY_ID` — live key (`rzp_live_...`)
- [ ] `RAZORPAY_KEY_SECRET`
- [ ] `RAZORPAY_WEBHOOK_SECRET`

---

## AWS Infrastructure

- [ ] RDS PostgreSQL created (ap-south-1, Multi-AZ recommended)
- [ ] S3 `rasayam-media-prod` created, CORS policy set
- [ ] S3 `rasayam-static-prod` created, public-read for `static/*`
- [ ] ElastiCache Redis cluster created
- [ ] ECR repository `rasayam-website` created
- [ ] ECS cluster + task definition (or App Runner service) created
- [ ] IAM task role with S3 read/write attached to ECS task
- [ ] ALB + target group → ECS service on port 8000
- [ ] ACM certificate issued for `rasayam.com` + `www.rasayam.com`
- [ ] Route 53 A records → ALB DNS

---

## Deployment Sequence

```bash
docker build -t rasayam-website .
docker tag rasayam-website <ecr-uri>:latest
docker push <ecr-uri>:latest
py manage.py migrate --noinput

# Deploy new ECS task revision / trigger App Runner redeploy

```

---

## Post-Deployment Verification

```bash
curl https://rasayam.com/health/

# {"status":"ok","checks":{"db":"ok","cache":"ok","s3":"ok"}}

```

- [ ] `/health/` → 200 with all three checks green
- [ ] Homepage loads with banners and products
- [ ] Product detail page loads gallery images from S3
- [ ] Cart add / update / remove works (JSON API responses correct)
- [ ] OTP login flow completes end-to-end ✅
- [ ] Checkout creates order; Razorpay payment page opens
- [ ] Test payment → order flips to `Paid` in admin
- [ ] Webhook endpoint reachable at `POST /webhooks/razorpay/`
- [ ] Static assets served from S3 URL (not `/static/`)
- [ ] Admin panel loads at `/admin/`
- [ ] No 5xx errors in CloudWatch Logs for first 10 minutes

---

## Razorpay Webhook Setup

- [ ] Dashboard → Settings → Webhooks → URL: `https://rasayam.com/webhooks/razorpay/`
- [ ] Event: `payment.captured` ✓
- [ ] Copy webhook secret → set `RAZORPAY_WEBHOOK_SECRET` in environment
- [ ] Test payment confirms order flips to `Paid`

---

## Rollback

| Scenario | Action |
| --- | --- |
| Bad code deploy | Redeploy previous ECR image tag in ECS |
| Migration broke DB | `py manage.py migrate products 0012_...`; redeploy previous image |
| Missing env var | Update ECS task definition env; force new deployment |
