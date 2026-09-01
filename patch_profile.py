import os, re

base_dir = '/Users/uditiagarwal/Downloads/Rasayam1/Rasayam-website/products/templates/products'
with open(os.path.join(base_dir, 'profile.html'), 'r') as f:
    html = f.read()

target = """                <div class="profile-detail">
                    <span>Shipping Muse</span>
                    <strong>
                        {% if user.customerprofile.city and user.customerprofile.state %}
                            {{ user.customerprofile.city }}, {{ user.customerprofile.state }}
                        {% elif user.customerprofile.city %}
                            {{ user.customerprofile.city }}
                        {% elif user.customerprofile.state %}
                            {{ user.customerprofile.state }}
                        {% else %}
                            Not Provided
                        {% endif %}
                    </strong>
                </div>"""

replacement = """                <div class="profile-detail">
                    <span>Delivery Addresses</span>
                    <strong>
                        <a href="{% url 'address_list' %}" style="color: #c5a059; text-decoration: none; font-weight: 600; font-size: 0.82rem;">Manage Addresses →</a>
                    </strong>
                </div>"""

html = html.replace(target, replacement)
with open(os.path.join(base_dir, 'profile.html'), 'w') as f:
    f.write(html)
print("profile.html patched.")
