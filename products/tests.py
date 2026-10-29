from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Cart, CartItem, Category, Order, OrderItem, Product, Size, CustomerProfile

class RasayamCoreSystemTests(TestCase):

    def setUp(self):
        """Build mock data structures in memory with fake image references"""
        self.category_odisha = Category.objects.create(
            name="Odisha", 
            slug="odisha",
            image="mock_odisha.jpg"  # 🌟 Added fake image string
        )
        self.category_punjab = Category.objects.create(
            name="Punjab", 
            slug="punjab",
            image="mock_punjab.jpg"  # 🌟 Added fake image string
        )
        
        # Build mock listings with image placeholders to keep template renderers happy
        self.item_ikat = Product.objects.create(
            name="Premium Ikat Silk Kurti",
            price=4500,
            category=self.category_odisha,
            seller_tag="Handloom Artisan",
            image="mock_ikat.jpg",  # 🌟 Added fake image string
            stock=10,
        )
        self.item_phulkari = Product.objects.create(
            name="Heritage Phulkari Suit",
            price=6800,
            category=self.category_punjab,
            seller_tag="Vintage Craft",
            image="mock_phulkari.jpg",  # 🌟 Added fake image string
            stock=10,
        )

        self.category_plain = Category.objects.create(name="Plain Cotton", slug="plain-cotton")
        self.category_without_slug = Category.objects.create(name="Unlinked Category")
        self.item_without_image = Product.objects.create(
            name="Minimal Cotton Kurti",
            price=2200,
            category=self.category_plain,
            seller_tag="Everyday Craft",
            stock=10,
        )

    def test_homepage_render_and_grid_context(self):
        """Verify the index view successfully parses our variety categories"""
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.category_odisha, response.context['categories'])

    def test_search_engine_by_name(self):
        """Verify search handles direct name intersections matching database queries"""
        response = self.client.get(reverse('search'), {'q': 'Ikat'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Premium Ikat Silk Kurti")

    def test_search_engine_by_seller_tag(self):
        """Verify complex Q filters accurately evaluate multi-column tag parameters"""
        response = self.client.get(reverse('search'), {'q': 'Vintage'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Heritage Phulkari Suit")

    def test_search_engine_empty_fallbacks(self):
        """Verify layout system provides a clean UX empty state if no matches occur"""
        response = self.client.get(reverse('search'), {'q': 'NonExistentProductStyle'})
        self.assertEqual(response.status_code, 200)

    def test_storefront_pages_render_optional_images_and_slugs(self):
        """Optional images and blank category slugs should not crash templates."""
        urls = [
            reverse('index'),
            reverse('shop'),
            reverse('category_detail', args=[self.category_plain.slug]),
            reverse('product_detail', args=[self.item_without_image.id]),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('search'), {'q': 'Minimal'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Minimal Cotton Kurti")

    def test_cart_renders_item_without_image(self):
        """Cart thumbnails should fall back cleanly when a product has no image."""
        user = User.objects.create_user(username="buyer", password="test-pass-123")
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(cart=cart, product=self.item_without_image, quantity=1)

        self.client.force_login(user)
        response = self.client.get(reverse('cart'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Minimal Cotton Kurti")

    def test_cart_uses_price_snapshot(self):
        """Cart totals should keep the price captured when the item was added."""
        user = User.objects.create_user(username="price-buyer", password="test-pass-123")
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(
            cart=cart,
            product=self.item_without_image,
            quantity=2,
            price=2000,
        )
        self.item_without_image.price = 3000
        self.item_without_image.save(update_fields=['price'])

        self.client.force_login(user)
        response = self.client.get(reverse('cart'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "₹2000")
        self.assertContains(response, "₹4000")

    def test_paid_order_clears_only_snapshot_quantities(self):
        """Payment finalization should leave cart quantities added after checkout."""
        from .views import clear_paid_cart_items

        user = User.objects.create_user(username="partial-clear", password="test-pass-123")
        cart = Cart.objects.create(user=user)
        cart_item = CartItem.objects.create(
            cart=cart,
            product=self.item_without_image,
            quantity=3,
            price=self.item_without_image.price,
        )
        order = Order.objects.create(
            user=user,
            total_amount=self.item_without_image.price * 2,
            status="Pending",
            original_cart_items=[
                {
                    'cart_item_id': cart_item.id,
                    'product_id': self.item_without_image.id,
                    'product_name': self.item_without_image.name,
                    'selected_size': '',
                    'quantity': 2,
                    'price': str(self.item_without_image.price),
                }
            ],
        )

        clear_paid_cart_items(cart, order)

        cart_item.refresh_from_db()
        self.assertEqual(cart_item.quantity, 1)

    def test_selected_size_is_saved_and_displayed(self):
        """Selected sizes should stay attached to cart and order items."""
        user = User.objects.create_user(username="sized-buyer", password="test-pass-123")
        size = Size.objects.create(name="M")
        self.item_without_image.sizes.add(size)

        self.client.force_login(user)
        self.client.post(
            reverse('add_to_cart', args=[self.item_without_image.id]),
            {'selected_size': size.name},
            HTTP_REFERER=reverse('product_detail', args=[self.item_without_image.id]),
        )

        cart_item = CartItem.objects.get(cart__user=user, product=self.item_without_image)
        self.assertEqual(cart_item.selected_size, "M")

        cart_response = self.client.get(reverse('cart'))
        self.assertContains(cart_response, "Size: M")

        order = Order.objects.create(
            user=user,
            total_amount=self.item_without_image.price,
            status="Paid",
            is_paid=True,
        )
        OrderItem.objects.create(
            order=order,
            product_name=self.item_without_image.name,
            selected_size=cart_item.selected_size,
            price=self.item_without_image.price,
            quantity=1,
        )

        order_response = self.client.get(reverse('order_detail', args=[order.id]))
        self.assertContains(order_response, "Size: M")

    def test_registration_hijack_prevention(self):
        """Verify registering with an existing username returns an error and does not overwrite user data."""
        # Create an existing user
        existing_user = User.objects.create_user(username="target_admin", email="admin@rasayam.com")
        existing_user.save()
        
        # Try to register with the same username
        response = self.client.post(reverse('register'), {
            'username': 'target_admin',
            'phone': '1234567890',
            'email': 'hacker@rasayam.com',
            'gender': 'Male',
            'city': 'Odisha'
        })
        
        # Should render the register page again (not redirect to verification)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Username is already taken.")
        
        # Verify the user email was NOT updated/hijacked
        existing_user.refresh_from_db()
        self.assertEqual(existing_user.email, "admin@rasayam.com")

    def test_registration_duplicate_email_prevention(self):
        """Verify registering with an existing email returns an error."""
        user = User.objects.create_user(username="user1", email="user1@rasayam.com")
        CustomerProfile.objects.create(user=user, email="user1@rasayam.com")

        response = self.client.post(reverse('register'), {
            'username': 'user2',
            'email': 'user1@rasayam.com',
            'gender': 'Female',
            'city': 'Punjab'
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This email is already registered.")



    def test_resend_otp_post_only(self):
        """Verify that resend_otp endpoint requires a POST request."""
        # Create a profile first
        user = User.objects.create_user(username="otp_user", email="otp@rasayam.com")
        CustomerProfile.objects.create(user=user, email="otp@rasayam.com")
        
        # GET request should return 405 Method Not Allowed
        response = self.client.get(reverse('resend_otp', args=["otp@rasayam.com"]))
        self.assertEqual(response.status_code, 405)
        
        # POST request should succeed/redirect
        response = self.client.post(reverse('resend_otp', args=["otp@rasayam.com"]))
        self.assertEqual(response.status_code, 302)

    def test_cancel_expired_orders_command(self):
        """Verify cancel_expired_orders command cancels pending orders older than 20 mins and restores stock."""
        from django.core.management import call_command
        from django.utils import timezone
        
        # Set initial stock
        self.item_ikat.stock = 10
        self.item_ikat.save(update_fields=['stock'])
        
        # Create user
        user = User.objects.create_user(username="pending_buyer", password="test-pass-123")
        
        # Create order snapshot and order
        original_cart_items = [
            {
                'cart_item_id': 999,
                'product_id': self.item_ikat.id,
                'product_name': self.item_ikat.name,
                'selected_size': '',
                'quantity': 3,
                'price': str(self.item_ikat.price),
            }
        ]
        
        # Deduct stock as save_order view would do
        self.item_ikat.stock -= 3
        self.item_ikat.save()
        
        order = Order.objects.create(
            user=user,
            total_amount=self.item_ikat.price * 3,
            status='Pending',
            original_cart_items=original_cart_items
        )
        
        # Set order created_at to 30 minutes ago
        Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timezone.timedelta(minutes=30))
        
        # Call command
        call_command('cancel_expired_orders')
        
        # Refresh from DB
        order.refresh_from_db()
        self.item_ikat.refresh_from_db()
        
        # Order should be cancelled and stock restored
        self.assertEqual(order.status, 'Cancelled')
        self.assertEqual(self.item_ikat.stock, 10)

    def test_guest_cart_flow(self):
        """Verify guest user can add, view, and modify items in their session cart."""
        # 1. Add item to cart
        response = self.client.post(reverse('add_to_cart', args=[self.item_ikat.id]), {
            'selected_size': ''
        })
        self.assertEqual(response.status_code, 302) # Redirect to referer / shop
        
        # Verify item added in session
        session_cart = self.client.session.get('guest_cart')
        key = f"{self.item_ikat.id}:"
        self.assertIn(key, session_cart)
        self.assertEqual(session_cart[key]['quantity'], 1)
        
        # 2. Add via AJAX
        response = self.client.post(reverse('add_to_cart_ajax', args=[self.item_ikat.id]), {
            'selected_size': ''
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['cart_count'], 2)
        
        # 3. View cart page
        response = self.client.get(reverse('cart'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Premium Ikat Silk Kurti")
        self.assertContains(response, "₹9000") # Total price (2 * 4500)
        
        # 4. Context processor check
        self.assertEqual(response.context['cart_count'], 2)
        
        # 5. Decrease item
        import zlib
        pseudo_id = zlib.crc32(f"{self.item_ikat.id}:".encode('utf-8')) & 0x7fffffff
        response = self.client.get(reverse('decrease_cart_item', args=[pseudo_id]))
        self.assertEqual(response.status_code, 302)
        
        # Verify quantity decreased
        session_cart = self.client.session.get('guest_cart')
        self.assertEqual(session_cart[key]['quantity'], 1)
        
        # 6. Remove item
        response = self.client.get(reverse('remove_from_cart', args=[pseudo_id]))
        self.assertEqual(response.status_code, 302)
        
        # Verify item removed
        session_cart = self.client.session.get('guest_cart')
        self.assertNotIn(key, session_cart)



import hashlib
import hmac
import json
from decimal import Decimal
from django.conf import settings
from django.test import override_settings
from unittest.mock import patch, MagicMock
from django.contrib.admin.sites import AdminSite
from products.admin import OrderAdmin


@override_settings(RAZORPAY_WEBHOOK_SECRET="test_webhook_secret_key_123")
class RazorpayWebhookAndPaymentReviewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test_buyer_webhook", password="test_password_123")
        self.category = Category.objects.create(name="Silk Wear", slug="silk-wear")
        self.product = Product.objects.create(
            name="Banarasi Saree",
            price=Decimal("5000.00"),
            stock=10,
            category=self.category,
        )
        self.webhook_secret = "test_webhook_secret_key_123"

    def _generate_signature(self, payload_bytes):
        return hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

    def _post_webhook(self, payload_dict, signature=None):
        payload_bytes = json.dumps(payload_dict).encode('utf-8')
        if signature is None:
            signature = self._generate_signature(payload_bytes)
        return self.client.post(
            reverse('razorpay_webhook'),
            data=payload_bytes,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=signature
        )

    def test_webhook_normal_capture(self):
        """A normal payment.captured webhook flips Pending order to Paid and clears cart items."""
        cart = Cart.objects.create(user=self.user)
        cart_item = CartItem.objects.create(cart=cart, product=self.product, quantity=2, price=Decimal("5000.00"))
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("10000.00"),
            status='Pending',
            razorpay_order_id='order_norm_123',
            original_cart_items=[{
                'cart_item_id': cart_item.id,
                'product_id': self.product.id,
                'quantity': 2,
                'selected_size': '',
                'price': '5000.00'
            }]
        )

        payload = {
            'event': 'payment.captured',
            'payload': {
                'payment': {
                    'entity': {
                        'id': 'pay_norm_123',
                        'order_id': 'order_norm_123',
                        'amount': 1000000
                    }
                }
            }
        }

        resp = self._post_webhook(payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'status': 'ok'})

        order.refresh_from_db()
        self.assertTrue(order.is_paid)
        self.assertEqual(order.status, 'Paid')
        self.assertEqual(order.razorpay_payment_id, 'pay_norm_123')
        self.assertEqual(order.transaction_id, 'pay_norm_123')
        self.assertEqual(cart.items.count(), 0)

    def test_webhook_duplicate_capture(self):
        """Duplicate payment.captured webhook for an already Paid order is a no-op returning 200 OK."""
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("5000.00"),
            status='Paid',
            is_paid=True,
            razorpay_order_id='order_dup_123',
            razorpay_payment_id='pay_dup_123',
            transaction_id='pay_dup_123'
        )

        payload = {
            'event': 'payment.captured',
            'payload': {
                'payment': {
                    'entity': {
                        'id': 'pay_dup_123',
                        'order_id': 'order_dup_123',
                        'amount': 500000
                    }
                }
            }
        }

        resp = self._post_webhook(payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'status': 'ok'})

        order.refresh_from_db()
        self.assertTrue(order.is_paid)
        self.assertEqual(order.status, 'Paid')

    def test_webhook_late_capture_moves_to_payment_review(self):
        """A capture arriving for a Cancelled order must be marked Payment Review with no stock changes."""
        initial_stock = self.product.stock
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("5000.00"),
            status='Cancelled',
            is_paid=False,
            razorpay_order_id='order_late_123',
            original_cart_items=[{
                'cart_item_id': 101,
                'product_id': self.product.id,
                'quantity': 2,
                'selected_size': '',
                'price': '5000.00'
            }]
        )

        payload = {
            'event': 'payment.captured',
            'payload': {
                'payment': {
                    'entity': {
                        'id': 'pay_late_123',
                        'order_id': 'order_late_123',
                        'amount': 500000
                    }
                }
            }
        }

        resp = self._post_webhook(payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'status': 'payment_review'})

        order.refresh_from_db()
        self.assertEqual(order.status, 'Payment Review')
        self.assertFalse(order.is_paid)
        self.assertEqual(order.razorpay_payment_id, 'pay_late_123')
        self.assertEqual(order.total_amount, Decimal('5000.00'))

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, initial_stock)

    def test_webhook_duplicate_late_capture(self):
        """Duplicate capture for an order already in Payment Review changes nothing and returns 200 OK."""
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("5000.00"),
            status='Payment Review',
            is_paid=False,
            razorpay_order_id='order_late_dup_123',
            razorpay_payment_id='pay_late_dup_123',
            transaction_id='pay_late_dup_123'
        )

        payload = {
            'event': 'payment.captured',
            'payload': {
                'payment': {
                    'entity': {
                        'id': 'pay_late_dup_123',
                        'order_id': 'order_late_dup_123',
                        'amount': 500000
                    }
                }
            }
        }

        resp = self._post_webhook(payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'status': 'ok'})

        order.refresh_from_db()
        self.assertEqual(order.status, 'Payment Review')
        self.assertFalse(order.is_paid)

    def test_webhook_invalid_signature(self):
        """Webhook with invalid signature returns 400 Bad Request."""
        payload = {
            'event': 'payment.captured',
            'payload': {
                'payment': {
                    'entity': {
                        'id': 'pay_invalid_123',
                        'order_id': 'order_invalid_123',
                        'amount': 500000
                    }
                }
            }
        }

        resp = self._post_webhook(payload, signature='invalid_signature_hex')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json(), {'error': 'Invalid signature'})

    def test_payment_verify_late_capture_renders_payment_review(self):
        """Browser payment_verify for a Cancelled order sets Payment Review and renders neutral page."""
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("5000.00"),
            status='Cancelled',
            is_paid=False,
            razorpay_order_id='order_verify_late_123'
        )

        self.client.force_login(self.user)
        with patch('products.views.get_razorpay_client') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.utility.verify_payment_signature.return_value = True

            resp = self.client.post(reverse('payment_verify'), {
                'razorpay_payment_id': 'pay_verify_late_123',
                'razorpay_order_id': 'order_verify_late_123',
                'razorpay_signature': 'valid_mock_signature'
            })

            self.assertEqual(resp.status_code, 200)
            self.assertTemplateUsed(resp, 'products/payment_review.html')

            order.refresh_from_db()
            self.assertEqual(order.status, 'Payment Review')
            self.assertFalse(order.is_paid)
            self.assertEqual(order.razorpay_payment_id, 'pay_verify_late_123')

    def test_admin_confirm_and_re_reserve_stock(self):
        """Admin action re-reserves stock when available, or warns if insufficient."""
        site = AdminSite()
        admin_obj = OrderAdmin(Order, site)

        # 1. Successful re-reservation
        self.product.stock = 5
        self.product.save()

        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("5000.00"),
            status='Payment Review',
            is_paid=False,
            original_cart_items=[{
                'product_id': self.product.id,
                'quantity': 2,
                'selected_size': '',
                'price': '2500.00'
            }]
        )

        request = MagicMock()
        admin_obj.confirm_and_re_reserve_stock(request, Order.objects.filter(id=order.id))

        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.status, 'Paid')
        self.assertTrue(order.is_paid)
        self.assertEqual(self.product.stock, 3)

        # 2. Out of stock failure
        order2 = Order.objects.create(
            user=self.user,
            total_amount=Decimal("5000.00"),
            status='Payment Review',
            is_paid=False,
            original_cart_items=[{
                'product_id': self.product.id,
                'quantity': 10,
                'selected_size': '',
                'price': '500.00'
            }]
        )

        admin_obj.confirm_and_re_reserve_stock(request, Order.objects.filter(id=order2.id))
        order2.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order2.status, 'Payment Review')
        self.assertFalse(order2.is_paid)
        self.assertEqual(self.product.stock, 3)

    def test_admin_refund_via_razorpay(self):
        """Admin refund calls Razorpay API and marks order Refunded."""
        site = AdminSite()
        admin_obj = OrderAdmin(Order, site)

        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("3500.00"),
            status='Payment Review',
            is_paid=False,
            razorpay_payment_id='pay_refund_test_123'
        )

        request = MagicMock()
        with patch('products.views.get_razorpay_client') as mock_client:
            mock_inst = MagicMock()
            mock_client.return_value = mock_inst
            mock_inst.payment.refund.return_value = {'id': 'rfnd_test_123'}

            admin_obj.refund_via_razorpay(request, Order.objects.filter(id=order.id))

            order.refresh_from_db()
            self.assertEqual(order.status, 'Refunded')
            self.assertEqual(order.refund_id, 'rfnd_test_123')
