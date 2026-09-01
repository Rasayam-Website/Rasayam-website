import os, re

base_dir = '/Users/uditiagarwal/Downloads/Rasayam1/Rasayam-website/products/templates/products'
with open(os.path.join(base_dir, 'cart.html'), 'r') as f:
    html = f.read()

target = """            <div style="margin-top: 32px;">
                <a href="{% url 'save_order' %}" id="checkout-link" style="text-decoration: none; display: block;">
                    <button id="checkout-btn" class="btn-cart" style="width: 100%; padding: 20px;">
                        PROCEED TO SECURE PAYMENT
                    </button>
                </a>
                <p style="font-size: 0.63rem; color: #bbb; text-align: center; margin-top: 14px; letter-spacing: 0.5px;">
                    🔒 Powered by Razorpay — 256-bit encryption
                </p>
            </div>"""

replacement = """            <form method="POST" action="{% url 'save_order' %}" id="checkout-form">
                {% csrf_token %}
                {% if user.is_authenticated and addresses %}
                <div style="margin-bottom: 20px; border: 1px solid var(--border); border-radius: 8px; padding: 16px;">
                    <label style="font-size: 0.66rem; letter-spacing: 1.8px; text-transform: uppercase; color: #999; font-weight: 600; display: block; margin-bottom: 10px;">Deliver To</label>
                    <select name="shipping_address_id" id="address-select" style="width: 100%; padding: 12px 14px; border: 1.5px solid #e8e8e8; border-radius: 6px; font-size: 0.85rem; font-family: inherit; color: #1a1a1a; background: #fafafa; outline: none; cursor: pointer; -webkit-appearance: none; background-image: url(&quot;data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23999' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E&quot;); background-repeat: no-repeat; background-position: right 14px center; padding-right: 36px;">
                        {% for addr in addresses %}
                        <option value="{{ addr.id }}" {% if addr.is_default %}selected{% endif %}>{{ addr.full_name }} — {{ addr.address_line1 }}, {{ addr.city }} {{ addr.pincode }}{% if addr.is_default %} ★{% endif %}</option>
                        {% endfor %}
                    </select>
                    <a href="{% url 'address_list' %}" style="display: inline-block; margin-top: 8px; font-size: 0.7rem; color: #c5a059; text-decoration: none; letter-spacing: 0.5px;">+ Manage Addresses</a>
                </div>
                {% elif user.is_authenticated %}
                <div style="margin-bottom: 20px; border: 1px dashed #e8e8e8; border-radius: 8px; padding: 18px; text-align: center;">
                    <p style="font-size: 0.82rem; color: #888; margin: 0 0 10px;">No saved addresses yet</p>
                    <a href="{% url 'address_list' %}" style="font-size: 0.72rem; color: #c5a059; text-decoration: none; font-weight: 600; letter-spacing: 1px; text-transform: uppercase;">+ Add Delivery Address</a>
                </div>
                {% endif %}

                <div style="margin-top: 20px;">
                    <button type="submit" id="checkout-btn" class="btn-cart" style="width: 100%; padding: 20px;"{% if not addresses %} disabled title="Add a delivery address first" style="opacity: 0.5;"{% endif %}>
                        PROCEED TO SECURE PAYMENT
                    </button>
                    <p style="font-size: 0.63rem; color: #bbb; text-align: center; margin-top: 14px; letter-spacing: 0.5px;">
                        🔒 Powered by Razorpay — 256-bit encryption
                    </p>
                </div>
            </form>"""

html = html.replace(target, replacement)
with open(os.path.join(base_dir, 'cart.html'), 'w') as f:
    f.write(html)
print("cart.html patched.")
