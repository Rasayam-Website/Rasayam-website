import json
import hmac
import hashlib
import secrets
import razorpay
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Q, F
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django_ratelimit.decorators import ratelimit
from .models import (
    Product, Banner, Category, PromoBox,
    CustomerProfile, ContactInquiry, Order, OrderItem, Review,
    Cart, CartItem,
    Wishlist, WishlistItem,
    OTPToken,
)
from .otp_gateway import send_otp
from . import session_cart as guest_cart

class GuestCartItem:
    def __init__(self, product, size, quantity, price):
        self.product = product
        self.selected_size = size
        self.quantity = quantity
        self._price = Decimal(price)

    @property
    def id(self):
        import zlib
        return zlib.crc32(f"{self.product.id}:{self.selected_size}".encode('utf-8')) & 0x7fffffff

    @property
    def unit_price(self):
        return self._price

    @property
    def total_item_price(self):
        return self.unit_price * self.quantity

def find_guest_item_by_pseudo_id(session, item_id):
    import zlib
    for item in guest_cart.get_items(session):
        pid = item['product_id']
        size = item['size']
        h = zlib.crc32(f"{pid}:{size}".encode('utf-8')) & 0x7fffffff
        if h == item_id:
            return pid, size, item
    return None

def get_selected_size_from_request(request, product):
    selected_size = (
        request.POST.get('selected_size')
        or request.GET.get('selected_size')
        or ''
    ).strip()

    if selected_size and product.sizes.filter(name=selected_size).exists():
        return selected_size

    return ''


def add_product_to_cart(cart, product, selected_size=''):
    cart_item = cart.items.filter(
        product=product,
        selected_size=selected_size,
    ).first()

    if cart_item:
        cart_item.quantity += 1
        cart_item.save(update_fields=['quantity'])
        return cart_item, False

    return CartItem.objects.create(
        cart=cart,
        product=product,
        selected_size=selected_size,
        price=product.price,  # Store product price at time of adding to cart
    ), True


def get_razorpay_client():
    """Create the Razorpay client only when checkout needs it."""
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise ValueError("Razorpay keys are missing. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to your environment.")
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

# --- 1. Main Display Views ---

@cache_page(60 * 5)  # Cache for 5 minutes
def index(request):
    banners = Banner.objects.filter(active=True).order_by('order')
    categories = Category.objects.all().order_by('order')
    promos = PromoBox.objects.all().order_by('order')[:3]
    # Use prefetch_related to optimize gallery_images loading
    items = Product.objects.all().prefetch_related('gallery_images').select_related('category')[:12]
    
    context = {
        'items': items,
        'banners': banners,
        'categories': categories,
        'promos': promos,
    }
    return render(request, 'products/index.html', context)

@ratelimit(key='ip', rate='30/m', method='GET')  # 30 requests per minute
def shop(request):
    # Get page number from request
    page = request.GET.get('page', 1)
    
    # Optimized query with prefetches
    items_list = Product.objects.all().prefetch_related('gallery_images').select_related('category').order_by('-id')
    
    # Paginate results - 12 items per page
    paginator = Paginator(items_list, 12)
    
    try:
        items = paginator.page(page)
    except PageNotAnInteger:
        items = paginator.page(1)
    except EmptyPage:
        items = paginator.page(paginator.num_pages)
    
    categories = Category.objects.all().order_by('order')
    promos = PromoBox.objects.all().order_by('order')[:3]
    
    cart_product_ids = []
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart_product_ids = list(cart.items.values_list('product_id', flat=True))

    return render(request, 'products/shop.html', {
        'items': items, 
        'categories': categories, 
        'promos': promos,
        'cart_product_ids': cart_product_ids,
        'paginator': paginator,
    })

def about_view(request):
    # Fetch only verified reviews to improve performance
    reviews = Review.objects.filter(
        is_verified=True
    ).select_related('user', 'product').order_by('-id')[:20]  # Limit to recent 20
    return render(request, 'products/about.html', {'reviews': reviews})

def about_us(request):
    return render(request, 'products/about_us.html')

@ratelimit(key='ip', rate='10/m', method='POST')  # Rate limit POST requests
def contact(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        ContactInquiry.objects.create(
            full_name=full_name,
            email=email,
            subject=subject,
            message=message
        )
        messages.success(
            request,
            "Your inquiry has been sent to the Rasayam concierge.",
            extra_tags="contact",
        )
        return redirect('contact') 

    return render(request, 'products/contact.html')

def cart(request):
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        # Optimize query by using select_related and prefetch_related
        cart_items = cart.items.select_related('product').prefetch_related('product__gallery_images').all()
        total_price = sum(item.total_item_price for item in cart_items)
    else:
        session_items = guest_cart.get_items(request.session)
        product_ids = [item['product_id'] for item in session_items]
        products = {p.id: p for p in Product.objects.filter(id__in=product_ids).prefetch_related('gallery_images')}
        cart_items = []
        for item in session_items:
            prod = products.get(item['product_id'])
            if prod:
                cart_items.append(GuestCartItem(
                    product=prod,
                    size=item['size'],
                    quantity=item['quantity'],
                    price=item['price']
                ))
        total_price = sum(item.total_item_price for item in cart_items)

    recommended_items = Product.objects.all().exclude(category__isnull=True).select_related('category').order_by('?')[:4]
    
    context = {
        'cart_items': cart_items,
        'total_price': total_price,
        'recommended_items': recommended_items,
    }
    return render(request, 'products/cart.html', context)

# --- 2. Product & Category Logic ---

def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    
    # Pagination for category products
    page = request.GET.get('page', 1)
    products_list = Product.objects.filter(
        category=category
    ).prefetch_related('gallery_images').select_related('category').order_by('-id')
    
    paginator = Paginator(products_list, 12)
    try:
        products = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        products = paginator.page(1)
    
    return render(request, 'products/category_detail.html', {
        'category': category,
        'products': products,
        'paginator': paginator,
    })

def product_detail_view(request, pk):
    """Product Detail with Gallery and Sizes - Optimized query"""
    # Use select_related and prefetch_related for optimal performance
    product = get_object_or_404(
        Product.objects.select_related('category').prefetch_related(
            'gallery_images',
            'sizes',
        ),
        pk=pk
    )
    # Get recent reviews separately without slicing in prefetch
    reviews = product.reviews.select_related('user').order_by('-created_at')[:10]
    
    # Process highlights for list display
    highlights_list = product.highlights.split('\n') if product.highlights else []

    return render(request, 'products/product_detail.html', {
        'product': product,
        'reviews': reviews,
        'highlights_list': highlights_list
    })

def product_detail_view_slug(request, slug):
    """Product Detail by Slug (SEO-friendly URL) - Optimized query"""
    # Use select_related and prefetch_related for optimal performance
    product = get_object_or_404(
        Product.objects.select_related('category').prefetch_related(
            'gallery_images',
            'sizes',
        ),
        slug=slug
    )
    # Get recent reviews separately without slicing in prefetch
    reviews = product.reviews.select_related('user').order_by('-created_at')[:10]
    
    # Process highlights for list display
    highlights_list = product.highlights.split('\n') if product.highlights else []

    return render(request, 'products/product_detail.html', {
        'product': product,
        'reviews': reviews,
        'highlights_list': highlights_list
    })

# --- 3. Authentication Views ---

def _issue_otp(profile: CustomerProfile) -> bool:
    """Invalidate any live token and issue a fresh one. Returns True if OTP was sent successfully."""
    profile.otp_tokens.filter(is_used=False).update(is_used=True)
    token = OTPToken.objects.create(
        profile=profile,
        token=str(secrets.randbelow(900000) + 100000),  # cryptographically random 6-digit
        expires_at=timezone.now() + timezone.timedelta(minutes=OTPToken.EXPIRY_MINUTES),
    )
    return send_otp(profile.phone_number, token.token)


@ratelimit(key='ip', rate='5/m', method='POST')
def register_view(request):
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()

        if not phone or not username or not email:
            messages.error(request, "All fields are required.")
            return render(request, 'products/register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username is already taken.")
            return render(request, 'products/register.html')

        if CustomerProfile.objects.filter(phone_number=phone).exists():
            messages.error(request, "This phone number is already registered.")
            return render(request, 'products/register.html')

        with transaction.atomic():
            user = User.objects.create(username=username, email=email)
            user.set_unusable_password()
            user.save()

            profile = CustomerProfile.objects.create(
                user=user,
                phone_number=phone,
                email=email,
                gender=request.POST.get('gender', ''),
                city=request.POST.get('city', ''),
            )

        success = _issue_otp(profile)
        if not success:
            messages.error(request, "Failed to send OTP. Please try again later.")
            return redirect('register')
        return redirect('verify_otp', phone_number=phone)

    return render(request, 'products/register.html')


@ratelimit(key='ip', rate='5/m', method='POST')
def login_view(request):
    if request.method == 'POST':
        phone = request.POST.get('phone_number', '').strip()
        try:
            profile = CustomerProfile.objects.get(phone_number=phone)
        except CustomerProfile.DoesNotExist:
            messages.error(request, "This phone number isn't registered yet.")
            return redirect('register')
        except CustomerProfile.MultipleObjectsReturned:
            profile = CustomerProfile.objects.filter(phone_number=phone).first()

        success = _issue_otp(profile)
        if not success:
            messages.error(request, "Failed to send OTP. Please try again later.")
            return redirect('login')
        return redirect('verify_otp', phone_number=phone)

    return render(request, 'products/login.html')


@ratelimit(key='ip', rate='10/m', method='POST')
def verify_otp(request, phone_number):
    profile = get_object_or_404(CustomerProfile, phone_number=phone_number.strip())
    otp_obj = profile.otp_tokens.filter(is_used=False).first()

    if request.method == 'POST':
        # Guard: no active token at all
        if not otp_obj or not otp_obj.is_valid():
            messages.error(request, "OTP expired or already used. Request a new one.")
            return redirect('login')

        submitted = request.POST.get('otp', '').strip()

        # Check the token first
        if submitted == otp_obj.token:
            otp_obj.is_used = True
            otp_obj.save(update_fields=['is_used'])
            profile.is_verified = True
            profile.save(update_fields=['is_verified'])
            login(request, profile.user)
            guest_cart.merge_guest_cart_on_login(request.session, profile.user)
            messages.success(request, f"Welcome, {profile.user.username}!")
            return redirect('index')

        # Increment attempts only on incorrect submission
        otp_obj.attempts += 1
        otp_obj.save(update_fields=['attempts'])

        if otp_obj.attempts >= OTPToken.MAX_ATTEMPTS:
            otp_obj.is_used = True
            otp_obj.save(update_fields=['is_used'])
            messages.error(request, "Too many incorrect attempts. Please request a new code.")
            return redirect('login')

        remaining = OTPToken.MAX_ATTEMPTS - otp_obj.attempts
        return render(request, 'products/verify_otp.html', {
            'phone': phone_number,
            'error': f"Incorrect code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.",
        })

    return render(request, 'products/verify_otp.html', {'phone': phone_number})


@require_POST
@ratelimit(key='ip', rate='3/m', method='POST')
def resend_otp(request, phone_number):
    """Issues a new OTP, subject to a per-token cooldown to prevent spamming."""
    profile = get_object_or_404(CustomerProfile, phone_number=phone_number.strip())
    latest = profile.otp_tokens.first()

    if latest:
        elapsed = (timezone.now() - latest.created_at).total_seconds()
        if elapsed < OTPToken.RESEND_COOLDOWN_SECONDS:
            wait = int(OTPToken.RESEND_COOLDOWN_SECONDS - elapsed)
            messages.error(request, f"Please wait {wait}s before requesting a new code.")
            return redirect('verify_otp', phone_number=phone_number)

    success = _issue_otp(profile)
    if success:
        messages.success(request, "A new code has been sent.")
    else:
        messages.error(request, "Failed to send OTP. Please try again later.")
    return redirect('verify_otp', phone_number=phone_number)


def logout_view(request):
    logout(request)
    request.session.flush()
    return redirect('index')

@login_required
def profile_view(request):
    # We only want to show orders that were successfully completed
    orders = request.user.orders.filter(is_paid=True).order_by('-created_at')
    order_count = orders.count()

    if order_count == 0:
        customer_badge = 'New Welcome'
    elif order_count < 4:
        customer_badge = 'Regular Customer'
    else:
        customer_badge = 'Loyal Customer'

    context = {
        'orders': orders,
        'customer_badge': customer_badge,
        'is_staff_portal_user': request.user.is_active and request.user.is_staff,
    }
    return render(request, 'products/profile.html', context)

# --- 4. Order & Cart Processing (with Razorpay) ---

@login_required
@ratelimit(key='user', rate='10/h', method='POST')
def save_order(request):
    """
    Converts the active cart into a pending order and opens a Razorpay payment session.

    Stock deduction happens inside transaction.atomic() with select_for_update() so
    concurrent requests are serialised at the DB row level — the second request will
    see the already-decremented stock and return an Out of Stock error instead of
    overselling.
    """
    shipping_address = request.POST.get('shipping_address', '').strip()

    cart = get_object_or_404(Cart, user=request.user)
    cart_items = list(cart.items.select_related('product').prefetch_related('product__sizes'))

    if not cart_items:
        messages.error(request, "Your bag is empty.")
        return redirect('shop')

    try:
        razorpay_client = get_razorpay_client()
    except ValueError as e:
        messages.error(request, f"Gateway Error: {e}")
        return redirect('cart')

    # ── Atomic block: validate sizes, check & deduct stock, create order ──────
    try:
        with transaction.atomic():
            # Lock every product row involved in this order for the duration of
            # the transaction. Any concurrent checkout for the same products will
            # block here until this transaction commits or rolls back.
            product_ids = [item.product_id for item in cart_items]
            locked_products = {
                p.pk: p
                for p in Product.objects.select_for_update().filter(pk__in=product_ids)
            }

            original_cart_items = []
            for item in cart_items:
                product = locked_products[item.product_id]

                # Size still available?
                if item.selected_size and not product.sizes.filter(name=item.selected_size).exists():
                    raise ValueError(f"Size {item.selected_size} for '{product.name}' is no longer available.")

                # Enough stock?
                if product.stock < item.quantity:
                    available = product.stock
                    raise ValueError(
                        f"Only {available} unit{'s' if available != 1 else ''} of "
                        f"'{product.name}' left in stock."
                    )

                product.stock -= item.quantity
                product.save(update_fields=['stock'])

                original_cart_items.append({
                    'cart_item_id': item.id,
                    'product_id': product.pk,
                    'product_name': product.name,
                    'selected_size': item.selected_size,
                    'quantity': item.quantity,
                    'price': str(item.unit_price),
                })

            total_amount = sum(item.total_item_price for item in cart_items)
            order = Order.objects.create(
                user=request.user,
                total_amount=total_amount,
                status='Pending',
                shipping_address=shipping_address,
                original_cart_items=original_cart_items,
            )
            for item in cart_items:
                product = locked_products[item.product_id]
                OrderItem.objects.create(
                    order=order,
                    product_name=product.name,
                    selected_size=item.selected_size,
                    price=item.unit_price,
                    quantity=item.quantity,
                    image_url=product.image.url if product.image else '',
                )

    except ValueError as stock_error:
        messages.error(request, str(stock_error))
        return redirect('cart')

    # ── Create Razorpay order (outside the DB transaction — network call) ─────
    amount_in_paise = int(order.total_amount * 100)
    try:
        razorpay_order = razorpay_client.order.create(data={
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": f"rasayam_{order.id}",
        })
        order.razorpay_order_id = razorpay_order['id']
        order.save(update_fields=['razorpay_order_id'])
    except Exception as e:
        # Order was created but gateway failed — restore stock and delete order.
        with transaction.atomic():
            snapshot = order.original_cart_items or []
            for entry in snapshot:
                product_id = entry.get('product_id')
                quantity = int(entry.get('quantity') or 0)
                if product_id and quantity > 0:
                    Product.objects.filter(pk=product_id).update(
                        stock=F('stock') + quantity
                    )
        order.delete()
        messages.error(request, f"Payment gateway error: {e}")
        return redirect('cart')

    return render(request, 'products/payment.html', {
        'order': order,
        'razorpay_order_id': razorpay_order['id'],
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'amount': amount_in_paise,
    })


def clear_paid_cart_items(cart, order):
    """Remove only the cart quantities that were captured for this order."""
    snapshot = order.original_cart_items or []

    if snapshot:
        for entry in snapshot:
            cart_item = cart.items.filter(id=entry.get('cart_item_id')).first()
            if not cart_item:
                continue

            if (
                cart_item.product_id != entry.get('product_id')
                or cart_item.selected_size != entry.get('selected_size', '')
            ):
                continue

            paid_quantity = int(entry.get('quantity') or 0)
            if paid_quantity <= 0:
                continue

            if cart_item.quantity > paid_quantity:
                cart_item.quantity -= paid_quantity
                cart_item.save(update_fields=['quantity'])
            else:
                cart_item.delete()
        return

    # Backward-compatible fallback for pending orders created before snapshots existed.
    for order_item in order.items.all():
        cart_item = cart.items.filter(
            product__name=order_item.product_name,
            selected_size=order_item.selected_size
        ).first()
        if not cart_item:
            continue

        if cart_item.quantity > order_item.quantity:
            cart_item.quantity -= order_item.quantity
            cart_item.save(update_fields=['quantity'])
        else:
            cart_item.delete()


@login_required
def payment_verify(request):
    """Verifies Razorpay Signature and finalizes transaction"""
    if request.method == "POST":
        try:
            payment_id = request.POST.get('razorpay_payment_id')
            razorpay_order_id = request.POST.get('razorpay_order_id')
            signature = request.POST.get('razorpay_signature')

            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }

            # 1. Security Check: Verify the signature from Razorpay
            razorpay_client = get_razorpay_client()
            razorpay_client.utility.verify_payment_signature(params_dict)

            # 2. Update the Order in your database
            order = Order.objects.get(razorpay_order_id=razorpay_order_id, user=request.user)
            order.razorpay_payment_id = payment_id
            order.razorpay_signature = signature
            order.is_paid = True
            order.status = 'Paid'
            order.save()

            # 3. SUCCESS: Clear only the items from this completed order
            cart = Cart.objects.get(user=request.user)
            clear_paid_cart_items(cart, order)

            messages.success(request, "Payment verified! Your order is being prepared.")
            return redirect('payment_success', order_id=order.id)

        except Exception as e:
            # 4. FAILURE: Verification failed or signature was invalid
            print("Verification Error:", str(e))
            
            # Note: Because 'save_order' no longer deletes the cart, 
            # the user can come back here, and their items will still be there.
            return redirect('payment_fail')
            
    return redirect('shop')


@csrf_exempt
def razorpay_webhook(request):
    """
    Razorpay server-to-server webhook receiver.

    Security: CSRF exemption is intentional — this endpoint is called by
    Razorpay's servers which have no CSRF cookie. Authentication is provided
    entirely by HMAC-SHA256 signature verification against RAZORPAY_WEBHOOK_SECRET.

    Razorpay Dashboard → Settings → Webhooks → Add new endpoint:
      URL : https://rasayam.com/webhooks/razorpay/
      Events: payment.captured
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not webhook_secret:
        return JsonResponse({'error': 'Webhook secret not configured'}, status=500)

    # 1. Verify HMAC-SHA256 signature
    received_sig = request.headers.get('X-Razorpay-Signature', '')
    body = request.body
    expected_sig = hmac.new(
        webhook_secret.encode('utf-8'),
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, received_sig):
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    # 2. Parse event
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    event = payload.get('event')
    if event != 'payment.captured':
        # Acknowledge unhandled events without error so Razorpay stops retrying
        return JsonResponse({'status': 'ignored'})

    # 3. Flip order to Paid
    try:
        payment_entity = payload['payload']['payment']['entity']
        razorpay_order_id = payment_entity.get('order_id')
        payment_id = payment_entity.get('id')

        order = Order.objects.get(razorpay_order_id=razorpay_order_id)
        if not order.is_paid:
            order.is_paid = True
            order.status = 'Paid'
            order.razorpay_payment_id = payment_id
            order.transaction_id = payment_id  # populate unique transaction_id
            order.save(update_fields=['is_paid', 'status', 'razorpay_payment_id', 'transaction_id'])
    except (Order.DoesNotExist, KeyError):
        # Return 200 so Razorpay doesn't keep retrying for unknown orders
        return JsonResponse({'status': 'order_not_found'})

    return JsonResponse({'status': 'ok'})


@login_required
def order_detail_view(request, order_id):    # This prevents users from accessing an unpaid order detail page via a direct URL
    order = get_object_or_404(Order, id=order_id, user=request.user, is_paid=True)
    return render(request, 'products/order_detail.html', {'order': order})

def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    selected_size = get_selected_size_from_request(request, product)
    
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        add_product_to_cart(cart, product, selected_size)
    else:
        guest_cart.add_item(request.session, product, selected_size)
    
    messages.success(request, f"{product.name} added to Selection.")
    if request.POST.get('buy_now'):
        return redirect('cart')
    return redirect(request.META.get('HTTP_REFERER', 'shop'))


def decrease_cart_item(request, item_id):
    if request.user.is_authenticated:
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
            messages.info(request, "Item quantity updated.")
        else:
            cart_item.delete()
            messages.info(request, "Item removed.")
    else:
        found = find_guest_item_by_pseudo_id(request.session, item_id)
        if found:
            pid, size, item = found
            new_qty = item['quantity'] - 1
            if new_qty > 0:
                guest_cart.update_item(request.session, pid, size, new_qty)
                messages.info(request, "Item quantity updated.")
            else:
                guest_cart.remove_item(request.session, pid, size)
                messages.info(request, "Item removed.")
        else:
            messages.error(request, "Item not found in your bag.")
    return redirect('cart')


def remove_from_cart(request, item_id):
    if request.user.is_authenticated:
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        cart_item.delete()
        messages.info(request, "Item removed.")
    else:
        found = find_guest_item_by_pseudo_id(request.session, item_id)
        if found:
            pid, size, _ = found
            guest_cart.remove_item(request.session, pid, size)
            messages.info(request, "Item removed.")
        else:
            messages.error(request, "Item not found in your bag.")
    return redirect('cart')


@ratelimit(key='ip', rate='30/m', method='POST')  # Prevent spam adds (use IP to include guests)
def add_to_cart_ajax(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    selected_size = get_selected_size_from_request(request, product)
    
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        add_product_to_cart(cart, product, selected_size)
        total_count = sum(item.quantity for item in cart.items.all())
    else:
        guest_cart.add_item(request.session, product, selected_size)
        total_count = sum(item['quantity'] for item in guest_cart.get_items(request.session))

    return JsonResponse({
        'status': 'success',
        'cart_count': total_count,
        'selected_size': selected_size,
        'message': f"{product.name} added.",
    })


def cart_detail_api(request):
    """GET /api/cart/ — full cart state as JSON for frontend re-renders."""
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        items = []
        for item in cart.items.select_related('product'):
            items.append({
                'id': item.id,
                'product_id': item.product_id,
                'product_name': item.product.name,
                'selected_size': item.selected_size,
                'quantity': item.quantity,
                'unit_price': str(item.unit_price),
                'total_price': str(item.total_item_price),
                'image_url': item.product.image.url if item.product.image else '',
            })
        total_price = cart.total_price
    else:
        session_items = guest_cart.get_items(request.session)
        product_ids = [item['product_id'] for item in session_items]
        products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}
        items = []
        import zlib
        for item in session_items:
            prod = products.get(item['product_id'])
            if prod:
                unit_price = Decimal(item['price'])
                qty = item['quantity']
                pseudo_id = zlib.crc32(f"{prod.id}:{item['size']}".encode('utf-8')) & 0x7fffffff
                items.append({
                    'id': pseudo_id,
                    'product_id': prod.id,
                    'product_name': prod.name,
                    'selected_size': item['size'],
                    'quantity': qty,
                    'unit_price': str(unit_price),
                    'total_price': str(unit_price * qty),
                    'image_url': prod.image.url if prod.image else '',
                })
        total_price = guest_cart.total(request.session)

    return JsonResponse({
        'items': items,
        'total': str(total_price),
        'count': sum(i['quantity'] for i in items),
    })


def update_cart_item(request, item_id):
    """POST /api/cart/update/<id>/ — body: {quantity: int}. 0 removes the item."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        quantity = int(data.get('quantity', 1))
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid payload'}, status=400)

    if request.user.is_authenticated:
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        if quantity <= 0:
            cart_item.delete()
        else:
            cart_item.quantity = quantity
            cart_item.save(update_fields=['quantity'])
        cart = Cart.objects.get(user=request.user)
        total_price = cart.total_price
        total_count = sum(i.quantity for i in cart.items.all())
    else:
        found = find_guest_item_by_pseudo_id(request.session, item_id)
        if found:
            pid, size, _ = found
            if quantity <= 0:
                guest_cart.remove_item(request.session, pid, size)
            else:
                guest_cart.update_item(request.session, pid, size, quantity)
        total_price = guest_cart.total(request.session)
        total_count = sum(item['quantity'] for item in guest_cart.get_items(request.session))

    return JsonResponse({
        'status': 'ok',
        'cart_total': str(total_price),
        'cart_count': total_count,
    })


def remove_cart_item_api(request, item_id):
    """DELETE /api/cart/remove/<id>/"""
    if request.method not in ('POST', 'DELETE'):
        return JsonResponse({'error': 'POST or DELETE required'}, status=405)

    if request.user.is_authenticated:
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        cart_item.delete()
        cart = Cart.objects.get(user=request.user)
        total_price = cart.total_price
        total_count = sum(i.quantity for i in cart.items.all())
    else:
        found = find_guest_item_by_pseudo_id(request.session, item_id)
        if found:
            pid, size, _ = found
            guest_cart.remove_item(request.session, pid, size)
        total_price = guest_cart.total(request.session)
        total_count = sum(item['quantity'] for item in guest_cart.get_items(request.session))

    return JsonResponse({
        'status': 'ok',
        'cart_total': str(total_price),
        'cart_count': total_count,
    })

@login_required
def payment_success(request, order_id):
    """
    Renders the success page after a confirmed transaction.
    """
    # Ensure the user can only see their own order success page
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    context = {
        'order': order,
        'title': 'Thank You for Your Selection'
    }
    return render(request, 'products/payment_success.html', context)

def payment_fail(request):
    """
    Renders the failure page. The cart remains full, allowing 
    the customer to return and try again.
    """
    # We can add a helpful message to guide them back to the cart
    messages.warning(request, "Your payment could not be processed. Your selection is still safe in your bag.")
    
    return render(request, 'products/payment_fail.html', {
        'title': 'Transaction Unsuccessful'
    })

# --- Policy Pages ---
def privacy(request): return render(request, 'products/privacy_policy.html')
def refund(request): return render(request, 'products/refund.html')
def refund_policy(request): return render(request, 'products/refund_policy.html')
def shipping(request): return render(request, 'products/shipping.html')
def shipping_policy(request): return render(request, 'products/shipping_policy.html')
def terms(request): return render(request, 'products/terms.html')
def faq(request):
    return render(request, 'products/faq.html')


@login_required
def get_wishlists(request):
    """Returns a list of the user's wishlists for the Save modal"""
    wishlists = request.user.wishlists.all().values('id', 'name')
    return JsonResponse(list(wishlists), safe=False)

@login_required
def add_to_wishlist(request):
    """Saves a product to a specific or brand new wishlist"""
    if request.method != "POST":
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON payload.'}, status=400)

    product_id = data.get('product_id')
    wishlist_id = data.get('wishlist_id')
    new_name = data.get('new_name')

    if not product_id:
        return JsonResponse({'status': 'error', 'message': 'Product is required.'}, status=400)

    product = get_object_or_404(Product, id=product_id)

    if new_name:
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user, name=new_name)
    elif wishlist_id:
        wishlist = get_object_or_404(Wishlist, id=wishlist_id, user=request.user)
    else:
        return JsonResponse({'status': 'error', 'message': 'Choose a collection or create a new one.'}, status=400)

    WishlistItem.objects.get_or_create(wishlist=wishlist, product=product)
    return JsonResponse({'status': 'success', 'message': f'Saved to {wishlist.name}'})

@login_required
def collections_view(request):
    """Fetches all of the user's named wishlists and the items inside them."""
    # prefetch_related makes loading the images much faster
    user_collections = request.user.wishlists.prefetch_related('items__product').order_by('-created_at')
    return render(request, 'products/collections.html', {'collections': user_collections})

@ratelimit(key='ip', rate='60/m', method='GET')  # Rate limit search requests
def search_view(request):
    query = request.GET.get('q', '').strip()
    results = []
    page = request.GET.get('page', 1)
    paginator = None
    
    if query and len(query) >= 2:  # Require at least 2 characters
        # Optimized search with select_related and prefetch_related
        results_list = Product.objects.filter(
            Q(name__icontains=query) | 
            Q(seller_tag__icontains=query) | 
            Q(category__name__icontains=query) |
            Q(description__icontains=query)
        ).select_related('category').prefetch_related('gallery_images').distinct().order_by('-id')
        
        # Paginate search results - 12 items per page
        paginator = Paginator(results_list, 12)
        
        try:
            results = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            results = paginator.page(1)
    
    return render(request, 'products/search_results.html', {
        'query': query,
        'results': results,
        'paginator': paginator,
    })
