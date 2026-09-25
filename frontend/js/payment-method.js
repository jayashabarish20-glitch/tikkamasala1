/**
 * Payment Method Selection and Cash on Delivery
 */
let _selectedPaymentMethod = null;

function selectPaymentMethod(method) {
  _selectedPaymentMethod = method;

  // Update radio button
  document.getElementById('payment-cod').checked = (method === 'COD');
  document.getElementById('payment-online').checked = (method === 'ONLINE');

  // Update option styling
  const codOption = document.getElementById('cod-option');
  const onlineOption = document.getElementById('online-option');
  const placeOrderBtn = document.getElementById('place-order-btn');

  if (method === 'COD') {
    codOption.style.borderColor = 'var(--primary)';
    codOption.style.backgroundColor = 'rgba(var(--primary-rgb), 0.05)';
    onlineOption.style.borderColor = '#ddd';
    onlineOption.style.backgroundColor = 'transparent';
    placeOrderBtn.disabled = false;
    placeOrderBtn.style.opacity = '1';
    placeOrderBtn.style.cursor = 'pointer';
  } else if (method === 'ONLINE') {
    onlineOption.style.borderColor = 'var(--primary)';
    onlineOption.style.backgroundColor = 'rgba(var(--primary-rgb), 0.05)';
    codOption.style.borderColor = '#ddd';
    codOption.style.backgroundColor = 'transparent';
    placeOrderBtn.disabled = false;
    placeOrderBtn.style.opacity = '1';
    placeOrderBtn.style.cursor = 'pointer';
  }
}

async function loadPaymentMethodSummary() {
  try {
    const cart = await api.get('/api/cart');
    const itemsEl = document.getElementById('payment-items');
    const subtotalEl = document.getElementById('payment-subtotal');
    const deliveryEl = document.getElementById('payment-delivery');
    const totalEl = document.getElementById('payment-total');

    if (itemsEl) {
      itemsEl.innerHTML = cart.items.map(item =>
        `<div style="display:flex;justify-content:space-between;padding:.3rem 0;font-size:.9rem">
          <span>${item.product_name} × ${item.quantity}</span>
          <span>${formatPrice(item.subtotal)}</span>
        </div>`
      ).join('');
    }

    if (subtotalEl) subtotalEl.textContent = formatPrice(cart.subtotal);
    if (deliveryEl) deliveryEl.textContent = '₹30';
    if (totalEl) {
      const total = cart.subtotal + 30; // Always include delivery fee for now
      totalEl.textContent = formatPrice(total);
    }

    // Auto-select COD
    selectPaymentMethod('COD');
  } catch (err) {
    console.error('Payment method summary error:', err);
  }
}

async function handlePlaceOrder() {
  if (!_selectedPaymentMethod) {
    showToast('Please select a payment method.', 'warning');
    return;
  }

  if (_selectedPaymentMethod === 'ONLINE') {
    showToast('Online payment is coming soon.', 'info');
    return;
  }

  if (_selectedPaymentMethod !== 'COD') {
    showToast('Invalid payment method.', 'error');
    return;
  }

  // Handle Cash on Delivery
  await handleCashOnDelivery();
}

async function handleCashOnDelivery() {
  const btn = document.getElementById('place-order-btn');
  const deliveryData = JSON.parse(sessionStorage.getItem('pending_delivery_data') || '{}');

  if (!deliveryData || !deliveryData.order_type) {
    showToast('Error: Delivery data not found. Please go back to checkout.', 'error');
    return;
  }

  // Prepare order payload
  const payload = {
    order_type: deliveryData.order_type,
    delivery_address: deliveryData.delivery_address,
    delivery_house_flat_door: deliveryData.delivery_house_flat_door,
    delivery_street_area: deliveryData.delivery_street_area,
    delivery_city: deliveryData.delivery_city,
    delivery_state: deliveryData.delivery_state,
    delivery_pincode: deliveryData.delivery_pincode,
    delivery_landmark: deliveryData.delivery_landmark,
    delivery_lat: deliveryData.delivery_lat,
    delivery_lng: deliveryData.delivery_lng,
    notes: deliveryData.notes,
    payment_method: 'COD',
  };

  setLoading(btn, true, 'Creating order...');
  try {
    const order = await api.post('/api/orders', payload);

    // Clear session data
    sessionStorage.removeItem('pending_delivery_data');

    showToast('Order created successfully!', 'success');

    // Redirect to order confirmation
    sessionStorage.setItem('recent_order_id', order.order_id);
    sessionStorage.setItem('recent_order_number', order.order_number);
    sessionStorage.setItem('recent_order_total', order.total);
    sessionStorage.setItem('recent_payment_method', 'COD');

    setTimeout(() => window.location.href = '/customer/order-confirmation.html', 800);
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    setLoading(btn, false, 'Place Order');
  }
}
