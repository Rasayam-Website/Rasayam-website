import json
import random
import razorpay
from datetime import timedelta
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import cache_page
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django_ratelimit.decorators import ratelimit
from .models import (
    Product, Banner, Category, PromoBox, 
    CustomerProfile, ContactInquiry, Order, OrderItem, Review,
    Cart, CartItem,
    Wishlist, WishlistItem
)

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

@cache_page(60 * 10)  # Cache for 10 minutes
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

@login_required
def cart(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    # Optimize query by using select_related and prefetch_related
    cart_items = cart.items.select_related('product').prefetch_related('product__gallery_images').all()
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

@ratelimit(key='ip', rate='5/m', method='POST')  # Prevent brute force
def register_view(request):
    if request.method == 'POST':
        phone = request.POST.get('phone')
        username = request.POST.get('username')
        email = request.POST.get('email')
        gender = request.POST.get('gender')
        city = request.POST.get('city')
        
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.email = email
            user.set_password('temp_pass_123')
            user.save()
            
        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        profile.phone_number = phone
        profile.email = email
        profile.gender = gender
        profile.city = city
        
        generated_otp = str(random.randint(100000, 999999))
        profile.otp = generated_otp
        profile.otp_created_at = timezone.now()
        profile.save()
        
        # DEBUG MODE: Check your terminal for the code
        print(f"--- OTP FOR {username} ({phone}): {generated_otp} ---")
        
        return redirect('verify_otp', phone_number=phone)
        
    return render(request, 'products/register.html')

@ratelimit(key='ip', rate='5/m', method='POST')  # Prevent brute force
def login_view(request):
    if request.method == "POST":
        phone = request.POST.get('phone_number')
        try:
            profile = CustomerProfile.objects.get(phone_number=phone)
            new_otp = str(random.randint(100000, 999999))
            profile.otp = new_otp
            profile.otp_created_at = timezone.now()
            profile.save()
            
            # DEBUG MODE: Check your terminal for the code
            print(f"DEBUG: OTP for {phone} is {new_otp}")
            
            return redirect('verify_otp', phone_number=phone)
            
        except CustomerProfile.DoesNotExist:
            messages.error(request, "This phone number isn't registered yet.")
            return redirect('register')

    return render(request, 'products/login.html')

@ratelimit(key='ip', rate='10/m', method='POST')  # Rate limit OTP attempts
def verify_otp(request, phone_number):
    profile = get_object_or_404(CustomerProfile, phone_number=phone_number.strip())
    
    if request.method == 'POST':
        user_otp = request.POST.get('otp', '').strip()
        db_otp = (profile.otp or '').strip()

        # Check OTP expiry (5 minutes)
        if profile.otp_created_at:
            elapsed = timezone.now() - profile.otp_created_at
            if elapsed > timedelta(minutes=5):
                messages.error(request, "OTP expired. Request a new one.")
                return redirect('login')

        if user_otp == db_otp:
            profile.is_verified = True
            profile.save()
            login(request, profile.user)
            messages.success(request, f"Welcome back, {profile.user.username}!")
            return redirect('index')
        else:
            messages.error(request, "Incorrect OTP. Check your server logs.")
            return render(request, 'products/verify_otp.html', {'phone': phone_number})

    return render(request, 'products/verify_otp.html', {'phone': phone_number})

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
@ratelimit(key='user', rate='10/h', method='POST')  # Prevent order spam
def save_order(request):
    cart = get_object_or_404(Cart, user=request.user)
    # Optimize query with select_related
    cart_items = list(
        cart.items.select_related('product').prefetch_related('product__sizes')
    )

    if not cart_items:
        messages.error(request, "Your bag is empty.")
        return redirect('shop')

    total_amount = sum(item.total_item_price for item in cart_items)

    try:
        razorpay_client = get_razorpay_client()
    except ValueError as e:
        messages.error(request, f"Gateway Error: {str(e)}")
        return redirect('cart')

    original_cart_items = []
    for item in cart_items:
        # Validate size is still available before the order is created.
        if item.selected_size and not item.product.sizes.filter(name=item.selected_size).exists():
            messages.error(request, f"Size {item.selected_size} is no longer available. Please update your selection.")
            return redirect('cart')

        original_cart_items.append({
            'cart_item_id': item.id,
            'product_id': item.product_id,
            'product_name': item.product.name,
            'selected_size': item.selected_size,
            'quantity': item.quantity,
            'price': str(item.unit_price),
        })

    # 1. Create the Order record (status stays 'Pending')
    order = Order.objects.create(
        user=request.user,
        total_amount=total_amount,
        status='Pending',
        original_cart_items=original_cart_items,
    )

    for item in cart_items:
        OrderItem.objects.create(
            order=order,
            product_name=item.product.name,
            selected_size=item.selected_size,
            price=item.unit_price,
            quantity=item.quantity,
            image_url=item.product.image.url if item.product.image else ""
        )

    amount_in_paise = int(total_amount * 100)
    payment_data = {
        "amount": amount_in_paise,
        "currency": "INR",
        "receipt": f"rasayam_order_{order.id}",
    }

    try:
        razorpay_order = razorpay_client.order.create(data=payment_data)
        order.razorpay_order_id = razorpay_order['id']
        order.save()

        # --- IMPORTANT: REMOVED cart_items.delete() FROM HERE ---
        # Items stay in cart until payment_verify confirms success.

        return render(request, 'products/payment.html', {
            'order': order,
            'razorpay_order_id': razorpay_order['id'],
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'amount': amount_in_paise,
        })
    except Exception as e:
        messages.error(request, f"Gateway Error: {str(e)}")
        return redirect('cart')


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


@login_required
def order_detail_view(request, order_id):
    # This prevents users from accessing an unpaid order detail page via a direct URL
    order = get_object_or_404(Order, id=order_id, user=request.user, is_paid=True)
    return render(request, 'products/order_detail.html', {'order': order})

@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    selected_size = get_selected_size_from_request(request, product)
    cart, _ = Cart.objects.get_or_create(user=request.user)
    add_product_to_cart(cart, product, selected_size)
    
    messages.success(request, f"{product.name} added to Selection.")
    if request.POST.get('buy_now'):
        return redirect('cart')
    return redirect(request.META.get('HTTP_REFERER', 'shop'))

@login_required
def decrease_cart_item(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    if cart_item.quantity > 1:
        cart_item.quantity -= 1
        cart_item.save()
        messages.info(request, "Item quantity updated.")
    else:
        cart_item.delete()
        messages.info(request, "Item removed.")
    return redirect('cart')

@login_required
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    cart_item.delete()
    messages.info(request, "Item removed.")
    return redirect('cart')

@login_required
@ratelimit(key='user', rate='30/m', method='POST')  # Prevent spam adds
def add_to_cart_ajax(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    selected_size = get_selected_size_from_request(request, product)
    cart, _ = Cart.objects.get_or_create(user=request.user)
    add_product_to_cart(cart, product, selected_size)
    
    total_count = sum(item.quantity for item in cart.items.all())
    
    return JsonResponse({
        'status': 'success',
        'cart_count': total_count,
        'selected_size': selected_size,
        'message': f"{product.name} added."
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
