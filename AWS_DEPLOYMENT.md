# Rasayam AWS Deployment Checklist

This project is ready for the infrastructure phase with Django + Gunicorn, a `/health/` endpoint, environment-driven production settings, optional S3 media storage, and RDS-ready database configuration.

## Runtime Contract

- App command: `gunicorn Rasayam_website.wsgi:application --bind 0.0.0.0:$PORT`
- Health check path: `/health/`
- Static files: served by WhiteNoise after `python manage.py collectstatic --noinput --clear`
- Media uploads: use S3 when `AWS_STORAGE_BUCKET_NAME` is set
- Database: PostgreSQL via `DATABASE_URL` or `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST`

## Required AWS Resources

- EC2, Elastic Beanstalk, App Runner, or ECS/Fargate for the app runtime
- RDS PostgreSQL for the production database
- S3 bucket for uploaded product/category/banner images
- IAM role or access keys allowing the app to read/write the S3 media bucket
- Application Load Balancer or managed HTTPS endpoint
- ACM certificate for the production domain
- Route 53 records for `rasayam.com` and `www.rasayam.com`
- CloudWatch Logs for application logs

## Required Environment Variables

Use `.env.example` as the source of truth. At minimum, production needs:

- `DEBUG=False`
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL` or split RDS variables
- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `AWS_STORAGE_BUCKET_NAME` for S3 media uploads

## Deployment Steps

1. Create RDS PostgreSQL and set `DATABASE_URL`.
2. Create an S3 media bucket and attach read/write permissions to the app runtime role.
3. Set environment variables from `.env.example` in the AWS service.
4. Run migrations once:
   ```bash
   python manage.py migrate --noinput
   ```
5. Collect static files:
   ```bash
   python manage.py collectstatic --noinput --clear
   ```
6. Start the app with the `Procfile` or Dockerfile command.
7. Configure the load balancer health check to `GET /health/`.
8. Point the domain to the load balancer or managed AWS endpoint.

## Docker/ECS Notes

Build and run:

```bash
docker build -t rasayam-website .
docker run --env-file .env.example -p 8000:8000 rasayam-website
```

For ECS/Fargate, keep `RUN_MIGRATIONS_ON_STARTUP=false` and run migrations as a one-off task during releases. For a single App Runner style deployment, `RUN_MIGRATIONS_ON_STARTUP=true` is acceptable during early infrastructure testing.
