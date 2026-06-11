from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0013_otptoken'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='stock',
            field=models.PositiveIntegerField(default=0, help_text='Available units. 0 = out of stock.'),
        ),
        migrations.AddField(
            model_name='order',
            name='shipping_address',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='order',
            name='transaction_id',
            field=models.CharField(
                blank=True, max_length=100, null=True, unique=True,
                help_text='Payment gateway transaction reference.',
            ),
        ),
    ]
