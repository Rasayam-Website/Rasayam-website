from django.core.management.base import BaseCommand
from django.utils import timezone
from products.models import Order, Product
from django.db import transaction
from django.db.models import F

class Command(BaseCommand):
    help = 'Auto-cancels pending orders older than 20 minutes and restores their stock levels.'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timezone.timedelta(minutes=20)
        expired_orders = Order.objects.filter(status='Pending', created_at__lt=cutoff)
        
        count = 0
        for order in expired_orders:
            with transaction.atomic():
                # Re-fetch order and lock it
                order = Order.objects.select_for_update().get(pk=order.pk)
                if order.status == 'Pending':
                    # Restore stock using the original_cart_items snapshot
                    snapshot = order.original_cart_items or []
                    for entry in snapshot:
                        product_id = entry.get('product_id')
                        quantity = int(entry.get('quantity') or 0)
                        if product_id and quantity > 0:
                            Product.objects.filter(pk=product_id).update(
                                stock=F('stock') + quantity
                            )
                    order.status = 'Cancelled'
                    order.save(update_fields=['status'])
                    count += 1
        
        self.stdout.write(self.style.SUCCESS(f"Successfully cancelled {count} expired pending orders."))
