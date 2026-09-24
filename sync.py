import subprocess
import os

files_to_sync = [
    "products/delhivery.py",
    "products/templates/products/track_order.html",
    "products/templates/products/pincode_check_snippet.html",
    "products/templates/products/address_edit.html",
    "products/templates/products/addresses.html",
    "products/migrations/0018_delhivery_shipping_fields.py",
    "products/models.py",
    "products/views.py",
    "products/urls.py",
    "products/admin.py",
    "products/templates/products/base.html"
]

for f in files_to_sync:
    print(f"Syncing {f}...")
    result = subprocess.run([
        "ssh", "-n", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no", 
        "-i", os.path.expanduser(r"~\.ssh\rasayam-key.pem"), 
        "ubuntu@43.204.238.250", 
        f"cat /srv/rasayam/{f}"
    ], capture_output=True)
    
    if result.returncode == 0:
        os.makedirs(os.path.dirname(f) or ".", exist_ok=True)
        content = result.stdout.decode('utf-8', errors='replace').replace('\r\n', '\n')
        with open(f, "w", encoding="utf-8") as out:
            out.write(content)
        print(f"Saved {f}")
    else:
        print(f"Failed {f}: {result.stderr.decode('utf-8', errors='replace')}")
