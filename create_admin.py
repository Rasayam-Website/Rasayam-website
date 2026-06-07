import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Rasayam_website.settings')
django.setup()

from django.contrib.auth.models import User

if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@rasayam.com', 'Rasayam@Admin123')
    print('Admin user created successfully!')
    print('Username: admin')
    print('Password: Rasayam@Admin123')
else:
    print('Admin user already exists')
