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
    
    # --- Cart Logic ---
    path('cart/', views.cart, name='cart'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('add-to-cart-ajax/<int:product_id>/', views.add_to_cart_ajax, name='add_to_cart_ajax'), # Moved here for grouping
    path('decrease-item/<int:item_id>/', views.decrease_cart_item, name='decrease_cart_item'),
    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('search/', views.search_view, name='search'),
    
    # --- Product & Category Logic ---
    path('collection/<slug:slug>/', views.category_detail, name='category_detail'),
    path('product/<int:pk>/', views.product_detail_view, name='product_detail'),  # Keep both for backward compatibility
    path('product/<slug:slug>/', views.product_detail_view_slug, name='product_detail_slug'),
    
     # --- Wishlist Logic ---
    path('get-wishlists/', views.get_wishlists, name='get_wishlists'),
    path('add-to-wishlist/', views.add_to_wishlist, name='add_to_wishlist'),
    path('collections/', views.collections_view, name='collections'),
    
    # --- Orders & Razorpay Payments ---
    path('save-order/', views.save_order, name='save_order'),
    
    # --- ADDED THIS LINE: The callback for Razorpay to verify payment signature ---
    path('payment-verify/', views.payment_verify, name='payment_verify'), 
    
    path('order/<int:order_id>/', views.order_detail_view, name='order_detail'),

    # --- Authentication Flow ---
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('verify/<str:phone_number>/', views.verify_otp, name='verify_otp'),
    path('profile/', views.profile_view, name='profile'),
    
    # Built-in Logout
    path('logout/', auth_views.LogoutView.as_view(next_page='index'), name='logout'),


    # --- products/urls.py ---
    path('payment-success/<int:order_id>/', views.payment_success, name='payment_success'),
    path('payment-fail/', views.payment_fail, name='payment_fail'),

    # --- Legal & Policy Pages ---
    path('refund/', views.refund, name='refund'),
    path('refund-policy/', views.refund_policy, name='refund_policy'),
    path('shipping/', views.shipping, name='shipping'),
    path('shipping-policy/', views.shipping_policy, name='shipping_policy'),
    path('terms/', views.terms, name='terms'),
    path('faq/', views.faq, name='faq'),
]
