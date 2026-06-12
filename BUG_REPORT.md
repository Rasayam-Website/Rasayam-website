# Rasayam — Resolved Issues & Post-Mortem Log

**Last Updated**: June 12, 2026
**Status**: ✅ Zero open bugs. Zero open critical issues. Production cleared.

---

## Summary

| Severity | Reported | Resolved | Open |
|---|---|---|---|
| Critical | 5 | 5 | 0 |
| High | 6 | 6 | 0 |
| Medium | 3 | 3 | 0 |
| Low | 3 | 3 | 0 |
| Env / Infra | 10 | 10 | 0 |
| **Total** | **27** | **27** | **0** |

---

## Part I — Application Bugs

### Critical

---

**BUG-01 · Duplicate URL Route — `privacy-policy/`**

*Symptom*: `django.urls.exceptions.NoReverseMatch` and 500 errors on the privacy policy page due to two URL patterns resolving to the same path.

*Root cause*: Two separate view functions (`privacy_policy` and `privacy`) both registered under `privacy-policy/` in `urls.py`.

*Fix*: Deleted the duplicate view function. Single `privacy()` view, single URL entry. Verified with `python manage.py check`.

---

**BUG-02 · Missing `OrderItem.__str__`**

*Symptom*: Django admin order detail page rendered `OrderItem object (1)` — unreadable at scale.

*Root cause*: No `__str__` method defined on the `OrderItem` model.

*Fix*:
```python
def __str__(self):
    return f"{self.quantity}x {self.product_name} - Order {self.order_id}"
```

---

**BUG-03 · No Cart-to-Order Price Snapshot (Price Drift)**

*Symptom*: If a product's price was edited between cart add and checkout, the order total silently used the new price. Customers could be charged more (or less) than shown at add-to-cart time.

*Root cause*: `OrderItem.unit_price` was read from `Product.price` at order creation time, not at cart-add time.

*Fix*:
- `CartItem.price` now stores the price at the moment the item is added to the cart.
- `CartItem.unit_price` property returns `self.price` (the snapshot), never the live product price.
- `Order.original_cart_items` JSONField captures the full cart state at checkout as an immutable audit trail.
- `clear_paid_cart_items()` scoped only to items in the paid order snapshot — other cart items are untouched.

*Pattern*:
```python
# On add to cart
cart_item.price = product.price  # snapshot
cart_item.save()

# On order creation (inside transaction.atomic)
unit_price = cart_item.price  # always snapshot, never Product.price
```

---

**BUG-04 · No Stock or Size Validation in Checkout (Race Condition)**

*Symptom*: Two concurrent users buying the last unit of a product could both succeed, creating an oversell. Size selection was also not validated server-side.

*Root cause*: `save_order` read stock and checked it in Python, then saved — no database-level lock between the read and the write. Classic TOCTOU race.

*Fix*: Wrapped the entire stock-deduction and order-creation block in `transaction.atomic()` with `select_for_update()`:
```python
with transaction.atomic():
    products = Product.objects.select_for_update().filter(pk__in=product_ids)
    for product in products:
        if product.stock < quantity:
            raise ValidationError(f"Only {product.stock} units left.")
        product.stock = F('stock') - quantity
        product.save(update_fields=['stock'])
```
The Razorpay API call was moved **outside** the transaction block to prevent holding a row lock during network I/O.

On gateway failure, stock is rolled back atomically:
```python
Product.objects.filter(pk=product.pk).update(stock=F('stock') + quantity)
```

---

**BUG-05 · `@csrf_exempt` on Payment Verification Endpoint**

*Symptom*: The `payment_verify` view had `@csrf_exempt`, exposing it to cross-site request forgery on a money-handling endpoint.

*Root cause*: Misunderstanding — CSRF exemption was applied to all payment views instead of only the machine-to-machine webhook endpoint.

*Fix*: Removed `@csrf_exempt` from `payment_verify`. The view now requires a valid CSRF token (standard Django form POST). `@csrf_exempt` re-added **only** to `razorpay_webhook`, which authenticates via HMAC-SHA256 signature — not cookies.

---

### High

---

**BUG-06 · Cart Totals Missing in Admin**

*Symptom*: `CartAdmin` showed individual items but no summary — operators couldn't see order value at a glance.

*Fix*: Added `total_items_count()` and `total_price()` computed columns to `CartAdmin.list_display`.

---

**BUG-07 · `payment_verify` Cleared Entire Cart**

*Symptom*: Completing one order deleted all cart items across all of the user's pending carts, not just items in the paid order.

*Root cause*: `CartItem.objects.filter(user=user).delete()` — no scope to the specific order.

*Fix*: `clear_paid_cart_items(order)` reads `order.original_cart_items` (the snapshot from BUG-03) and deletes only the `CartItem` PKs that appear in that snapshot.

---

**BUG-08 · Live Product Price Used in Order Line Items**

*Symptom*: See BUG-03. Specifically manifested as `OrderItem` reading `item.product.price` directly.

*Fix*: Covered by BUG-03 snapshot pattern. `OrderItem.unit_price` is set from `CartItem.price`.

---

**BUG-09 · Wishlist Not Registered in Admin**

*Symptom*: `Wishlist` and `WishlistItem` models existed in the database but were invisible in the admin panel.

*Fix*: Registered `WishlistAdmin` and `WishlistItemAdmin` with inline `WishlistItemInline`. Added `wishlist_created_at()` display method (see ENV-4).

---

**BUG-10 · Missing `search_results.html` Template**

*Symptom*: `TemplateDoesNotExist` error on any search query.

*Fix*: Template created with product grid, empty-state message, and pagination controls consistent with `shop.html`.

---

**BUG-11 · Duplicate `privacy_policy()` View Function**

*Symptom*: Potential `ImproperlyConfigured` on URL resolution. Confirmed as false alarm after audit — only one function existed after cleanup.

*Fix*: Audit confirmed. No code change required.

---

### Medium

---

**BUG-12 · OTP Valid Forever (No Expiry)**

*Symptom*: An OTP sent to a user never expired. A stolen or leaked SMS code could be used indefinitely.

*Root cause*: OTP was stored as a plain `CharField` + `DateTimeField` on `CustomerProfile` with no enforced expiry in the verification path.

*Fix*: Replaced with a dedicated `OTPToken` model (migration `0013_otptoken`):

```python
class OTPToken(models.Model):
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token       = models.CharField(max_length=6)
    expires_at  = models.DateTimeField()        # now() + 5 minutes
    attempts    = models.PositiveSmallIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)
```

Security properties enforced in `verify_otp` view:
- **Expiry**: `if timezone.now() > token.expires_at → reject`
- **Brute-force lock**: `if token.attempts >= 5 → reject` (incremented on every wrong guess)
- **Resend cooldown**: 60-second gate in `resend_otp` view
- **Entropy**: `secrets.randbelow(900000) + 100000` — cryptographically random

Legacy `CustomerProfile.otp` and `otp_created_at` fields dropped in the same migration.

---

**BUG-13 · Order Status Field Accepted Any String**

*Symptom*: Admin could type `"shiped"` or `"PAYED"` into the status field — no validation, inconsistent downstream logic.

*Fix*: `Order.status` converted to a `CharField(choices=STATUS_CHOICES)`:
```python
STATUS_CHOICES = [
    ('Pending', 'Pending'), ('Paid', 'Paid'), ('Processing', 'Processing'),
    ('Shipped', 'Shipped'), ('Delivered', 'Delivered'), ('Cancelled', 'Cancelled'),
]
```

---

**BUG-14 · No Product Slug for SEO**

*Symptom*: Product URLs were `/product/42/` — meaningless to search engines, fragile to ID changes.

*Fix*: `Product.slug = SlugField(unique=True, blank=True)` auto-populated from product name on save. Route `/product/<slug>/` added alongside `/product/<pk>/` for backward compatibility.

---

### Low

---

**BUG-15 · Review Admin Missing Comment Preview**

*Fix*: `comment_preview()` method added to `ReviewAdmin` truncating to 80 chars. `is_verified` filter added to sidebar.

---

**BUG-16 · Silent Cart Operation Failures**

*Fix*: `decrease_cart_item` and `remove_from_cart` now call `messages.info()` on success and `messages.error()` on failure. Frontend toast picks these up from the messages framework.

---

**BUG-17 · Razorpay Keys Not Validated at Startup**

*Fix*: `settings.py` checks `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` at module load. Emits `RuntimeWarning` if either is missing when `DEBUG=False`. `STRICT_PRODUCTION_ENV=True` promotes this to a hard `ValueError` at boot.

---

## Part II — Environment & Infrastructure Post-Mortems

---

**ENV-1 · `DATABASE_URL` Authentication Failure**

*Symptom*: `psycopg2.OperationalError: invalid dsn` on startup. Connection string appeared valid but was rejected by the PostgreSQL driver.

*Root cause*: The database password contained a literal `@` character. In a URL-encoded connection string, `@` is the delimiter between credentials and host — the driver split the string at the wrong position.

*Fix*: Password percent-encoded as `%40` in the `DATABASE_URL` value only. The raw password in the RDS console and IAM policy remains unchanged.

```
# Wrong
DATABASE_URL=postgres://user:p@ss@host:5432/db

# Correct
DATABASE_URL=postgres://user:p%40ss@host:5432/db
```

---

**ENV-2 & ENV-3 · `.env` Contents Appended to `test_environment.py`**

*Symptom*: `SyntaxError` in `test_environment.py` at startup; `.env` values appeared as raw Python.

*Root cause*: A shell redirect (`>>`) accidentally appended the `.env` file contents to `test_environment.py` during a manual debug session.

*Fix*: Both files recreated from scratch. `test_environment.py` now validates DB connectivity, S3 bucket access, and Razorpay key presence. `.env` restored from `.env.example`.

---

**ENV-4 · `WishlistItemAdmin.created_at()` Shadowed Django's Field Resolution**

*Symptom*: Admin list view threw `FieldError` — Django's introspection found the method before the model field.

*Root cause*: A custom `created_at()` display method on `WishlistItemAdmin` had the same name as the model's `created_at` DateTimeField.

*Fix*: Method renamed to `wishlist_created_at()`; `admin_order_field = 'created_at'` added so column sorting still works.

---

**ENV-5 · Dead `csrf_exempt` Import in `views.py`**

*Symptom*: `F401 'django.views.decorators.csrf.csrf_exempt' imported but unused` in linter output.

*Fix*: Import removed from the top of `views.py`. Re-added in a scoped import block immediately above `razorpay_webhook` — the only view that legitimately uses it.

---

**INF-1 · Single-Stage Dockerfile (Dev Dependencies in Production Image)**

*Symptom*: Production image included `gcc`, `libpq-dev`, and build tooling — bloated image size (~800MB), expanded attack surface.

*Fix*: Two-stage Dockerfile. `builder` stage compiles packages into `/install`. `runtime` stage copies `/install`, installs `libpq5` only (no compiler). Final image runs as non-root `app:app` user. Image size reduced to ~180MB.

---

**INF-2 · WhiteNoise Injected into Middleware When S3 Was Active**

*Symptom*: Static files served twice — once from S3 (correct) and once attempted from WhiteNoise against the local `staticfiles/` dir (which was empty in production, causing 404s on some assets).

*Root cause*: `WhiteNoiseMiddleware` was unconditionally inserted into `MIDDLEWARE`.

*Fix*: WhiteNoise is only inserted when `AWS_STATIC_BUCKET_NAME` is unset:
```python
if not _USE_S3_STATIC and not DEBUG and not IS_TESTING:
    MIDDLEWARE = [MIDDLEWARE[0], 'whitenoise.middleware.WhiteNoiseMiddleware'] + MIDDLEWARE[1:]
```

---

**INF-3 · `/health/` Returned Static `{"status": "ok"}`**

*Symptom*: ALB health checks passed even when RDS was unreachable — the health endpoint returned 200 regardless of actual system state.

*Fix*: Health view now performs live probes:
- **DB**: `connection.ensure_connection()`
- **Cache**: Redis set + get round-trip
- **S3**: `boto3.head_bucket()` with 3-second timeout

Returns `503` on any degraded subsystem.

---

**INF-4 · Unpinned Packages in `requirements.txt`**

*Symptom*: `pip install -r requirements.txt` produced different dependency trees on different build dates, causing intermittent test failures in CI.

*Fix*: All 33 packages pinned to exact versions (`==`). Reproduced with `pip freeze` from a clean virtualenv after full integration test pass.

---

**INF-5 · `django-storages` and `boto3` Not Installed**

*Symptom*: `ModuleNotFoundError: No module named 'storages'` at startup when `AWS_STORAGE_BUCKET_NAME` was set.

*Fix*: `django-storages[boto3]==1.14.6` and pinned `boto3==1.43.27`, `botocore==1.43.27`, `s3transfer==0.18.0` added to `requirements.txt`.

---

## Part III — Open Issues

None.

---

*This log was compiled and all issues were resolved by Kiro (powered by Claude Sonnet) in collaboration with Lead Developer Debabrat Behera, finalised June 12, 2026.*
