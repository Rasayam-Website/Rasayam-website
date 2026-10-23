"""
URL configuration for Rasayam_website project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse, HttpResponse
from django.db import connection
from django.core.cache import cache


def health_check(request):
    checks = {}
    ok = True

    # 1. Database
    try:
        connection.ensure_connection()
        checks['db'] = 'ok'
    except Exception as e:
        checks['db'] = f'error: {e}'
        ok = False

    # 2. Cache
    try:
        cache.set('health', '1', timeout=5)
        assert cache.get('health') == '1'
        checks['cache'] = 'ok'
    except Exception as e:
        checks['cache'] = f'error: {e}'
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
            checks['s3'] = f'error: {e}'
            ok = False
    else:
        checks['s3'] = 'skipped'

    status = 200 if ok else 503
    return JsonResponse({'status': 'ok' if ok else 'degraded', 'checks': checks}, status=status)

def robots_txt(request):
    content = "User-agent: *\nDisallow: /admin/\nDisallow: /account/\nDisallow: /cart/\nAllow: /\n"
    return HttpResponse(content, content_type="text/plain")


def favicon_ico(request):
    # Return 204 No Content so browsers and bots stop generating 404 error logs
    return HttpResponse(status=204)


urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('favicon.ico', favicon_ico, name='favicon_ico'),
    path('admin/', admin.site.urls),
    path('', include('products.urls')),
]

# This tells Django how to find your product images while you are developing
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
