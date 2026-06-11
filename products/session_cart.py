"""
Guest cart backed by Django's session engine.

Session key: 'guest_cart'
Structure:   { "<product_id>:<size>": {"product_id": int, "size": str,
                                        "quantity": int, "price": str} }

Auth users use the Cart/CartItem DB models. This module is only for guests.
On login, call merge_guest_cart_on_login() to fold session items into the DB cart.
"""
from decimal import Decimal
from .models import Cart, CartItem, Product

SESSION_KEY = 'guest_cart'


# ── Internal helpers ──────────────────────────────────────────────────────────

def _key(product_id: int, size: str) -> str:
    return f"{product_id}:{size}"


def _cart(session: dict) -> dict:
    if SESSION_KEY not in session:
        session[SESSION_KEY] = {}
    return session[SESSION_KEY]


# ── Public API ────────────────────────────────────────────────────────────────

def add_item(session, product: Product, size: str = '', quantity: int = 1) -> None:
    cart = _cart(session)
    k = _key(product.pk, size)
    if k in cart:
        cart[k]['quantity'] += quantity
    else:
        cart[k] = {
            'product_id': product.pk,
            'size': size,
            'quantity': quantity,
            'price': str(product.price),
        }
    session.modified = True


def update_item(session, product_id: int, size: str, quantity: int) -> bool:
    """Returns False if the item didn't exist."""
    cart = _cart(session)
    k = _key(product_id, size)
    if k not in cart:
        return False
    if quantity <= 0:
        del cart[k]
    else:
        cart[k]['quantity'] = quantity
    session.modified = True
    return True


def remove_item(session, product_id: int, size: str) -> bool:
    cart = _cart(session)
    k = _key(product_id, size)
    if k not in cart:
        return False
    del cart[k]
    session.modified = True
    return True


def get_items(session) -> list[dict]:
    return list(_cart(session).values())


def total(session) -> Decimal:
    return sum(
        Decimal(item['price']) * item['quantity']
        for item in _cart(session).values()
    )


def clear(session) -> None:
    session[SESSION_KEY] = {}
    session.modified = True


def merge_guest_cart_on_login(session, user) -> None:
    """
    Called after a guest logs in. Folds session cart into the user's DB cart,
    then clears the session cart.
    """
    items = get_items(session)
    if not items:
        return
    cart, _ = Cart.objects.get_or_create(user=user)
    for entry in items:
        try:
            product = Product.objects.get(pk=entry['product_id'])
        except Product.DoesNotExist:
            continue
        existing = cart.items.filter(product=product, selected_size=entry['size']).first()
        if existing:
            existing.quantity += entry['quantity']
            existing.save(update_fields=['quantity'])
        else:
            CartItem.objects.create(
                cart=cart,
                product=product,
                selected_size=entry['size'],
                quantity=entry['quantity'],
                price=Decimal(entry['price']),
            )
    clear(session)
