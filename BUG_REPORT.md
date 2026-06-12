# Rasayam — Bug Report & Resolution Log

**Last Updated**: June 12, 2026
**Status**: ✅ All 17 issues resolved. No open bugs.

---

## Summary

| Severity | Total | Resolved |
|---|---|---|
| Critical | 5 | 5 ✅ |
| High | 6 | 6 ✅ |
| Medium | 3 | 3 ✅ |
| Low | 3 | 3 ✅ |
| **Total** | **17** | **17 ✅** |

---

## Critical

| # | Bug | Resolution |
|---|---|---|
| 1 | Duplicate `privacy-policy/` URL paths | Single `privacy()` view, single route |
| 2 | Missing `OrderItem.__str__` | `f"{qty}x {name} - Order {id}"` |
| 3 | No cart-to-order price snapshot | `original_cart_items` JSONField on Order; `clear_paid_cart_items()` scoped to paid order only |
| 4 | No `selected_size` validation in checkout | `select_for_update()` validates size before order creation |
| 5 | `@csrf_exempt` on payment verification | Removed; Razorpay HMAC signature is the auth mechanism |

---

## High

| # | Bug | Resolution |
|---|---|---|
| 6 | No cart totals in admin | `CartAdmin` with `total_items_count()` and `total_price()` |
| 7 | `payment_verify` deleted all cart items | `clear_paid_cart_items()` scoped to paid order snapshot only |
| 8 | OrderItem price taken from live product | `CartItem.price` stored at add-time; `unit_price` uses it |
| 9 | Wishlist not in admin | `WishlistAdmin` + `WishlistItemAdmin` with inline support |
| 10 | Missing `search_results.html` | Template added with product grid, empty state, pagination |
| 11 | Duplicate `privacy_policy()` view function | Confirmed single `privacy()` function |

---

## Medium

| # | Bug | Resolution |
|---|---|---|
| 12 | OTP valid forever | `OTPToken` model: 5-min expiry, 5-attempt lockout, 60s resend cooldown ✅ COMPLETE |
| 13 | Order status accepts any string | `STATUS_CHOICES` enforced: Pending/Paid/Processing/Shipped/Delivered/Cancelled |
| 14 | No product slug for SEO | `Product.slug` SlugField; `/product/<slug>/` route added |

---

## Low

| # | Bug | Resolution |
|---|---|---|
| 15 | Review admin missing comment preview | `comment_preview()` + `is_verified` filter in `ReviewAdmin` |
| 16 | Silent cart operation failures | `decrease_cart_item` and `remove_from_cart` return `messages.info()` feedback |
| 17 | Razorpay keys not validated at startup | `settings.py` emits `RuntimeWarning` if keys missing in production |

---

## Environment & Infrastructure Fixes (June 11, 2026)

| ID | Issue | Resolution |
|---|---|---|
| ENV-1 | `DATABASE_URL` had unencoded `@` in password | Password percent-encoded as `%40` |
| ENV-2 | `.env` contents appended to `test_environment.py` | Both files recreated clean |
| ENV-3 | `test_environment.py` syntax broken | Restored; tests DB + S3 + Razorpay |
| ENV-4 | `WishlistItemAdmin.created_at()` shadowed Django field | Renamed `wishlist_created_at()`; `admin_order_field` added |
| ENV-5 | Dead `csrf_exempt` import in `views.py` | Removed; re-added scoped to webhook view only |
| INF-1 | No multi-stage Docker build | Two-stage Dockerfile; non-root `app:app` user; `entrypoint.sh` |
| INF-2 | WhiteNoise active in S3 mode | WhiteNoise only injected when `AWS_STATIC_BUCKET_NAME` unset |
| INF-3 | `/health/` returned static `{"status":"ok"}` | Now probes DB, cache, S3; returns 503 on degraded state |
| INF-4 | Unpinned packages in `requirements.txt` | All 33 packages pinned to exact versions |
| INF-5 | `django-storages` / `boto3` not installed | Installed and pinned |

---

## New Systems Built (June 11, 2026)

| System | Key Files | Status |
|---|---|---|
| OTP authentication | `models.OTPToken`, `otp_gateway.py`, `views.verify_otp` | ✅ Complete |
| Guest session cart | `products/session_cart.py` | ✅ Complete |
| Atomic checkout with stock locking | `views.save_order` — `transaction.atomic()` + `select_for_update()` | ✅ Complete |
| Cart JSON API | `GET /api/cart/`, `POST /api/cart/update/<id>/`, `POST /api/cart/remove/<id>/` | ✅ Complete |
| Razorpay webhook | `views.razorpay_webhook` — HMAC-SHA256, `payment.captured` | ✅ Complete |
| S3 static + media pipeline | `Rasayam_website/storages.py` | ✅ Complete |
| Migration 0013 | OTPToken table; drops legacy `otp`/`otp_created_at` | ✅ Applied |
| Migration 0014 | `Product.stock`, `Order.shipping_address`, `Order.transaction_id` | ✅ Applied |
