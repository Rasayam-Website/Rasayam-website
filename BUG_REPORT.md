# 🐛 RASAYAM WEBSITE — BUG REPORT & RESOLUTION LOG

**Project**: Rasayam E-Commerce  
**Last Updated**: June 11, 2026  
**Status**: ✅ ALL ISSUES RESOLVED — PRODUCTION READY

---

## SUMMARY

17 bugs identified across May–June 2026. All resolved. No open issues.

| Severity | Total | Resolved |
|---|---|---|
| 🔴 Critical | 5 | 5 ✅ |
| 🟡 High | 6 | 6 ✅ |
| 🟠 Medium | 3 | 3 ✅ |
| 🔵 Low | 3 | 3 ✅ |
| **Total** | **17** | **17 ✅** |

---

## 🔴 CRITICAL — ALL RESOLVED

| # | Bug | Resolution |
|---|---|---|
| 1 | Duplicate `privacy-policy/` URL paths | ✅ Single `privacy()` view, single URL route |
| 2 | Missing `OrderItem.__str__` | ✅ `f"{qty}x {name} - Order {id}"` implemented |
| 3 | No cart-to-order snapshot | ✅ `original_cart_items` JSONField on Order; `clear_paid_cart_items()` only removes paid items |
| 4 | No `selected_size` validation in checkout | ✅ `select_for_update()` checkout validates size existence before order creation |
| 5 | `@csrf_exempt` on payment verification | ✅ Removed; Razorpay signature verification is the auth mechanism |

---

## 🟡 HIGH — ALL RESOLVED

| # | Bug | Resolution |
|---|---|---|
| 6 | No cart totals in admin | ✅ `CartAdmin` shows `total_items_count()` and `total_price()` |
| 7 | `payment_verify` deleted all cart items | ✅ `clear_paid_cart_items()` scoped to paid order's snapshot only |
| 8 | OrderItem price taken from live product | ✅ `CartItem.price` stores price at add-time; `unit_price` property uses it |
| 9 | Wishlist not in admin | ✅ `WishlistAdmin` + `WishlistItemAdmin` registered with inline support |
| 10 | Missing `search_results.html` | ✅ Template exists with product grid, empty state, pagination |
| 11 | Duplicate `privacy_policy()` view function | ✅ Confirmed single `privacy()` function; no duplication |

---

## 🟠 MEDIUM — ALL RESOLVED

| # | Bug | Resolution |
|---|---|---|
| 12 | OTP valid forever | ✅ `OTPToken` model: 5-min `expires_at`, 5-attempt lockout, 60s resend cooldown |
| 13 | Order status accepts any string | ✅ `STATUS_CHOICES` enforced: Pending/Paid/Processing/Shipped/Delivered/Cancelled |
| 14 | No product slug for SEO | ✅ `Product.slug` SlugField; `/product/<slug>/` URL route added alongside `/product/<pk>/` |

---

## 🔵 LOW — ALL RESOLVED

| # | Bug | Resolution |
|---|---|---|
| 15 | Review admin missing comment preview | ✅ `comment_preview()` method in `ReviewAdmin`; `is_verified` filter added |
| 16 | Silent failures in cart operations | ✅ `decrease_cart_item` and `remove_from_cart` return `messages.info()` feedback |
| 17 | Razorpay keys not validated at startup | ✅ `settings.py` emits `RuntimeWarning` if keys missing in production |

---

## ADDITIONAL FIXES (Environment & Infrastructure, June 11, 2026)

| ID | Issue | Resolution |
|---|---|---|
| ENV-1 | `DATABASE_URL` had unencoded `@` in password | ✅ Password percent-encoded as `%40` in URL form only |
| ENV-2 | `.env` contents appended to `test_environment.py` | ✅ Both files recreated clean |
| ENV-3 | `test_environment.py` syntax broken by appended `.env` | ✅ Restored; now tests DB + S3 + Razorpay |
| ENV-4 | `WishlistItemAdmin.created_at()` shadowed Django field resolution | ✅ Renamed `wishlist_created_at()`; `admin_order_field` added |
| ENV-5 | Dead `csrf_exempt` import in `views.py` | ✅ Removed (re-added scoped to webhook view only) |
| INF-1 | No multi-stage Docker build | ✅ Two-stage Dockerfile; non-root `app:app` user; `entrypoint.sh` |
| INF-2 | Static files served by WhiteNoise in S3 mode | ✅ WhiteNoise only injected when `AWS_STATIC_BUCKET_NAME` unset |
| INF-3 | `/health/` returned static `{"status":"ok"}` | ✅ Now probes DB, cache, and S3 with 503 on degraded state |
| INF-4 | Unpinned packages in `requirements.txt` | ✅ All 33 packages pinned to exact versions |
| INF-5 | `django-storages` / `boto3` not installed | ✅ Installed and pinned; VS Code import errors cleared |

---

## NEW SYSTEMS BUILT (June 11, 2026)

| System | Files | Status |
|---|---|---|
| OTP authentication engine | `models.OTPToken`, `views._issue_otp`, `views.verify_otp`, `views.resend_otp`, `otp_gateway.py` | ✅ Complete |
| Guest session cart | `session_cart.py` — add/update/remove/merge-on-login | ✅ Complete |
| Atomic checkout with stock locking | `views.save_order` — `transaction.atomic()` + `select_for_update()` | ✅ Complete |
| Cart JSON API | `GET /api/cart/`, `POST /api/cart/update/<id>/`, `POST /api/cart/remove/<id>/` | ✅ Complete |
| Razorpay webhook receiver | `views.razorpay_webhook` — HMAC-SHA256, `payment.captured` → Order Paid | ✅ Complete |
| S3 static + media pipeline | `Rasayam_website/storages.py` — `S3StaticStorage`, `S3MediaStorage` | ✅ Complete |
| Migration 0013 | `OTPToken` table; drops legacy `otp`/`otp_created_at` fields | ✅ Applied |
| Migration 0014 | `Product.stock`, `Order.shipping_address`, `Order.transaction_id` | ✅ Applied |
