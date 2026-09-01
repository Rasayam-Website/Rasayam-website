import os, re

base_dir = '/Users/uditiagarwal/Downloads/Rasayam1/Rasayam-website/products'

# 1. Update models.py
with open(os.path.join(base_dir, 'models.py'), 'r') as f:
    models_code = f.read()

address_model = """
class Address(models.Model):
    class AddressType(models.TextChoices):
        HOME = 'HOME', 'Home'
        WORK = 'WORK', 'Office / Work'
        OTHER = 'OTHER', 'Other'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField('Full Name', max_length=120)
    phone_number = models.CharField('Phone Number', max_length=15)
    pincode = models.CharField('PIN Code', max_length=6)
    address_line1 = models.CharField('Flat / House No / Building', max_length=255)
    address_line2 = models.CharField('Area / Street / Locality', max_length=255)
    landmark = models.CharField('Landmark', max_length=150, blank=True, default='')
    city = models.CharField('City / Town', max_length=100)
    state = models.CharField('State', max_length=100)
    address_type = models.CharField(
        max_length=10,
        choices=AddressType.choices,
        default=AddressType.HOME,
    )
    is_default = models.BooleanField('Default address', default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-updated_at']
        verbose_name_plural = 'Addresses'

    def __str__(self):
        return f"{self.full_name} — {self.address_line1}, {self.city} ({self.pincode})"

    @property
    def formatted_text(self):
        lines = [
            self.full_name,
            self.address_line1,
            self.address_line2,
            f"Landmark: {self.landmark}" if self.landmark else None,
            f"{self.city}, {self.state} — {self.pincode}",
            f"Phone: {self.phone_number}",
        ]
        return '\\n'.join(line for line in lines if line)

    def save(self, *args, **kwargs):
        from django.db import transaction as db_transaction
        with db_transaction.atomic():
            if not self.pk and not Address.objects.filter(user=self.user, is_active=True).exists():
                self.is_default = True
            if self.is_default:
                Address.objects.filter(user=self.user, is_active=True).exclude(pk=self.pk).update(is_default=False)
            super().save(*args, **kwargs)

"""
if 'class Address(' not in models_code:
    models_code = models_code.replace('class OTPToken(models.Model):', address_model + '\nclass OTPToken(models.Model):')
    with open(os.path.join(base_dir, 'models.py'), 'w') as f:
        f.write(models_code)

# 2. Update admin.py
with open(os.path.join(base_dir, 'admin.py'), 'r') as f:
    admin_code = f.read()

if 'Address' not in admin_code:
    admin_code = admin_code.replace('Size, ProductImage, Wishlist, WishlistItem, Cart, OTPToken\n)', 'Size, ProductImage, Wishlist, WishlistItem, Cart, OTPToken, Address\n)')
    address_admin = """
@admin.register(Address)
class AddressAdmin(ModelAdmin):
    list_display = ('full_name', 'user', 'city', 'state', 'pincode', 'address_type', 'is_default', 'is_active')
    list_filter = ('address_type', 'is_default', 'state')
    search_fields = ('full_name', 'phone_number', 'city', 'pincode', 'user__username')
"""
    admin_code = admin_code.replace('# --- 2. Product Management', address_admin + '\n# --- 2. Product Management')
    with open(os.path.join(base_dir, 'admin.py'), 'w') as f:
        f.write(admin_code)

print("Models and admin patched successfully.")
