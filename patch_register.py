import os, re

base_dir = '/Users/uditiagarwal/Downloads/Rasayam1/Rasayam-website/products/templates/products'
with open(os.path.join(base_dir, 'register.html'), 'r') as f:
    html = f.read()

target = """                <div class="form-row">
                    <div class="form-group">
                        <label for="reg-city">City</label>
                        <input type="text" id="reg-city" name="city" placeholder="e.g. Mumbai" required>
                    </div>
                    <div class="form-group">
                        <label for="reg-state">State <span class="optional">(Optional)</span></label>
                        <input type="text" id="reg-state" name="state" placeholder="e.g. Maharashtra">
                    </div>
                </div>"""

html = html.replace(target, '')
with open(os.path.join(base_dir, 'register.html'), 'w') as f:
    f.write(html)
print("register.html patched.")
