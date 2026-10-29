from django.db import transaction
# products/admin.py
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline 
from import_export.admin import ImportExportModelAdmin
from unfold.contrib.import_export.forms import ExportForm, ImportForm
from .models import (
    CustomerProfile, Product, Banner, Category, 
    Order, OrderItem, Review, PromoBox, ContactInquiry,
    Size, ProductImage, Wishlist, WishlistItem, Cart, OTPToken, Address
)

# --- 1. Product Inlines & Size Management ---

class ProductImageInline(TabularInline):
    """Allows uploading multiple gallery images directly on the Product page"""
    model = ProductImage
    extra = 3  # Provides 3 empty slots for side, back, and close-up views
    tab = True # Unfold specific: puts inlines in a nice tab

@admin.register(Size)
class SizeAdmin(ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Address)
class AddressAdmin(ModelAdmin):
    list_display = ('full_name', 'user', 'city', 'state', 'pincode', 'address_type', 'is_default', 'is_active')
    list_filter = ('address_type', 'is_default', 'state')
    search_fields = ('full_name', 'phone_number', 'city', 'pincode', 'user__username')

# --- 2. Product Management with Gallery & Sizes ---

@admin.register(Product)
class ProductAdmin(ModelAdmin, ImportExportModelAdmin):
    import_form_class = ImportForm
    export_form_class = ExportForm

    list_display = ('display_thumbnail', 'name', 'slug', 'price', 'category', 'seller_tag')
    list_filter = ('category', 'seller_tag', 'sizes')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}  # Auto-populate slug from name
    
    # Enables a nice side-by-side selection for sizes
    filter_horizontal = ('sizes',)
    
    # Adds the image gallery uploader
    inlines = [ProductImageInline]
    
    fixed_submit_bar = True

    def display_thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />', obj.image.url)
        return "No Image"
    display_thumbnail.short_description = "Main View"

# --- 3. Branding & Content ---

@admin.register(Banner)
class BannerAdmin(ModelAdmin):
    list_display = ('display_banner', 'title', 'active', 'order')
    list_filter = ('active',)
    
    def display_banner(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 100px; height: 40px; object-fit: cover; border-radius: 4px;" />', obj.image.url)
        return "No Image"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._clear_page_cache()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        self._clear_page_cache()

    def _clear_page_cache(self):
        """Clear the cached index page so new banners appear immediately."""
        from django.core.cache import cache
        cache.clear()

@admin.register(PromoBox)
class PromoBoxAdmin(ModelAdmin):
    list_display = ('title', 'subtitle', 'link_text', 'link_url', 'order')
    list_editable = ('order', 'link_text', 'link_url')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._clear_page_cache()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        self._clear_page_cache()

    def _clear_page_cache(self):
        """Clear the cached index/shop pages so new promos appear immediately."""
        from django.core.cache import cache
        cache.clear()

@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ('name', 'order')
    search_fields = ('name',)

# --- 4. User & Interaction ---

@admin.register(CustomerProfile)
class CustomerProfileAdmin(ModelAdmin):
    list_display = ('user', 'email', 'city', 'is_verified')
    list_filter = ('is_verified', 'city')
    search_fields = ('user__username', 'email')

@admin.register(OTPToken)
class OTPTokenAdmin(ModelAdmin):
    list_display = ('profile', 'created_at', 'expires_at', 'is_used', 'attempts')
    list_filter = ('is_used',)
    readonly_fields = ('token', 'created_at', 'expires_at', 'attempts')

@admin.register(ContactInquiry)
class ContactInquiryAdmin(ModelAdmin):
    list_display = ('full_name', 'email', 'subject', 'created_at')
    readonly_fields = ('created_at',)
    list_filter = ('created_at',)

@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = ('user', 'product', 'rating', 'is_verified', 'comment_preview', 'created_at')
    list_filter = ('rating', 'is_verified', 'created_at')
    search_fields = ('user__username', 'product__name')
    
    def comment_preview(self, obj):
        return obj.comment[:50] + "..." if len(obj.comment) > 50 else obj.comment
    comment_preview.short_description = "Comment Preview"

# --- 5. Orders & Payments ---

class PaymentReviewFilter(admin.SimpleListFilter):
    title = 'Payment Review'
    parameter_name = 'payment_review'

    def lookups(self, request, model_admin):
        return (
            ('review_needed', 'Needs Payment Review'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'review_needed':
            return queryset.filter(status='Payment Review')
        return queryset


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    fields = ('product_name', 'selected_size', 'quantity', 'image_url', 'price')
    readonly_fields = ('selected_size', 'price')

@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ('id', 'user', 'total_amount', 'is_paid', 'status', 'delhivery_waybill', 'created_at')
    list_filter = ('is_paid', 'status', PaymentReviewFilter, 'created_at')
    
    # Razorpay fields are locked to maintain transaction integrity
    readonly_fields = ('razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature', 'refund_id')
    
    fieldsets = (
        (None, {
            'fields': ('user', 'status', 'total_amount', 'is_paid', 'shipping_address'),
        }),
        ('Payment (Razorpay)', {
            'fields': ('razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature', 'transaction_id', 'refund_id'),
            'classes': ('collapse',),
        }),
        ('Shipping (Delhivery)', {
            'fields': ('delhivery_waybill', 'delhivery_shipment_status'),
            'description': 'Assign a Delhivery waybill number to enable shipment tracking for the customer.',
        }),
    )
    
    inlines = [OrderItemInline]
    fixed_submit_bar = True
    actions = ['download_packing_slip', 'confirm_and_re_reserve_stock', 'refund_via_razorpay']

    @admin.action(description="🖨️ Download Packing Slip")
    def download_packing_slip(self, request, queryset):
        if queryset.count() == 1:
            order = queryset.first()
            from django.shortcuts import redirect
            return redirect('admin_packing_slip', order_id=order.id)
        else:
            self.message_user(request, "Please select only one order to download the slip at a time.", level='warning')

    @admin.action(description="Confirm and re-reserve stock")
    def confirm_and_re_reserve_stock(self, request, queryset):
        for order in queryset:
            if order.status != 'Payment Review' or not order.razorpay_payment_id:
                self.message_user(
                    request,
                    f"Order #{order.id} rejected: only orders in 'Payment Review' with a valid Razorpay payment ID can be confirmed (current status: '{order.status}').",
                    level='error'
                )
                continue

            snapshot = order.original_cart_items or []
            if not snapshot:
                self.message_user(request, f"Order #{order.id} has no cart items snapshot to verify stock.", level='warning')
                continue

            with transaction.atomic():
                product_ids = [entry.get('product_id') for entry in snapshot if entry.get('product_id')]
                locked_products = {
                    p.pk: p
                    for p in Product.objects.select_for_update().filter(pk__in=product_ids)
                }

                out_of_stock = []
                for entry in snapshot:
                    p_id = entry.get('product_id')
                    qty = int(entry.get('quantity') or 0)
                    product = locked_products.get(p_id)
                    if not product:
                        out_of_stock.append(f"Product ID {p_id} (not found)")
                    elif product.stock < qty:
                        out_of_stock.append(f"{product.name} (requested {qty}, available {product.stock})")

                if out_of_stock:
                    self.message_user(
                        request,
                        f"Cannot confirm Order #{order.id}: Insufficient stock for {', '.join(out_of_stock)}.",
                        level='error'
                    )
                    continue

                for entry in snapshot:
                    p_id = entry.get('product_id')
                    qty = int(entry.get('quantity') or 0)
                    product = locked_products[p_id]
                    product.stock -= qty
                    product.save(update_fields=['stock'])

                order.is_paid = True
                order.status = 'Paid'
                order.save(update_fields=['is_paid', 'status'])

                # Remove paid items from customer's cart
                from .models import Cart
                from .views import clear_paid_cart_items
                cart = Cart.objects.filter(user=order.user).first()
                if cart:
                    clear_paid_cart_items(cart, order)

                self.message_user(request, f"Order #{order.id} confirmed and stock re-reserved successfully.", level='success')

    @admin.action(description="Refund via Razorpay")
    def refund_via_razorpay(self, request, queryset):
        from .views import get_razorpay_client
        for order in queryset:
            if order.status != 'Payment Review':
                self.message_user(
                    request,
                    f"Order #{order.id} rejected: only orders in 'Payment Review' can be refunded (current status: '{order.status}').",
                    level='error'
                )
                continue

            if not order.razorpay_payment_id:
                self.message_user(request, f"Order #{order.id} has no Razorpay payment ID to refund.", level='error')
                continue

            try:
                client = get_razorpay_client()
                refund_resp = client.payment.refund(order.razorpay_payment_id, {})
                refund_id = refund_resp.get('id', '')
                order.refund_id = refund_id
                order.status = 'Refunded'
                order.save(update_fields=['status', 'refund_id'])
                self.message_user(request, f"Order #{order.id} refunded successfully via Razorpay (Refund ID: {refund_id}).", level='success')
            except Exception as e:
                self.message_user(request, f"Failed to refund Order #{order.id}: {e}", level='error')



# --- 6. Cart & Wishlist Management ---

@admin.register(Cart)
class CartAdmin(ModelAdmin):
    list_display = ('user', 'total_items_count', 'total_price', 'updated_at')
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'updated_at')
    
    def total_items_count(self, obj):
        return sum(item.quantity for item in obj.items.all())
    total_items_count.short_description = "Total Items"
    
    def total_price(self, obj):
        return f"₹{obj.total_price:.2f}"
    total_price.short_description = "Total Price"


@admin.register(Wishlist)
class WishlistAdmin(ModelAdmin):
    list_display = ('user', 'name', 'items_count', 'created_at')
    search_fields = ('user__username', 'name')
    list_filter = ('created_at',)
    
    def items_count(self, obj):
        return obj.items.count()
    items_count.short_description = "Items in Wishlist"


class WishlistItemInline(TabularInline):
    model = WishlistItem
    extra = 1
    fields = ('product',)


@admin.register(WishlistItem)
class WishlistItemAdmin(ModelAdmin):
    list_display = ('wishlist', 'product', 'wishlist_created_at')
    search_fields = ('wishlist__name', 'product__name')
    list_filter = ('wishlist__created_at',)

    def wishlist_created_at(self, obj):
        return obj.wishlist.created_at
    wishlist_created_at.short_description = "Added to Wishlist"
    wishlist_created_at.admin_order_field = 'wishlist__created_at'
