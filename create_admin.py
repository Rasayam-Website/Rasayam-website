import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Rasayam_website.settings')
django.setup()

from django.contrib.auth.models import User

username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@rasayamglobal.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

if not password:
    print("ERROR: DJANGO_SUPERUSER_PASSWORD environment variable must be set.", file=sys.stderr)
    sys.exit(1)

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print(f'Admin user "{username}" created successfully!')
else:
    admin_user = User.objects.get(username=username)
    admin_user.set_password(password)
    admin_user.email = email
    admin_user.is_superuser = True
    admin_user.is_staff = True
    admin_user.save()
    print(f'Admin user "{username}" updated successfully!')
