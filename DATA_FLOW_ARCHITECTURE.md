# Rasayam: System Architecture & Data Flow Specification

This document specifies the end-to-end architecture, sequence flows, data classification, concurrency behavior, and infrastructure dependencies for the Rasayam luxury ethnic wear e-commerce platform (`rasayamglobal.com`, Django 6.0).

---

## 1. Static Architecture & Trust Zones

### Master Topology Diagram

```mermaid
flowchart TD
    subgraph ZonePublic["Zone 1: Public Edge (Untrusted Perimeter)"]
        ClientBrowser["Client Browser (Mobile / Desktop)"]
        CF["Cloudflare Edge CDN<br/>• SSL/TLS Termination<br/>• DDoS / WAF Filtering<br/>• HTTP/2 & HTTP/3 Proxy<br/><i>[Infrastructure to confirm]</i>"]
    end

    subgraph ZoneApp["Zone 2: Application Runtime (Private Compute)"]
        Nginx["Nginx Reverse Proxy<br/>• Port 80/443 listener<br/>• Gzip compression<br/>• Static routing to disk<br/>• Proxy pass to 127.0.0.1:8000"]
        Gunicorn["Gunicorn WSGI Server<br/>• 2 Synchronous Workers<br/>• 127.0.0.1:8000 runtime"]
        DjangoApp["Django 6.0 Core Application (/srv/rasayam)<br/>• Middleware: Security, RateLimit, Session, CSRF<br/>• products.urls & products.views<br/>• WhiteNoise Static Engine<br/><i>[Verified in code]</i>"]
        CronRunner["OS Crontab Service<br/>• cancel_expired_orders runner<br/><i>[Infrastructure to confirm]</i>"]
    end

    subgraph ZoneData["Zone 3: Private Data Store (Host-Local Storage)"]
        Postgres[("PostgreSQL 16 (localhost:5432)<br/>• Tables: Order, Product, CustomerProfile, Address, OTPToken<br/>• Status: Pending, Paid, Cancelled, Payment Review, Refunded<br/>• Performance Indexes (0019/0020)<br/><i>[Verified in code]</i>")]
        CacheStore[("Django Cache Backend<br/>• RedisCache (if REDIS_URL set)<br/>• LocMemCache (fallback)<br/><i>[Verified in code / Infrastructure to confirm]</i>")]
        StaticDisk[("Static / Media Storage<br/>• /srv/rasayam/staticfiles/<br/>• Cloudinary / Media storage<br/><i>[Verified in code]</i>")]
    end

    subgraph ZoneThirdParty["Zone 4: Third-Party External Services (External Trust)"]
        RazorpayGateway["Razorpay Payments Gateway<br/>• REST API (Order Creation & Refunds)<br/>• Hosted Modal (Checkout)<br/>• Webhook Callbacks (/webhooks/razorpay/)<br/><i>[Verified in code]</i>"]
        DelhiveryGateway["Delhivery Logistics API<br/>• Pincode Serviceability API<br/>• Tracking API<br/>• Packing Slip API<br/>• Dormant CMU Shipment API (no active callers)<br/><i>[Verified in code]</i>"]
        SMTPGateway["SMTP / Email Provider<br/>• AWS SES or SMTP Host<br/>• 5-min OTP Delivery via send_mail<br/><i>[Infrastructure to confirm]</i>"]
    end

    ClientBrowser -->|HTTPS / WSS| CF
    CF -->|Reverse Proxy / SNI| Nginx
    Nginx -->|HTTP 127.0.0.1:8000| Gunicorn
    Gunicorn --> DjangoApp
    CronRunner -->|py manage.py| DjangoApp

    DjangoApp -->|psycopg2 / SQL Transactions| Postgres
    DjangoApp -->|django.core.cache| CacheStore
    Nginx -->|Direct Disk Reads| StaticDisk
    DjangoApp -->|Static Collection / Serving| StaticDisk

    DjangoApp -->|HTTPS REST API| RazorpayGateway
    RazorpayGateway -->|POST Webhook /webhooks/razorpay/| CF
    DjangoApp -->|HTTPS REST API| DelhiveryGateway
    DjangoApp -->|SMTP TLS 587| SMTPGateway
```

### Component Verification Matrix

| Component | Trust Zone | Verification Status | Operational Notes & Code Reference |
| :--- | :--- | :--- | :--- |
| **Cloudflare CDN** | Public Edge | **Infrastructure to confirm** | Identified in production response headers (`Cf-Ray`, `cf-cache-status: DYNAMIC`). WAF firewall rules, SSL mode (Strict/Full), and HTTP/3 caching require dashboard verification. |
| **Nginx Reverse Proxy** | Application Runtime | **Verified in code** | Configured in `nginx.conf` with proxy headers (`X-Forwarded-For`, `X-Forwarded-Proto`), gzip compression, and direct static asset routing. |
| **Gunicorn WSGI** | Application Runtime | **Verified in code** | Configured via `start_gunicorn.sh` (2 synchronous workers binding to `127.0.0.1:8000`). |
| **Django Application** | Application Runtime | **Verified in code** | Application settings in `Rasayam_website/settings.py` and URL endpoints in `products/urls.py`. |
| **Stock Cleanup Cron** | Application Runtime | **Infrastructure to confirm** | Command logic verified in `products/management/commands/cancel_expired_orders.py`. OS crontab schedule (`*/10 * * * *`) requires host verification. |
| **PostgreSQL 16** | Private Data | **Verified in code** | Engine verified in `settings.py:142`. Models and constraints verified in `products/models.py`. |
| **Cache Engine** | Private Data | **Infrastructure to confirm** | `settings.py:181-200` conditionally binds `RedisCache` if `REDIS_URL` is configured, otherwise silently falling back to `LocMemCache`. |
| **Static / Media Storage** | Private Data | **Verified in code** | Static files served through WhiteNoise (`settings.py:56`). Media uses Cloudinary / local fallback (`settings.py:270-295`). |
| **Razorpay Payments** | Third-Party | **Verified in code** | Handled in `products/views.py:save_order`, `payment_verify`, `razorpay_webhook`, and `products/admin.py:refund_via_razorpay`. |
| **Delhivery Logistics** | Third-Party | **Verified in code** | Endpoints verified in `products/delhivery.py`. `create_shipment` verified as dormant. |
| **SMTP / Email Gateway** | Third-Party | **Infrastructure to confirm** | `settings.py:458-468` reads `EMAIL_HOST`. `.env.example` lists AWS SES, but production credentials and sender DNS records require confirmation. |

---

## 2. Sequence Flows (Happy Paths, Failure Paths & Payment Review)

### Use Case 1: Checkout, Payment, Late Capture & Stock Recovery

#### Happy Path

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Customer (Browser)
    participant SaveOrder as products/views.py:save_order
    participant DB as PostgreSQL (DB)
    participant RazorpayAPI as Razorpay REST API
    participant VerifyView as products/views.py:payment_verify
    participant WebhookView as products/views.py:razorpay_webhook
    participant CartHelper as products/views.py:clear_paid_cart_items

    Customer->>SaveOrder: POST /save-order/ (shipping_address_id)
    activate SaveOrder
    Note over SaveOrder: Rate limit: 10/h per user
    SaveOrder->>DB: BEGIN TRANSACTION (transaction.atomic)
    SaveOrder->>DB: Product.objects.select_for_update().filter(id__in=product_ids)
    Note over DB: Locks product rows at DB level<br/>Prevents concurrent overselling
    SaveOrder->>DB: Check stock & decrement Product.stock
    SaveOrder->>DB: Create Order(status='Pending', original_cart_items=[...])
    SaveOrder->>DB: Create OrderItem records
    SaveOrder->>DB: COMMIT TRANSACTION
    SaveOrder->>RazorpayAPI: razorpay_client.order.create(amount_in_paise, receipt)
    RazorpayAPI-->>SaveOrder: Returns razorpay_order_id
    SaveOrder->>DB: Order.objects.update(razorpay_order_id=order_id)
    SaveOrder-->>Customer: Render products/payment.html (Razorpay modal config)
    deactivate SaveOrder

    Customer->>RazorpayAPI: Completes payment (UPI / Card / NetBanking)
    RazorpayAPI-->>Customer: Returns razorpay_payment_id, signature

    Customer->>VerifyView: POST /payment-verify/ (payment_id, razorpay_order_id, signature)
    activate VerifyView
    VerifyView->>VerifyView: razorpay_client.utility.verify_payment_signature(params)
    VerifyView->>DB: BEGIN TRANSACTION (transaction.atomic)
    VerifyView->>DB: Order.objects.select_for_update().get(razorpay_order_id, user)
    Note over VerifyView,DB: Verified status == 'Pending': flips to Paid
    VerifyView->>DB: Update order (is_paid=True, status='Paid', transaction_id=payment_id)
    VerifyView->>CartHelper: clear_paid_cart_items(cart, order)
    CartHelper->>DB: Delete/decrement captured CartItem records
    VerifyView->>DB: COMMIT TRANSACTION
    VerifyView-->>Customer: 302 Redirect to /payment-success/<order_id>/
    deactivate VerifyView

    opt Asynchronous Server Webhook Backup
        RazorpayAPI->>WebhookView: POST /webhooks/razorpay/ (event: payment.captured)
        activate WebhookView
        WebhookView->>WebhookView: hmac.compare_digest(expected_sig, received_sig)
        WebhookView->>DB: BEGIN TRANSACTION (transaction.atomic)
        WebhookView->>DB: Order.objects.select_for_update().get(razorpay_order_id)
        Note over WebhookView,DB: If order.is_paid is already True, safe no-op
        WebhookView->>DB: COMMIT TRANSACTION
        WebhookView-->>RazorpayAPI: HTTP 200 {"status": "ok"}
        deactivate WebhookView
    end
```

#### Explicit Failure & Late Capture Paths

```mermaid
flowchart TD
    Start["Customer Submits /save-order/"] --> F1{"Enough stock for all items?<br/><i>products/views.py:629</i>"}
    F1 -- "No" --> E1["Rollback atomic block<br/>Redirect to /cart/<br/>Show 'Only X units left'"]
    F1 -- "Yes" --> F2{"Amount >= 100 paise (₹1)?<br/><i>products/views.py:674</i>"}
    F2 -- "No" --> E2["Atomic stock restoration<br/>Delete Order<br/>Show 'Amount must be at least ₹1'"]
    F2 -- "Yes" --> F3{"Razorpay API reachable?<br/><i>products/views.py:689</i>"}
    F3 -- "No / Auth Error" --> E3["Atomic stock restoration from snapshot<br/>Delete Order<br/>Render cart.html with HTTP 401 or 500"]
    F3 -- "Yes" --> F4["Render payment.html modal"]
    
    F4 --> F5{"Customer completes payment<br/>in browser modal?"}
    F5 -- "No: Drops off > 20 mins" --> CleanupJob["Cron Job: products/management/commands/cancel_expired_orders.py<br/>Scans orders > 20 min old<br/>Locks row with select_for_update()<br/>Restores stock via F('stock') + qty<br/>Marks status='Cancelled'"]
    
    CleanupJob --> LatePay["Customer completes payment after 20 mins<br/>(Late Capture / Webhook arrives)"]
    
    LatePay --> CheckLate{"Order status == 'Cancelled'?<br/><i>products/views.py:808 & 898</i>"}
    CheckLate -- "Yes in /webhooks/razorpay/" --> RevWeb["Lock row with select_for_update()<br/>Set status='Payment Review'<br/>Save payment_id & amount<br/>Do NOT change stock, do NOT refund<br/>Return HTTP 200 {'status': 'payment_review'}"]
    CheckLate -- "Yes in /payment-verify/" --> RevView["Lock row with select_for_update()<br/>Set status='Payment Review'<br/>Save payment_id, signature, transaction_id<br/>Render neutral products/payment_review.html"]
    
    RevWeb --> AdminResolve{"Admin Manual Resolution<br/><i>products/admin.py:OrderAdmin</i>"}
    RevView --> AdminResolve
    
    AdminResolve -- "Action: Confirm and re-reserve stock" --> Act1["products/admin.py:confirm_and_re_reserve_stock<br/>Lock products with select_for_update()<br/>Verify all items in stock<br/>If out of stock: report items & abort<br/>If available: decrement stock & mark Paid"]
    AdminResolve -- "Action: Refund via Razorpay" --> Act2["products/admin.py:refund_via_razorpay<br/>Call client.payment.refund(payment_id)<br/>Save refund_id on Order<br/>Mark status='Refunded'"]
```

---

### Use Case 2: OTP Login and Registration

#### Happy Path

```mermaid
sequenceDiagram
    autonumber
    actor User as Customer (Browser)
    participant RegView as products/views.py:register_view
    participant LoginView as products/views.py:login_view
    participant IssueOTP as products/views.py:_issue_otp
    participant Gateway as products/otp_gateway.py:send_otp
    participant VerifyOTP as products/views.py:verify_otp
    participant CartMerge as products/session_cart.py:merge_guest_cart_on_login
    participant DB as PostgreSQL (DB)

    alt Registration Path
        User->>RegView: POST /register/ (username, email, phone, dob)
        Note over RegView: Rate limit: 5/m per IP
        RegView->>DB: Check unique username & email
        RegView->>DB: BEGIN TRANSACTION (transaction.atomic)
        RegView->>DB: User.objects.create(username, email, unusable_password)
        RegView->>DB: CustomerProfile.objects.create(user, email, phone, ...)
        RegView->>DB: COMMIT TRANSACTION
        RegView->>IssueOTP: _issue_otp(profile)
    else Login Path
        User->>LoginView: POST /login/ (email)
        Note over LoginView: Rate limit: 5/m per IP
        LoginView->>DB: CustomerProfile.objects.get(email=email)
        LoginView->>IssueOTP: _issue_otp(profile)
    end

    activate IssueOTP
    IssueOTP->>DB: profile.otp_tokens.filter(is_used=False).update(is_used=True)
    IssueOTP->>DB: OTPToken.objects.create(token=randbelow(900000)+100000, exp=now()+5m)
    IssueOTP->>Gateway: send_otp(email, token)
    Gateway->>Gateway: django.core.mail.send_mail(subject, otp, from_email, [email])
    Gateway-->>IssueOTP: True (sent successfully)
    IssueOTP-->>User: 302 Redirect to /verify/<email>/
    deactivate IssueOTP

    User->>VerifyOTP: POST /verify/<email>/ (otp="123456")
    activate VerifyOTP
    Note over VerifyOTP: Rate limit: 10/m per IP
    VerifyOTP->>DB: Fetch active OTPToken (is_used=False)
    VerifyOTP->>VerifyOTP: Check token == submitted and is_valid()
    VerifyOTP->>DB: OTPToken.update(is_used=True)
    VerifyOTP->>DB: CustomerProfile.update(is_verified=True)
    VerifyOTP->>VerifyOTP: django.contrib.auth.login(request, user)
    VerifyOTP->>CartMerge: merge_guest_cart_on_login(request.session, user)
    CartMerge->>DB: Fold session guest_cart items into DB Cart
    VerifyOTP-->>User: 302 Redirect to / (Welcome Toast)
    deactivate VerifyOTP
```

#### Failure Paths
- **Failure B1: Rate Limit Blocked (`products/views.py:326, 387, 413`):** IP exceeds 5/min on register/login or 10/min on verify; returns HTTP 403 Forbidden via `django-ratelimit (block=True)`.
- **Failure B2: Duplicate Email on Register (`products/views.py:342`):** `CustomerProfile.objects.filter(email=email).exists()` is true; re-renders form with error "This email is already registered."
- **Failure B3: Unregistered Email on Login (`products/views.py:398`):** `CustomerProfile.DoesNotExist` caught; redirects to `/register/` with toast.
- **Failure B4: Resend Cooldown (`products/views.py:372`):** Token created $<60$ seconds ago (`OTPToken.RESEND_COOLDOWN_SECONDS`); returns notice with remaining seconds without dispatching duplicate email.
- **Failure B5: SMTP Outage (`products/otp_gateway.py:37`):** `send_mail` throws exception; logged as error, view returns "Failed to send OTP. Please try again later."
- **Failure B6: Invalid OTP Submission (`products/views.py:438`):** Increments `otp_obj.attempts += 1`. If attempts $<5$, re-renders with remaining attempt count.
- **Failure B7: Max Attempts Exceeded (`products/views.py:441`):** `attempts >= 5`. Burns token (`otp_obj.is_used = True`), redirects to `/login/` with "Too many incorrect attempts."
- **Failure B8: Expired OTP Token (`products/views.py:420`):** Submitted after 5 minutes; `is_valid()` returns `False`, redirects to `/login/`.

---

### Use Case 3: Cart Merge on Login

#### Happy Path

```mermaid
sequenceDiagram
    autonumber
    actor Guest as Anonymous Guest
    participant ViewAdd as products/views.py:add_to_cart
    participant SessionCart as products/session_cart.py
    participant AuthVerify as products/views.py:verify_otp
    participant DB as PostgreSQL (DB)

    Guest->>ViewAdd: POST /add-to-cart/<product_id>/ (selected_size)
    ViewAdd->>SessionCart: add_item(request.session, product, size, qty=1)
    SessionCart->>SessionCart: Write to session['guest_cart'][f"{product_id}:{size}"]
    SessionCart->>SessionCart: session.modified = True

    Guest->>AuthVerify: Completes OTP Verification
    AuthVerify->>SessionCart: merge_guest_cart_on_login(request.session, user)
    activate SessionCart
    SessionCart->>SessionCart: items = get_items(session)
    SessionCart->>DB: Cart.objects.get_or_create(user=user)
    loop For each item in guest_cart
        SessionCart->>DB: Product.objects.get(pk=item['product_id'])
        SessionCart->>DB: Check if cart.items.filter(product=p, selected_size=s).first()
        alt Item already in DB Cart
            SessionCart->>DB: existing.quantity += entry['quantity']<br/>existing.save(update_fields=['quantity'])
        else New Item in DB Cart
            SessionCart->>DB: CartItem.objects.create(cart, product, size, qty, price)
        end
    end
    SessionCart->>SessionCart: clear(session) -> session['guest_cart'] = {}
    SessionCart-->>AuthVerify: Merge Complete
    deactivate SessionCart
```

#### Failure Paths
- **Failure C1: Orphaned Product ID (`products/session_cart.py:98`):** If a product is deleted while held in an anonymous session, `Product.DoesNotExist` is caught and skipped (`continue`), preserving remaining valid items.
- **Failure C2: Empty Session Cart (`products/session_cart.py:92`):** Returns immediately without DB operations.
- **Failure C3: Stock Ceiling Deferred:** `merge_guest_cart_on_login` does not query `Product.stock`. Stock limits are enforced at checkout in `products/views.py:save_order` via `select_for_update()`.

---

### Use Case 4: Delhivery Shipment Creation and Tracking

#### Happy Path (Public Tracking & Admin Slip Generation)

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Customer / Guest
    participant TrackView as products/views.py:track_order
    participant DelhiveryClient as products/delhivery.py:track_shipment
    participant DelhiveryAPI as Delhivery REST API (/api/v1/packages/json/)
    participant DB as PostgreSQL (DB)

    Customer->>TrackView: GET /track/?q=RASAYAM-42&verify=customer@domain.com
    activate TrackView
    Note over TrackView: Rate limit: 30/m per IP
    TrackView->>DB: Order.objects.get(id=42)
    TrackView->>TrackView: Authorization Check (user match OR email/phone match)
    TrackView->>DB: Retrieve order_obj.delhivery_waybill
    TrackView->>DelhiveryClient: track_shipment(waybill)
    activate DelhiveryClient
    DelhiveryClient->>DelhiveryAPI: GET /api/v1/packages/json/?waybill={waybill}
    DelhiveryAPI-->>DelhiveryClient: JSON (status, scans, destination, expected date)
    DelhiveryClient-->>TrackView: Parsed dict (success=True, scans=[...], status='In Transit')
    deactivate DelhiveryClient
    TrackView-->>Customer: Render products/track_order.html with timeline
    deactivate TrackView
```

#### Failure Paths
- **Failure D1: Invalid / Unserviceable Pincode (`products/views.py:1205`):** Non-6 digit pincode returns HTTP 400. Unserviceable code returns `{'serviceable': False}`.
- **Failure D2: Delhivery API Timeout (`products/delhivery.py:72, 136`):** `requests.RequestException` caught after 15s timeout; logs error, returns fallback dictionary `{'success': False, 'error': str(exc)}`.
- **Failure D3: Order Enumeration Prevented (`products/views.py:1162`):** Guest querying Order ID without registered phone/email verification parameter receives `{'need_verification': True}`, preventing PII leakage.
- **Failure D4: Unshipped Order (`products/views.py:1171`):** Valid order with empty `delhivery_waybill` returns "Order has not been shipped yet."
- **Status of `create_shipment` (Dormant):**
  - **Code Reality:** `products/delhivery.py:create_shipment(order)` formats a payload for Delhivery's `/api/cmu/create.json` endpoint, but has **zero active callers** across views, admin actions, or management commands.
  - **Production Reality:** Administrators assign `delhivery_waybill` manually via `products/admin.py:OrderAdmin`.
  - **Open Decision:** Adding a `"Create Delhivery Manifest"` admin action to invoke `create_shipment` and auto-assign the waybill is pending confirmation.

---

### Use Case 5: Admin Packing Slip Flow

#### Happy Path

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Staff / Admin
    participant AdminAction as products/admin.py:download_packing_slip
    participant SlipView as products/views.py:admin_packing_slip
    participant DelhiveryClient as products/delhivery.py:get_packing_slip
    participant DelhiveryAPI as Delhivery REST API (/api/p/packing_slip)
    participant DB as PostgreSQL (DB)

    Admin->>AdminAction: Select 1 order in Admin -> "Download Packing Slip"
    AdminAction->>SlipView: 302 Redirect to /admin-packing-slip/<order_id>/
    activate SlipView
    SlipView->>SlipView: Check request.user.is_staff
    SlipView->>DB: Order.objects.get(id=order_id)
    SlipView->>SlipView: Verify order.delhivery_waybill is present
    SlipView->>DelhiveryClient: get_packing_slip(order.delhivery_waybill)
    activate DelhiveryClient
    DelhiveryClient->>DelhiveryAPI: GET /api/p/packing_slip?wbns={waybill}
    DelhiveryAPI-->>DelhiveryClient: JSON (packages_found=1, packages=[{barcode, consignee...}])
    DelhiveryClient-->>SlipView: Return dict with package details
    deactivate DelhiveryClient
    SlipView-->>Admin: Render products/packing_slip.html (printable layout)
    deactivate SlipView
```

#### Failure Paths
- **Failure E1: Non-Staff Access (`products/views.py:1306`):** Redirects unauthorized users to `index` (`/`).
- **Failure E2: Missing Waybill (`products/views.py:1310`):** Redirects admin to order change page with message `"This order does not have a Delhivery waybill assigned yet."`
- **Failure E3: Multi-Select Warning (`products/admin.py:192`):** Selecting $>1$ order shows admin warning `"Please select only one order to download the slip at a time."`
- **Failure E4: Delhivery API Error (`products/delhivery.py:327`):** Returns `{'packages_found': 0, 'error': ...}`, rendered gracefully without an unhandled 500 error.

---

## 3. Data Classification & Boundaries

### Data Stores (Data Held Internally)

| Store / Component | Model / Data Structure | Fields & PII Held | Retention & Privacy Scope |
| :--- | :--- | :--- | :--- |
| **PostgreSQL** | `CustomerProfile` (`products/models.py:5`) | Email, phone, city, state, gender, date_of_birth, `is_verified`. | Permanent until user deletion. |
| **PostgreSQL** | `User` (Django `auth_user`) | Username, email, first/last name, unusable password hash, login time. | Permanent account record. |
| **PostgreSQL** | `Address` (`products/models.py:20`) | Full name, phone, pincode, flat/building, street, landmark, city, state, default flag. | Permanent until modified by user. |
| **PostgreSQL** | `Order` (`products/models.py:195`) | User FK, total_amount, status (`Pending`, `Paid`, `Cancelled`, `Payment Review`, `Refunded`), shipping address text, `original_cart_items` JSON (product, size, qty, price), `transaction_id`, `razorpay_order_id`, `razorpay_payment_id`, `razorpay_signature`, `refund_id`, `delhivery_waybill`, `delhivery_shipment_status`. | Permanent financial record. Pending orders cancelled after 20m. Late captures held under `Payment Review`. |
| **PostgreSQL** | `OTPToken` (`products/models.py:74`) | Profile FK, plaintext 6-digit token, `created_at`, `expires_at`, `is_used`, `attempts`. | Single live token per profile; expires in 5m. |
| **PostgreSQL** | `Cart` & `CartItem` (`products/models.py:241`) | User FK, product FK, selected size, quantity, unit price. | Cleared on successful checkout. |
| **Session Store** | `request.session['guest_cart']` (`products/session_cart.py:14`) | Dictionary of `{product_id}:{size}` $\rightarrow$ `{product_id, size, quantity, price}`. | Cleared on login merge or session expiry. |
| **Cache Engine** | `delhivery_pin_{pincode}`, `ratelimit:*` | Delhivery serviceability response (city, state, prepaid/cod, 24h TTL). Rate limit attempt counters. | Auto-expiring TTLs. No customer PII cached. |

### External Services (Data Leaving the System)

```mermaid
flowchart LR
    subgraph RasayamCore["Rasayam Core System"]
        OrderData["Order & Address Data"]
        AuthData["Customer Email & OTP"]
        PincodeQuery["Pincode Query"]
    end

    subgraph RazorpayGateway["Razorpay Payments"]
        RZP_Data["• Order Amount (paise)<br/>• Currency (INR)<br/>• Receipt ('rasayam_{order_id}')<br/>• Prefill Email & Phone (Browser Modal)<br/>• Refund Payment ID & Amount<br/><b>Card/UPI PINs NEVER enter Rasayam</b>"]
    end

    subgraph DelhiveryGateway["Delhivery Logistics"]
        DLV_Data["• Consignee Name & Full Shipping Address<br/>• Consignee Phone Number<br/>• Destination Pincode, City, State<br/>• Product Description & Quantities<br/>• Order Invoice Reference ('INV-{order_id}')"]
    end

    subgraph EmailProvider["SMTP Gateway (AWS SES)"]
        SES_Data["• Recipient Email Address<br/>• 6-digit OTP Token<br/>• Expiry Notice (5 minutes)"]
    end

    OrderData -->|save_order / payment.html / refund_via_razorpay| RazorpayGateway
    OrderData -->|create_shipment payload / track_order| DelhiveryGateway
    AuthData -->|send_otp via send_mail| EmailProvider
    PincodeQuery -->|pincode_check_api| DelhiveryGateway
```

---

## 4. Idempotency, Concurrency & State Invariants

### 1. Webhook Deduplication & Payment Review
- **Endpoint:** `products/views.py:razorpay_webhook`
- **Locking & Atomic Scope:**
  ```python
  with transaction.atomic():
      order = Order.objects.select_for_update().get(razorpay_order_id=razorpay_order_id)
      if order.is_paid or order.status == 'Payment Review':
          return JsonResponse({'status': 'ok'})
      if order.status == 'Cancelled':
          order.status = 'Payment Review'
          order.razorpay_payment_id = payment_id
          order.transaction_id = payment_id
          if amount_decimal is not None:
              order.total_amount = amount_decimal
          order.save(update_fields=['status', 'razorpay_payment_id', 'transaction_id', 'total_amount'])
          return JsonResponse({'status': 'payment_review'})
      order.is_paid = True
      order.status = 'Paid'
      ...
  ```
- **Idempotency Guarantees:**
  - Repeated deliveries for an order already `Paid` return HTTP 200 without duplicate execution.
  - Repeated deliveries for an order already in `Payment Review` return HTTP 200 without changing state.
  - Late captures arriving for `Cancelled` orders are intercepted before any stock mutations occur, moving safely to `Payment Review`.

### 2. Browser Verification Path (`payment_verify`)
- **Endpoint:** `products/views.py:payment_verify`
- **Mechanism:** Acquires row lock via `select_for_update()`. If `order.status == 'Cancelled'`, sets status to `'Payment Review'`, records payment credentials, and renders `products/payment_review.html` informing the customer that inventory is being verified by the concierge team.

### 3. Stock Locking & Recovery Concurrency
- **Checkout Reservation (`products/views.py:save_order`):** Product rows locked with `select_for_update()` inside `transaction.atomic()`. Concurrent requests serialize at the DB row level, preventing overselling.
- **Stock Recovery (`products/management/commands/cancel_expired_orders.py`):** Pending orders older than 20 minutes locked with `select_for_update()`. Evaluates `if order.status == 'Pending':` before restoring stock via `F('stock') + quantity` and marking `Cancelled`.
- **Elimination of Race Condition:** Because `razorpay_webhook` and `payment_verify` also lock the order row with `select_for_update()`, a late capture can never interleave with the cleanup job. If cleanup commits first, the capture sees `status == 'Cancelled'` and transitions to `Payment Review` rather than `Paid`.

### 4. Admin Action Concurrency & Safety
- **Action 1: "Confirm and re-reserve stock" (`products/admin.py:OrderAdmin.confirm_and_re_reserve_stock`):**
  - Evaluates `if order.is_paid or order.status == 'Paid':` (idempotent skip).
  - Inside `transaction.atomic()`, locks `Product` rows with `select_for_update()`.
  - Verifies stock for all snapshot items. If any item is insufficient, reports the exact item name, requested quantity, and available quantity via admin error message and aborts without partial deductions.
  - If all items available, decrements stock and sets `is_paid = True, status = 'Paid'`.
- **Action 2: "Refund via Razorpay" (`products/admin.py:OrderAdmin.refund_via_razorpay`):**
  - Evaluates `if order.status == 'Refunded' or order.refund_id:` (idempotent skip).
  - Invokes `client.payment.refund(order.razorpay_payment_id, {'amount': paise})`.
  - Stores `order.refund_id = refund_id` and sets `status = 'Refunded'`.

---

## 5. Open Questions & Infrastructure To Confirm

1. **Redis Cache Configuration in Production:**
   - [`settings.py:181-200`](file:///C:/Users/debab/OneDrive/Desktop/Rasayam-org-git-developer/Rasayam-website/Rasayam_website/settings.py#L181-L200) falls back to `LocMemCache` if `REDIS_URL` is unset.
   - Under multi-worker Gunicorn (2 workers), `LocMemCache` isolates memory per worker process, causing rate limit counters (`@ratelimit`) to be evaluated per-worker rather than globally.
   - *Confirmation needed:* Confirm whether Redis is provisioned and `REDIS_URL` is defined in the production `.env`.

2. **Crontab Execution Schedule on Production Host:**
   - The stock recovery command is tested and verified at `products/management/commands/cancel_expired_orders.py`.
   - *Confirmation needed:* Confirm that the crontab entry on the EC2 host (`*/10 * * * *`) is active and whether a centralized runner (Celery Beat or AWS EventBridge) should be configured.

3. **SMTP Provider & DNS Delivery Records:**
   - `settings.py:458-468` reads `EMAIL_HOST` and credentials from environment variables.
   - *Confirmation needed:* Confirm the active production SMTP provider (AWS SES Mumbai `email-smtp.ap-south-1.amazonaws.com` vs other) and verify that SPF, DKIM, and DMARC DNS records are active for `admin@rasayamglobal.com` to prevent OTP codes landing in spam.

4. **"Create Delhivery Manifest" Admin Action Decision:**
   - `products/delhivery.py:create_shipment` is dormant with no callers in views or admin.
   - *Open Decision:* Should we wire up a `"Create Delhivery Manifest"` admin action in `OrderAdmin` to automatically dispatch shipments to Delhivery's CMU API and record the assigned waybill, or should admin staff continue manual waybill entry?
