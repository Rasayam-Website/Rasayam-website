import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Rasayam_website.settings')
django.setup()

from django.contrib.auth.models import User

if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@rasayam.com', 'Rasayam@Admin123')
    print('Admin user created successfully!')
else:
    admin_user = User.objects.get(username='admin')
    admin_user.set_password('Rasayam@Admin123')
    admin_user.is_superuser = True
    admin_user.is_staff = True
    admin_user.save()
    print('Admin user already existed, password reset successfully!')

print('Username: admin')
print('Password: Rasayam@Admin123')
