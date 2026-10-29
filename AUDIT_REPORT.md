# 🛡️ Production Audit & Security Assessment: Rasayam Luxury Ethnic Wear

**Live URL Audited:** `https://rasayamglobal.com`  
**Server Instance:** `43.204.238.250` (AWS EC2 ap-south-1 Mumbai)  
**Audit Date:** October 29, 2026  
**Auditor:** Principal Full-Stack QA Engineer, Security Auditor & Conversion Specialist  
**Status:** ⚠️ Action Required (Critical Security, Credential & Logic Vulnerabilities Identified)

---

## Executive Summary

A comprehensive, end-to-end production audit was conducted evaluating the live production deployment at `https://rasayamglobal.com` and the project codebase. While the platform demonstrates strong foundations (such as atomic stock locking with `select_for_update()`, Delhivery integration, and responsive styling), critical vulnerabilities exist in **hardcoded repository credentials**, **unauthenticated open API endpoints**, **disabled rate limiters**, **unhandled stock leaks from abandoned checkouts**, **missing cookie security flags in production**, and **missing transactional notifications**.

---

## 🔑 Special Section: Exposed Secrets, Passwords & Open APIs

### 1. Hardcoded Credentials & Passwords in Git Repository
* **Superuser Password Committed to Git:**
  - **Location:** `create_admin.py:10`, `create_admin.py:14`, `create_admin.py:20-21`
  - **Commit History:** Commits `ccbbd00` and `d9bd0a0` ("Force admin password reset on startup")
  - **Exposed Secret:** Superuser username `admin` with hardcoded password `Rasayam@Admin123`.
  - **Impact:** Anyone with read access to the GitHub repository can log into the production Django Admin (`https://rasayamglobal.com/admin/`) with full superuser privileges to access all customer PII, order histories, database records, and server settings.
* **Third-Party API Credentials in Public README:**
  - **Location:** `README.md:70-76`
  - **Commit History:** Commit `4ce6cb3`
  - **Exposed Credentials:**
    ```ini
    RAZORPAY_KEY_ID='rzp_test_SjPurGf3j2o6YC'
    RAZORPAY_KEY_SECRET='6OKuYuLYp9vsPJo0ie2405n3'
    CLOUDINARY_CLOUD_NAME=drg4vbsm0
    CLOUDINARY_API_KEY=762895656888373
    CLOUDINARY_API_SECRET=inXeYDGYkDgFV7_Ox1QBy_w_zEM
    ```
  - **Impact:** Live Cloudinary media storage bucket API keys and Razorpay test credentials committed directly in documentation.

### 2. Open & Unauthenticated API Endpoints
* **Database & Infrastructure Exception Leak in Health Check:**
  - **Location:** `Rasayam_website/urls.py:36, 45, 62`
  - **Route:** `GET /health/` (Open without authentication)
  - **Vulnerability:** Raw Python exceptions are returned in the JSON payload (`checks['db'] = f'error: {e}'`). If PostgreSQL or Redis suffers a connection issue, internal database hostnames, usernames, IP addresses, and driver stack traces are exposed to unauthenticated callers.
* **Public Order Enumeration & PII Leak:**
  - **Location:** `products/views.py:1093-1129`
  - **Route:** `GET /track/?q=<order_id>` (Open without authentication)
  - **Vulnerability:** Accepts sequential integers or order strings (e.g. `?q=1`, `?q=RASAYAM-42`). The view queries Delhivery and returns shipment status, delivery addresses, and city locations for any order without verifying customer identity or requiring phone/email verification.
* **Unauthenticated Crash / Denial of Service on Order Endpoints:**
  - **Location:** `products/views.py:564` (`save_order`), `products/views.py:851` (`order_detail_view`)
  - **Vulnerability:** Missing `@login_required`. Accessing these routes with an unauthenticated session causes Django to execute `Cart.objects.get(user=request.user)` with an `AnonymousUser` object, triggering uncaught `500 Internal Server Errors`.
* **Non-Functional Rate Limiting (NOP Decorators):**
  - **Location:** `products/views.py:304`, `products/views.py:382`, `products/views.py:1018`
  - **Vulnerability:** Uses `@ratelimit(..., rate='10/m')` without `block=True` and without inspecting `request.limited`. In `django-ratelimit`, this only flags the request and **never blocks traffic**. Attackers can send unlimited requests without restriction.

---

## 1. Routing, Broken Links & SEO Hygiene

| Target | Live Status | Code Reference | Finding & Impact |
| :--- | :--- | :--- | :--- |
| `https://rasayamglobal.com/sitemap.xml` | **404 Not Found** | `Rasayam_website/urls.py` | Search engine crawlers (Google, Bing) cannot discover product catalog routes, hindering indexation and search rankings. |
| `/about/` vs `/about-us/` | **Duplicate Routes (200 OK)** | `products/urls.py:9-10`<br>`products/views.py:152-160` | **Navigation Mismatch:** The main navigation header in `products/templates/products/base.html:106, 205` points to `/about/` (Customer Reviews), whereas the footer in `base.html:260` points to `/about-us/` (Brand Story). Users looking for the brand heritage land on a reviews page. |
| Canonical & OpenGraph Meta | **Missing Tags** | `products/templates/products/base.html:4-12` | No `<link rel="canonical">` is present. Missing `og:image`, `og:title`, `og:description`, `twitter:card`, and standard `<meta name="description">`. Rich social link previews (WhatsApp, iMessage, Instagram, Twitter) will fail to display branding or images when shared. |
| Dead Size Guide Link | **`href="#"` Placeholder** | `products/templates/products/product_detail.html:53` | The "Size Guide" anchor has `href="#"`. Clicking it jumps the user's viewport to the top of the screen instead of opening a sizing chart modal. |
| Unlinked Social Handle | **Plain Text** | `products/templates/products/about.html:79` | `Tag us <strong>@RASAYAM_Official</strong>` has no hyperlink to the verified Instagram account (`https://www.instagram.com/rasayam_official`). |
| Footer Copy Typo | **Visible Misspelling** | `products/templates/products/base.html:243` | Displays `"Sai Poorna Appartment"` with a double 'p'. Demotes luxury brand polish. |
| Footer Category Links | **Generic Links** | `products/templates/products/base.html:251-253` | "Daily Wear Kurtis", "Festive Collection", and "Cotton Handlooms" all link generically to `{% url 'shop' %}` without category filtering parameters. |

---

## 2. Passwordless / OTP Auth & Session Security (`/login/`)

* **Insecure Production Cookies (Missing `Secure` Flag):**
  - **Live Probe:** Running HTTP header inspection against `https://rasayamglobal.com/` revealed:
    ```http
    Set-Cookie: csrftoken=...; Path=/; SameSite=Lax
    Set-Cookie: sessionid=...; HttpOnly; Path=/; SameSite=Lax
    ```
  - **Finding:** Neither `csrftoken` nor `sessionid` contains the `Secure` attribute.
  - **Root Cause:** In `Rasayam_website/settings.py:65-66`, `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` default to `not DEBUG`, but the production environment file does not explicitly enforce them as `True`.
  - **Impact:** Cookies are vulnerable to interception over unencrypted channels or during man-in-the-middle network attacks.
* **Missing Content-Security-Policy (CSP):**
  - **Finding:** No `Content-Security-Policy` header is configured in Nginx or Django middleware. Leaves the application vulnerable to cross-site scripting (XSS) if user input is ever reflected without escaping.
* **Header Duplication:**
  - **Finding:** Both Nginx and Django `SecurityMiddleware` emit `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff`, resulting in duplicated headers on every live response.
* **OTP Spamming & Gateway Flooding via `/login/`:**
  - **Location:** `products/views.py:357-380`, `products/views.py:293-301`
  - **Vulnerability:** `login_view` has no rate limiter. When an email is submitted, it immediately executes `_issue_otp(profile)`. Unlike `resend_otp`, `_issue_otp` does not enforce the 60-second `RESEND_COOLDOWN_SECONDS` cooldown. An attacker can repeatedly POST to `/login/`, flooding AWS SES/SMTP and triggering a Denial of Service on the customer's account by constantly invalidating their active OTP.
* **User Enumeration:**
  - **Location:** `products/views.py:367-369`
  - **Vulnerability:** If an email is not found, the response redirects with `"This email isn't registered yet."`, while valid emails redirect to `verify_otp`. Attackers can harvest registered customer emails.

---

## 3. Cart, Promo Logic & Razorpay Checkout Flow

* **Missing Backend Discount / Promotion Engine:**
  - **Location:** `products/views.py:617`, `products/templates/products/cart.html:64`
  - **Vulnerability:** While marketing banners in `PromoBox` advertise offers (e.g. "Flat 300 Off on first shopping", "Flat 500 off above 3000", "20% referral discount"), the cart total calculation contains **zero promo evaluation logic**:
    ```python
    total_amount = sum(item.total_item_price for item in cart_items)
    ```
    There is no coupon code input, no referral verification, and no automated discount deduction. Customers are billed the full undiscounted amount, resulting in cart abandonment and customer support disputes.
* **Critical Stock Leak from Abandoned Checkouts (Missing Cron):**
  - **Location:** `products/views.py:605`, `products/management/commands/cancel_expired_orders.py`
  - **Vulnerability:** In `save_order`, product stock is decremented **immediately** when an order is created in `Pending` status:
    ```python
    product.stock -= item.quantity
    product.save(update_fields=['stock'])
    ```
    If the customer closes their browser or cancels out of the Razorpay payment modal, the order remains `Pending` and stock remains permanently decremented.
    While a management command `cancel_expired_orders` exists, **system inspection of the production EC2 server confirmed that neither user `ubuntu` nor `root` has a crontab entry**. The command is never run automatically. Products quickly appear as "OUT OF STOCK" even though no purchase occurred.
* **Webhook Cart Clearance Omission:**
  - **Location:** `products/views.py:836-842`
  - **Vulnerability:** In `razorpay_webhook`, when a `payment.captured` event is processed, the order status flips to `Paid`, but `clear_paid_cart_items` is never invoked. If a buyer completes payment on their phone/UPI app and closes the browser before returning to `payment_verify`, the order is paid, but their shopping bag remains full.
* **Missing `transaction_id` Population in Direct Verification:**
  - **Location:** `products/views.py:758-764`
  - **Vulnerability:** `payment_verify` sets `order.razorpay_payment_id = payment_id`, but does not populate `order.transaction_id = payment_id`. The unique DB constraint on `transaction_id` only gets set if the webhook runs first.

---

## 4. Database & Backend Performance

* **Slow `ORDER BY RANDOM()` in Cart Recommendations:**
  - **Location:** `products/views.py:210`
  - **Vulnerability:** `Product.objects.filter(stock__gt=0)...order_by('?')[:4]` executes a full table scan using PostgreSQL `RANDOM()`. Under traffic, this causes disk-heavy CPU spikes. Additionally, `gallery_images` is not prefetched here.
* **Missing Critical Database Indexes:**
  - **Location:** `products/models.py:206, 220`
  - `Order.delhivery_waybill`: Queried directly during tracking lookups; missing `db_index=True`.
  - `Order.status`: Frequently filtered (`status='Pending'`) in expiry routines; missing index.
  - `Product.stock`: Filtered in recommendation queries (`stock__gt=0`); missing index.

---

## 5. Frontend Polish, Responsive Layout & Core Web Vitals

* **Z-Index Modal & Notification Clash:**
  - **Location:** `products/templates/products/base.html:51, 218`
  - **Finding:** Both `.messages-container` and `#wishlist-modal` are assigned identical `z-index: 9999`. Toast messages appear behind or clip modal overlays depending on DOM layout.
* **Cumulative Layout Shift (CLS) on Catalogue Images:**
  - **Location:** `products/templates/products/shop.html:37`, `products/templates/products/index.html:150`
  - **Finding:** Product images do not define explicit `width` and `height` aspect-ratio attributes or `loading="lazy"`. During initial mobile loading, the grid shifts abruptly as image payloads resolve.
* **Horizontal Viewport Overflow on Windows/Desktops:**
  - **Location:** `products/templates/products/base.html:29`, `products/static/products/style2.css:532, 577, 622`
  - **Finding:** Uses `max-width: 100vw`. On desktop browsers where the scrollbar occupies 15-17px, `100vw` exceeds the viewport width, creating horizontal jitter. Should be normalized to `100%`.

---

## 6. Order Tracking & Transactional Notifications

* **Sequential ID Enumeration in Order Tracking:**
  - **Location:** `products/views.py:1109-1129`
  - **Vulnerability:** The public tracking view extracts the integer ID from inputs like `RASAYAM-1` or `1` and looks up the order object directly. It does not require a customer phone number or email address confirmation. Anyone can crawl `?q=1`, `?q=2`, etc., to scrape tracking logs and recipient cities.
* **Silent Contact Form (Missing Admin Notification):**
  - **Location:** `products/views.py:170-181`
  - **Vulnerability:** When a customer submits a return request, damaged product report, or concierge inquiry, it only inserts a row into `ContactInquiry`. No email is dispatched to `admin@rasayamglobal.com`. Inquiries remain unread unless an administrator manually logs into Django Admin.
* **Missing Order Confirmation & Shipping Emails:**
  - **Location:** `products/views.py:760`, `products/views.py:840`
  - **Vulnerability:** The platform does not send transactional order receipts or Delhivery tracking updates to buyers upon successful payment.

---

## 7. Prioritized Automated Fix Plan

### 🔴 Phase 1: [CRITICAL] Security & Infrastructure (Immediate)
1. **Remove Hardcoded Credentials:**
   - Remove default superuser password from `create_admin.py` and read from environment variable `ADMIN_PASSWORD`.
   - Sanitize `README.md` to remove Cloudinary keys and Razorpay secrets.
   - Force change of the production admin password on EC2.
2. **Enable Secure Cookie Transmission:**
   - Set `SESSION_COOKIE_SECURE = True` and `CSRF_COOKIE_SECURE = True` in `.env` on production EC2.
3. **Configure Cron Job for Stock Recovery:**
   - Install a crontab entry on the EC2 server to run `py manage.py cancel_expired_orders` every 10 minutes, preventing inventory lockdown from abandoned payments.
4. **Sanitize `/health/` Endpoint:**
   - Mask internal database/cache exception details in `Rasayam_website/urls.py:36` to prevent server environment disclosure.
5. **Protect Order Endpoints from Unauthenticated 500 Crashes:**
   - Add `@login_required` to `save_order` (`products/views.py:546`) and `order_detail_view` (`products/views.py:851`).

### 🟡 Phase 2: [HIGH] Business Logic, Auth & SEO (Next)
1. **Activate Rate Limiting:**
   - Update all `@ratelimit` decorators in `products/views.py` to specify `block=True` so abusers are blocked with HTTP 429.
   - Add rate-limiting and a 60-second cooldown check to `login_view` to stop email OTP spamming.
2. **Implement Order Tracking Verification:**
   - Require Order ID **plus** either phone number or email in `products/views.py:1093` before exposing Delhivery shipment details.
3. **Fix Webhook Cart Clearance:**
   - Ensure `razorpay_webhook` (`products/views.py:836`) clears user cart items when an asynchronous payment succeeds.
4. **Implement Sitemap & Meta Tags:**
   - Add a dynamic `sitemap.xml` route using Django's sitemaps framework in `Rasayam_website/urls.py`.
   - Add `<link rel="canonical">` and OpenGraph/Twitter meta tags in `products/templates/products/base.html`.
5. **Dispatch Contact & Order Confirmation Emails:**
   - Connect Django `send_mail` in `contact` (`products/views.py:163`) to notify `admin@rasayamglobal.com`.
   - Send order confirmation emails upon successful payment verification.

### 🟢 Phase 3: [POLISH] UI/UX Polish & Performance (Final)
1. **Unify About vs About-Us Navigation:**
   - Point header "ABOUT" in `base.html:106` to `/about-us/` (Brand Heritage), and label `/about/` as "Stories" or "Reviews".
2. **Fix Dead Links & Typo:**
   - Correct `"Sai Poorna Appartment"` to `"Sai Poorna Apartment"` in `base.html:243`.
   - Link `Size Guide` in `product_detail.html:53` to a sizing guide modal.
   - Link `@RASAYAM_Official` in `about.html:79` to Instagram.
3. **Resolve Z-Index Collision & Cumulative Layout Shift:**
   - Elevate `.messages-container` to `z-index: 10001` in `base.html:51`.
   - Add `loading="lazy"` and explicit aspect ratios to product grid cards.
4. **Database Index Additions:**
   - Create a migration adding indexes to `Order.delhivery_waybill`, `Order.status`, and `Product.stock`.
