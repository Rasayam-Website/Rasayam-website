# Generated migration to add database indexes for high-traffic performance

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0010_order_original_cart_items'),
    ]

    operations = [
        # Category indexes for fast lookups
        migrations.AlterField(
            model_name='category',
            name='slug',
            field=models.SlugField(unique=True, db_index=True, blank=True, null=True),
        ),
        
        # Product indexes for search and filtering
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['name'], name='product_name_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['category'], name='product_category_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['seller_tag'], name='product_seller_tag_idx'),
        ),
        
        # CustomerProfile indexes for authentication
        migrations.AddIndex(
            model_name='customerprofile',
            index=models.Index(fields=['phone_number'], name='customer_phone_idx'),
        ),
        migrations.AddIndex(
            model_name='customerprofile',
            index=models.Index(fields=['user'], name='customer_user_idx'),
        ),
        
        # Order indexes for user order lookups
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['user', 'created_at'], name='order_user_created_idx'),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['razorpay_order_id'], name='order_razorpay_idx'),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['is_paid'], name='order_is_paid_idx'),
        ),
        
        # Cart indexes
        migrations.AddIndex(
            model_name='cart',
            index=models.Index(fields=['user'], name='cart_user_idx'),
        ),
        migrations.AddIndex(
            model_name='cartitem',
            index=models.Index(fields=['cart'], name='cartitem_cart_idx'),
        ),
        
        # ProductImage indexes for gallery loading
        migrations.AddIndex(
            model_name='productimage',
            index=models.Index(fields=['product'], name='productimage_product_idx'),
        ),
        
        # Review indexes
        migrations.AddIndex(
            model_name='review',
            index=models.Index(fields=['product', 'is_verified'], name='review_product_verified_idx'),
        ),
        
        # Banner and PromoBox indexes
        migrations.AddIndex(
            model_name='banner',
            index=models.Index(fields=['active', 'order'], name='banner_active_order_idx'),
        ),
        migrations.AddIndex(
            model_name='promobox',
            index=models.Index(fields=['order'], name='promobox_order_idx'),
        ),
    ]
