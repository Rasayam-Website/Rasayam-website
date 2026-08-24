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
            image="mock_ikat.jpg"  # 🌟 Added fake image string
        )
        self.item_phulkari = Product.objects.create(
            name="Heritage Phulkari Suit",
            price=6800,
            category=self.category_punjab,
            seller_tag="Vintage Craft",
            image="mock_phulkari.jpg"  # 🌟 Added fake image string
        )

        self.category_plain = Category.objects.create(name="Plain Cotton", slug="plain-cotton")
        self.category_without_slug = Category.objects.create(name="Unlinked Category")
        self.item_without_image = Product.objects.create(
            name="Minimal Cotton Kurti",
            price=2200,
            category=self.category_plain,
            seller_tag="Everyday Craft",
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

