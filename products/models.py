from django.db import models
from django.contrib.auth.models import User

# --- 1. User Infrastructure ---
class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, unique=True, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.user.username


class OTPToken(models.Model):
    """One OTP record per authentication attempt. Old tokens are invalidated on resend."""
    MAX_ATTEMPTS = 5
    RESEND_COOLDOWN_SECONDS = 60
    EXPIRY_MINUTES = 5

    profile = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name='otp_tokens')
    token = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() >= self.expires_at

    def is_valid(self):
        return not self.is_used and not self.is_expired() and self.attempts < self.MAX_ATTEMPTS

    def __str__(self):
        return f"OTP for {self.profile} (used={self.is_used})"

class Banner(models.Model):
    title = models.CharField(max_length=100, blank=True)
    image = models.ImageField(upload_to='banners/')
    active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)

    def __str__(self):
        return self.title or f"Banner {self.id}"


class PromoBox(models.Model):
    title = models.CharField(max_length=100)
    subtitle = models.CharField(max_length=200, blank=True)
    link_url = models.CharField(max_length=500, blank=True, null=True)
    link_text = models.CharField(max_length=50, default="Shop Now")
    order = models.IntegerField(default=0)

    class Meta:
        verbose_name_plural = "Promo Boxes"
        ordering = ['order']

    def __str__(self):
        return self.title

# --- 2. Catalog ---

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True, null=True)
    order = models.IntegerField(default=0)
    image = models.ImageField(upload_to='category_images/', blank=True, null=True)
    
    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

class Size(models.Model):
    """Allows admin to create sizes like XS, S, M, L, XL, 5XL etc."""
    name = models.CharField(max_length=10, unique=True)
    
    def __str__(self):
        return self.name

class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, null=True, help_text="Auto-generated from name for SEO-friendly URLs")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # This acts as the "Main" thumbnail image
    image = models.ImageField(upload_to='product_images/', blank=True, null=True)
    
    # Detailed Info for the Dedicated Product Page
    description = models.TextField(blank=True, help_text="Detailed story or description of the product.")
    highlights = models.TextField(blank=True, help_text="Amazon-style bullet points. Enter each highlight on a new line.")
    fabric_details = models.TextField(blank=True)
    seller_tag = models.CharField(max_length=50, blank=True)
    
    # Size selection
    sizes = models.ManyToManyField(Size, blank=True, help_text="Hold Ctrl to select multiple sizes.")
    stock = models.PositiveIntegerField(default=0, help_text="Available units. 0 = out of stock.")

    def __str__(self):
        return self.name

class ProductImage(models.Model):
    """Allows for multiple gallery images for a single product."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='gallery_images')
    image = models.ImageField(upload_to='product_gallery/')
    alt_text = models.CharField(max_length=255, blank=True, help_text="Optional: Describes image for SEO.")

    def __str__(self):
        return f"Gallery Image for {self.product.name}"

# --- 3. Interaction & Orders ---

class ContactInquiry(models.Model):
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Contact Inquiries"

class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(default=5) 
    comment = models.TextField()
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Order(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
        ('Processing', 'Processing'),
        ('Shipped', 'Shipped'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    original_cart_items = models.JSONField(default=list, blank=True)
    shipping_address = models.TextField(blank=True, default='')
    # Populated by the payment gateway on success; unique prevents duplicate confirmations.
    transaction_id = models.CharField(max_length=100, unique=True, blank=True, null=True)

    # --- RAZORPAY PAYMENT FIELDS ---
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    is_paid = models.BooleanField(default=False)

    def __str__(self):
        return f"Order {self.id} by {self.user.username}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product_name = models.CharField(max_length=255)
    selected_size = models.CharField(max_length=20, blank=True, default="")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    image_url = models.URLField(blank=True)

    def __str__(self):
        return f"{self.quantity}x {self.product_name} - Order {self.order.id}"

# --- 4. Cart Logic ---

class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for {self.user.username}"

    @property
    def total_price(self):
        return sum(item.total_item_price for item in self.items.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    selected_size = models.CharField(max_length=20, blank=True, default="")
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        size_suffix = f" ({self.selected_size})" if self.selected_size else ""
        return f"{self.quantity} x {self.product.name}{size_suffix}"

    @property
    def unit_price(self):
        return self.price if self.price > 0 else self.product.price

    @property
    def total_item_price(self):
        return self.unit_price * self.quantity
    

class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlists')
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'name') # Prevents duplicate collection names for one user

    def __str__(self):
        return f"{self.name} ({self.user.username})"

class WishlistItem(models.Model):
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.product.name} in {self.wishlist.name}"
