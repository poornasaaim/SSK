// Initialize Cart from LocalStorage
let cart = JSON.parse(localStorage.getItem('sskc_cart')) || [];
updateCartCount();

function addToCart(id, name, basePrice, image) {
    const weightSelect = document.getElementById(`weight-${id}`);
    const weight = weightSelect.value;
    
    // Simple logic: if base price is for 1kg, we just pass the base price to cart 
    // and note the weight variant for the admin to see.
    cart.push({ id, name, price: parseFloat(basePrice), weight, image });
    
    localStorage.setItem('sskc_cart', JSON.stringify(cart));
    updateCartCount();
    alert(`${name} (${weight}) added to cart!`);
}

function updateCartCount() {
    const countEl = document.getElementById('cart-count');
    if (countEl) countEl.innerText = cart.length;
}

function getLoggedInUser() {
    return JSON.parse(localStorage.getItem('sskc_user'));
}

function logout() {
    localStorage.removeItem('sskc_user');
    window.location.href = '/login';
}

// Render Cart items on Cart Page
function renderCart() {
    const cartDiv = document.getElementById('cart-items');
    if (!cartDiv) return;
    
    if (cart.length === 0) {
        cartDiv.innerHTML = "<p>Your cart is empty.</p>";
        return;
    }

    let html = "";
    let subtotal = 0;
    cart.forEach((item, index) => {
        subtotal += item.price;
        html += `<div style="display:flex; justify-content:space-between; border-bottom:1px solid #eee; padding:10px 0;">
            <p><strong>${item.name}</strong> (${item.weight})</p>
            <p>₹${item.price} <button onclick="removeFromCart(${index})" style="color:red; border:none; background:none; cursor:pointer; margin-left:10px;">X</button></p>
        </div>`;
    });
    
    document.getElementById('subtotal-display').innerText = subtotal;
    cartDiv.innerHTML = html;
    calculateFinal();
}

function removeFromCart(index) {
    cart.splice(index, 1);
    localStorage.setItem('sskc_cart', JSON.stringify(cart));
    renderCart();
    updateCartCount();
}

function calculateFinal() {
    const subtotal = parseFloat(document.getElementById('subtotal-display').innerText || 0);
    const pincode = document.getElementById('checkout-pincode').value;
    const discount = document.getElementById('checkout-discount').value;

    fetch('/api/validate_checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pincode, discount })
    })
    .then(res => res.json())
    .then(data => {
        const shipping = data.shipping;
        const discountAmt = (subtotal * data.discount_percent) / 100;
        const finalTotal = subtotal + shipping - discountAmt;
        
        document.getElementById('shipping-display').innerText = shipping;
        document.getElementById('discount-display').innerText = `-${discountAmt}`;
        document.getElementById('total-display').innerText = finalTotal;
    });
}

function generateWhatsAppOrder(shopNumber, orderId, total, itemsString) {
    const user = getLoggedInUser();
    const msg = `Hello Santhosh Sai Krishna & Co! %0A%0AI have paid and placed an order.%0A*Order ID:* ${orderId}%0A*Name:* ${user.Full_Name}%0A*Phone:* ${user.Phone_Number}%0A*Items:* ${itemsString}%0A*Total Paid:* ₹${total}%0A%0A*Please find my payment screenshot attached.*`;
    window.location.href = `https://wa.me/91${shopNumber}?text=${msg}`;
}