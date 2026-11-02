/* =========================================
   RASAYAM UNIFIED CART ENGINE
   ========================================= */

// 1. Helper to get CSRF token (Required for Secure Orders)
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// 2. Add to Cart (Silent/AJAX)
function addToCartAsync(productId, selectedSize = "", trigger = null) {
    const btn = trigger || document.getElementById(`add-btn-${productId}`);
    if (btn) {
        btn.innerText = "ADDING...";
        btn.classList.add("is-loading");
        btn.setAttribute("aria-busy", "true");
    }

    const params = new URLSearchParams();
    if (selectedSize) {
        params.set("selected_size", selectedSize);
    }
    const queryString = params.toString() ? `?${params.toString()}` : "";

    fetch(`/add-to-cart-ajax/${productId}/${queryString}`, {
        method: 'GET',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Update Navbar Badge (both desktop and mobile)
            document.querySelectorAll('#cart-count, .mobile-cart-badge, .cart-badge').forEach(badge => {
                badge.innerText = data.cart_count;
            });

            // Transform Button to "View Bag" Link
            if (btn) {
                btn.innerText = "IN SELECTION - VIEW BAG";
                btn.classList.remove("is-loading");
                btn.classList.add("is-in-cart");
                btn.removeAttribute("aria-busy");
                btn.disabled = false;
                btn.onclick = () => window.location.href = "/cart/";
            }
        }
    })
    .catch(error => {
        console.error('Cart Error:', error);
        if (btn) {
            btn.innerText = "ADD TO SELECTION";
            btn.classList.remove("is-loading");
            btn.removeAttribute("aria-busy");
        }
    });
}

document.addEventListener("click", function(event) {
    const scrollLink = event.target.closest(
        'a[href*="/add-to-cart/"], a[href*="/decrease-item/"], a[href*="/remove-from-cart/"]'
    );

    if (scrollLink) {
        sessionStorage.setItem("rasayamScrollY", String(window.scrollY));
    }
});

window.addEventListener("load", function() {
    const savedScrollY = sessionStorage.getItem("rasayamScrollY");
    if (savedScrollY !== null) {
        sessionStorage.removeItem("rasayamScrollY");
        window.scrollTo(0, parseInt(savedScrollY, 10) || 0);
    }
});
