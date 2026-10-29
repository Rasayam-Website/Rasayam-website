"""
URL configuration for Rasayam_website project.
"""

import logging
from django.contrib import admin
from django.urls import path, include, reverse
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse, HttpResponse
from django.db import connection
from django.core.cache import cache
from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap

logger = logging.getLogger(__name__)


def health_check(request):
    """
    Sanitized health check endpoint.
    Verifies DB, Cache, and S3 connectivity without leaking internal exception stack traces.
    """
    checks = {}
    ok = True

    # 1. Database
    try:
        connection.ensure_connection()
        checks['db'] = 'ok'
    except Exception as e:
        logger.error("Health check DB connection failed: %s", e)
        checks['db'] = 'unavailable'
        ok = False

    # 2. Cache
    try:
        cache.set('health', '1', timeout=5)
        assert cache.get('health') == '1'
        checks['cache'] = 'ok'
    except Exception as e:
        logger.error("Health check Cache failed: %s", e)
        checks['cache'] = 'unavailable'
        ok = False

    # 3. S3 (only when configured — skipped in local/dev)
    bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '')
    if bucket:
        try:
            import boto3
            from botocore.config import Config
            s3 = boto3.client(
                's3',
                region_name=getattr(settings, 'AWS_S3_REGION_NAME', None),
                config=Config(connect_timeout=3, read_timeout=3),
            )
            s3.head_bucket(Bucket=bucket)
            checks['s3'] = 'ok'
        except Exception as e:
            logger.error("Health check S3 bucket %s failed: %s", bucket, e)
            checks['s3'] = 'unavailable'
            ok = False
    else:
        checks['s3'] = 'skipped'

    status = 200 if ok else 503
    return JsonResponse({'status': 'ok' if ok else 'degraded', 'checks': checks}, status=status)


def robots_txt(request):
    sitemap_url = request.build_absolute_uri('/sitemap.xml')
    content = (
        "User-agent: *\n"
        "Disallow: /admin/\n"
        "Disallow: /account/\n"
        "Disallow: /cart/\n"
        "Allow: /\n\n"
        f"Sitemap: {sitemap_url}\n"
    )
    return HttpResponse(content, content_type="text/plain")


def favicon_ico(request):
    # Return 204 No Content so browsers and bots stop generating 404 error logs
    return HttpResponse(status=204)


# --- Sitemaps for SEO ---
class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return [
            'index', 'shop', 'about_us', 'about', 'contact',
            'terms', 'privacy_policy', 'shipping_policy', 'refund_policy', 'faq'
        ]

    def location(self, item):
        return reverse(item)


class ProductSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.9

    def items(self):
        from products.models import Product
        return Product.objects.all().order_by('-id')

    def location(self, obj):
        if obj.slug:
            return reverse('product_detail_slug', args=[obj.slug])
        return reverse('product_detail', args=[obj.id])


class CategorySitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        from products.models import Category
        return Category.objects.exclude(slug__isnull=True).exclude(slug='').order_by('order')

    def location(self, obj):
        return reverse('category_detail', args=[obj.slug])


sitemaps = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'categories': CategorySitemap,
}

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('favicon.ico', favicon_ico, name='favicon_ico'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('admin/', admin.site.urls),
    path('', include('products.urls')),
]

# This tells Django how to find your product images while you are developing
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
