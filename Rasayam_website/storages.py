"""
Custom django-storages backends.

S3StaticStorage  → reads AWS_STATIC_BUCKET_NAME, stores under static/ prefix.
S3MediaStorage   → reads AWS_STORAGE_BUCKET_NAME, stores under media/ prefix.

Both inherit from S3Boto3Storage so all AWS_S3_* settings from settings.py apply.
"""
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class S3StaticStorage(S3Boto3Storage):
    bucket_name = settings.AWS_STATIC_BUCKET_NAME if hasattr(settings, 'AWS_STATIC_BUCKET_NAME') else None
    location = 'static'
    default_acl = 'public-read'
    querystring_auth = False
    file_overwrite = True  # Deterministic hashed filenames — overwrite is safe


class S3MediaStorage(S3Boto3Storage):
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME if hasattr(settings, 'AWS_STORAGE_BUCKET_NAME') else None
    location = 'media'
    default_acl = None  # Inherit bucket/object policy; no public-read by default
    file_overwrite = False
