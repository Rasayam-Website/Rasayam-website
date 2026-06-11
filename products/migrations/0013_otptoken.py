from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0012_remove_banner_banner_active_order_idx_and_more'),
    ]

    operations = [
        # 1. Drop the old flat OTP fields from CustomerProfile
        migrations.RemoveField(model_name='customerprofile', name='otp'),
        migrations.RemoveField(model_name='customerprofile', name='otp_created_at'),

        # 2. Create the new OTPToken table
        migrations.CreateModel(
            name='OTPToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=6)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('is_used', models.BooleanField(default=False)),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('profile', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='otp_tokens',
                    to='products.customerprofile',
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
