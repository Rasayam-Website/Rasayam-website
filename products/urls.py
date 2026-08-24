from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # --- Main Boutique Pages ---
    path('', views.index, name='index'),
    path('shop/', views.shop, name='shop'),
    path('about/', views.about_view, name='about'),
    path('about-us/', views.about_us, name='about_us'),
    path('contact/', views.contact, name='contact'),
    path('privacy-policy/', views.privacy, name='privacy_policy'),

    # --- Cart (HTML views) ---
    path('cart/', views.cart, name='cart'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('add-to-cart-ajax/<int:product_id>/', views.add_to_cart_ajax, name='add_to_cart_ajax'),
    path('decrease-item/<int:item_id>/', views.decrease_cart_item, name='decrease_cart_item'),
    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),

    # --- Cart JSON API ---
    path('api/cart/', views.cart_detail_api, name='cart_detail_api'),
    path('api/cart/update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('api/cart/remove/<int:item_id>/', views.remove_cart_item_api, name='remove_cart_item_api'),

    # --- Search ---
    path('search/', views.search_view, name='search'),

    # --- Product & Category ---
    path('collection/<slug:slug>/', views.category_detail, name='category_detail'),
    path('product/<int:pk>/', views.product_detail_view, name='product_detail'),
    path('product/<slug:slug>/', views.product_detail_view_slug, name='product_detail_slug'),

    # --- Wishlist ---
    path('get-wishlists/', views.get_wishlists, name='get_wishlists'),
    path('add-to-wishlist/', views.add_to_wishlist, name='add_to_wishlist'),
    path('collections/', views.collections_view, name='collections'),

    # --- Orders & Payments ---
    path('save-order/', views.save_order, name='save_order'),
    path('payment-verify/', views.payment_verify, name='payment_verify'),
    path('webhooks/razorpay/', views.razorpay_webhook, name='razorpay_webhook'),
    path('order/<int:order_id>/', views.order_detail_view, name='order_detail'),
    path('payment-success/<int:order_id>/', views.payment_success, name='payment_success'),
    path('payment-fail/', views.payment_fail, name='payment_fail'),

    # --- Authentication ---
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('verify/<str:email>/', views.verify_otp, name='verify_otp'),
    path('resend-otp/<str:email>/', views.resend_otp, name='resend_otp'),
    path('profile/', views.profile_view, name='profile'),
    path('logout/', auth_views.LogoutView.as_view(next_page='index'), name='logout'),

    # --- Legal & Policy Pages ---
    path('refund/', views.refund, name='refund'),
    path('refund-policy/', views.refund_policy, name='refund_policy'),
    path('shipping/', views.shipping, name='shipping'),
    path('shipping-policy/', views.shipping_policy, name='shipping_policy'),
    path('terms/', views.terms, name='terms'),
    path('faq/', views.faq, name='faq'),
]
