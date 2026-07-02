from django.db.models import Sum
from .models import Cart
from . import session_cart as guest_cart

def cart_count(request):
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
        if cart:
            count = cart.items.aggregate(total=Sum('quantity'))['total'] or 0
        else:
            count = 0
        return {'cart_count': count}
    else:
        # Sum quantities from guest session cart
        count = sum(item['quantity'] for item in guest_cart.get_items(request.session))
        return {'cart_count': count}