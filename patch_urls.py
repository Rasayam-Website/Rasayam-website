import os, re

base_dir = '/Users/uditiagarwal/Downloads/Rasayam1/Rasayam-website/products'
with open(os.path.join(base_dir, 'urls.py'), 'r') as f:
    urls_code = f.read()

address_urls = """
    # --- Addresses ---
    path('account/addresses/', views.address_list, name='address_list'),
    path('account/addresses/add/', views.address_create, name='address_create'),
    path('account/addresses/<int:pk>/edit/', views.address_edit, name='address_edit'),
    path('account/addresses/<int:pk>/delete/', views.address_delete, name='address_delete'),
    path('account/addresses/<int:pk>/default/', views.address_set_default, name='address_set_default'),

    # --- Orders & Payments ---"""

if 'account/addresses/' not in urls_code:
    urls_code = urls_code.replace('# --- Orders & Payments ---', address_urls)
    with open(os.path.join(base_dir, 'urls.py'), 'w') as f:
        f.write(urls_code)

print("urls.py patched.")
