from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Cart, CartItem, Category, Order, OrderItem, Product, Size

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
