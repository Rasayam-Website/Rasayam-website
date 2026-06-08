# 🚀 Deployment Checklist - Rasayam Website Performance Optimizations

## Pre-Deployment Testing

- [x] All unit tests passing (9/9) ✅
- [x] No syntax errors in modified files ✅
- [x] Database migrations created and tested ✅
- [x] New dependencies added to requirements.txt ✅

## Local Development Setup

```bash
# Install new packages
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Test the application locally
python manage.py runserver

# Run tests
python manage.py test products.tests -v 2
```

## Pre-Production (Staging) Checklist

- [ ] Pull latest code with optimizations
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Run migrations: `python manage.py migrate`
- [ ] Test all critical endpoints:
  - [ ] Homepage (/)
  - [ ] Shop (/shop)
  - [ ] Search (/search?q=test)
  - [ ] Product detail (/product/1/)
  - [ ] Cart (/cart)
  - [ ] Authentication (login/register)
  - [ ] About (/about/)
  - [ ] Contact (/contact)
- [ ] Load test with 50 concurrent users for 5 minutes
- [ ] Verify search results pagination
- [ ] Test rate limiting (attempt >30 requests in 1 minute)
- [ ] Check cache hit ratio (if Redis configured)

## Production Deployment

### Step 1: Prepare Environment
```bash
# Set these environment variables in your production environment
export DEBUG=False
export STRICT_PRODUCTION_ENV=True
export REDIS_URL="redis://username:password@hostname:6379/0"
export CACHE_MIDDLEWARE_SECONDS=300
export SLOW_QUERY_THRESHOLD=1000
# Keep existing vars like DATABASE_URL, SECRET_KEY, etc.
```

### Step 2: Deploy Code
```bash
# Pull the latest code
git pull origin main

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Run database migrations
python manage.py migrate
```

### Step 3: Verify Deployment
```bash
# Check system
python manage.py check

# Run tests
python manage.py test products.tests

# Restart application server
# For Render: automatic restart
# For Heroku: heroku restart
# For AWS: deploy new version
```

### Step 4: Monitor Performance
- [ ] Monitor error rates (target: <1% 5xx errors)
- [ ] Check cache hit ratio (target: >50%)
- [ ] Monitor database connection count (target: <20)
- [ ] Track page load times (target: <1s avg)
- [ ] Verify rate limiting works (429 responses)

## Post-Deployment Validation

### Health Checks
```bash
# Test homepage loads
curl https://your-domain.com/

# Test search works
curl https://your-domain.com/search?q=test

# Test API endpoints return 200
curl https://your-domain.com/api/products/

# Verify no 5xx errors
# Check application logs for errors
```

### Performance Validation
```bash
# Load test (requires Apache Bench or Siege)
ab -c 50 -t 60 https://your-domain.com/
# Expected: >100 requests/second

# Or with Siege for varied endpoints
siege -c 50 -r 10 -f urls.txt
```

### Cache Verification (if Redis)
```bash
# SSH into Redis instance
redis-cli -h your-redis-host

# Check cache stats
INFO stats

# Calculate hit rate: hits / (hits + misses)
# Target: >50% hit rate
```

## Rollback Plan

If issues occur after deployment:

### Quick Rollback (Code Only)
```bash
# Revert to previous version
git revert HEAD
git push origin main

# Redeploy (automatic on Render/Heroku)
# Or manually restart on AWS
```

### Full Rollback (Code + Database)
```bash
# Revert database to previous version
python manage.py migrate products 0010_order_original_cart_items

# Revert code
git revert HEAD
git push origin main

# Restart application
```

### Troubleshooting

**Issue**: Cache not working
- Solution: Check REDIS_URL is set correctly
- Solution: Verify Redis server is running
- Solution: Check firewall allows connection to Redis

**Issue**: Rate limiting too strict
- Solution: Adjust rate limits in views.py
- Solution: Check client IP is not being blocked

**Issue**: Database slow queries
- Solution: Run `SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC;`
- Solution: Check if new indexes are being used: `EXPLAIN ANALYZE`

**Issue**: Tests failing
- Solution: Check all dependencies installed: `pip install -r requirements.txt`
- Solution: Run migrations: `python manage.py migrate`
- Solution: Check database connection

**Issue**: 500 errors in production
- Solution: Check logs for errors
- Solution: Verify environment variables set
- Solution: Check database connection string
- Solution: Verify Redis connection (if configured)

## Performance Metrics to Track

### Weekly Monitoring
- [ ] Error rate (< 1%)
- [ ] Average response time (< 500ms)
- [ ] Database query count (< 10 per request)
- [ ] Cache hit ratio (> 50%)
- [ ] Concurrent users handled (> 1000)

### Monthly Review
- [ ] Identify slow queries
- [ ] Review rate limit effectiveness
- [ ] Check cache efficiency
- [ ] Plan scaling if needed

## Escalation Contacts

For production issues:
- Database issues: Contact your database provider
- Redis issues: Check Redis provider dashboard
- Application errors: Check application logs
- DNS issues: Contact domain registrar

## Success Criteria

✅ All tests passing
✅ Homepage loads in <500ms
✅ Search works with pagination
✅ No 5xx errors in logs
✅ Cache hit ratio >50%
✅ Rate limiting prevents spam (429 responses)
✅ Can handle 1000+ concurrent users
✅ Database connections < 20

---

**Deployment Date**: ___________  
**Deployed By**: ___________  
**Status**: [ ] Successful [ ] Issues Found  
**Notes**: ___________________________________________

