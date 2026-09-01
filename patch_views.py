import os, re

base_dir = '/Users/uditiagarwal/Downloads/Rasayam1/Rasayam-website/products'
with open(os.path.join(base_dir, 'views.py'), 'r') as f:
    views_code = f.read()

# 1. Add Address to imports
if 'Address' not in views_code:
    views_code = views_code.replace(
        'from .models import CustomerProfile, Category, Product, Cart, CartItem, Order, OrderItem, Review, ContactInquiry, Wishlist, WishlistItem, OTPToken',
        'from .models import CustomerProfile, Category, Product, Cart, CartItem, Order, OrderItem, Review, ContactInquiry, Wishlist, WishlistItem, OTPToken, Address'
    )

# 2. Update register_view
reg_old = """            profile = CustomerProfile.objects.create(
                user=user,
                email=email,
                phone=phone or None,
                gender=request.POST.get('gender', ''),
                date_of_birth=dob if dob else None,
                city=request.POST.get('city', ''),
                state=request.POST.get('state', ''),
            )"""
reg_new = """            profile = CustomerProfile.objects.create(
                user=user,
                email=email,
                phone=phone or None,
                gender=request.POST.get('gender', ''),
                date_of_birth=dob if dob else None,
            )"""
views_code = views_code.replace(reg_old, reg_new)

# 3. Update cart view
cart_old = """    return render(request, 'products/cart.html', {
        'cart_items': cart_items,
        'total_price': total_price,
        'recommended_items': recommended_items,
    })"""
cart_new = """    addresses = Address.objects.filter(user=request.user, is_active=True) if request.user.is_authenticated else []
    return render(request, 'products/cart.html', {
        'cart_items': cart_items,
        'total_price': total_price,
        'recommended_items': recommended_items,
        'addresses': addresses,
    })"""
views_code = views_code.replace(cart_old, cart_new)

# 4. Update save_order view
save_order_old = """    shipping_address = request.POST.get('shipping_address', '').strip()"""
save_order_new = """    shipping_address_id = request.POST.get('shipping_address_id')
    shipping_address = ''
    if shipping_address_id:
        try:
            addr = Address.objects.get(pk=shipping_address_id, user=request.user, is_active=True)
            shipping_address = addr.formatted_text
        except Address.DoesNotExist:
            pass"""
views_code = views_code.replace(save_order_old, save_order_new)

# 5. Add Address views
address_views = """
# --- Address Management ---

@login_required
def address_list(request):
    addresses = Address.objects.filter(user=request.user, is_active=True)
    return render(request, 'products/addresses.html', {'addresses': addresses})

@login_required
def address_create(request):
    if request.method == 'POST':
        Address.objects.create(
            user=request.user,
            full_name=request.POST.get('full_name', '').strip(),
            phone_number=request.POST.get('phone_number', '').strip(),
            pincode=request.POST.get('pincode', '').strip(),
            address_line1=request.POST.get('address_line1', '').strip(),
            address_line2=request.POST.get('address_line2', '').strip(),
            landmark=request.POST.get('landmark', '').strip(),
            city=request.POST.get('city', '').strip(),
            state=request.POST.get('state', '').strip(),
            address_type=request.POST.get('address_type', 'HOME'),
            is_default=request.POST.get('is_default') == 'on',
        )
        messages.success(request, 'Address saved successfully.')
        return redirect(request.POST.get('next') or 'address_list')
    return redirect('address_list')

@login_required
def address_edit(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user, is_active=True)
    if request.method == 'POST':
        address.full_name = request.POST.get('full_name', '').strip()
        address.phone_number = request.POST.get('phone_number', '').strip()
        address.pincode = request.POST.get('pincode', '').strip()
        address.address_line1 = request.POST.get('address_line1', '').strip()
        address.address_line2 = request.POST.get('address_line2', '').strip()
        address.landmark = request.POST.get('landmark', '').strip()
        address.city = request.POST.get('city', '').strip()
        address.state = request.POST.get('state', '').strip()
        address.address_type = request.POST.get('address_type', 'HOME')
        address.is_default = request.POST.get('is_default') == 'on'
        address.save()
        messages.success(request, 'Address updated.')
        return redirect(request.POST.get('next') or 'address_list')
    return render(request, 'products/address_edit.html', {'address': address})

@login_required
@require_POST
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.is_active = False
    address.is_default = False
    address.save(update_fields=['is_active', 'is_default'])
    remaining = Address.objects.filter(user=request.user, is_active=True).first()
    if remaining and not Address.objects.filter(user=request.user, is_active=True, is_default=True).exists():
        remaining.is_default = True
        remaining.save(update_fields=['is_default'])
    messages.success(request, 'Address removed.')
    return redirect(request.POST.get('next') or 'address_list')

@login_required
@require_POST
def address_set_default(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user, is_active=True)
    address.is_default = True
    address.save()
    messages.success(request, 'Default address updated.')
    return redirect(request.POST.get('next') or 'address_list')

# --- 4. Order & Cart Processing
"""
views_code = views_code.replace('# --- 4. Order & Cart Processing', address_views)

with open(os.path.join(base_dir, 'views.py'), 'w') as f:
    f.write(views_code)
print("views.py patched.")
