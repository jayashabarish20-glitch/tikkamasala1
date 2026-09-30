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
    await handleOnlinePayment();
    return;
  }

  if (_selectedPaymentMethod !== 'COD') {
    showToast('Invalid payment method.', 'error');
    return;
  }

  // Handle Cash on Delivery
  await handleCashOnDelivery();
}

async function handleOnlinePayment() {
  const btn = document.getElementById('place-order-btn');
  const deliveryData = JSON.parse(sessionStorage.getItem('pending_delivery_data') || '{}');

  if (!deliveryData || !deliveryData.order_type) {
    showToast('Error: Delivery data not found. Please go back to checkout.', 'error');
    return;
  }

  setLoading(btn, true, 'Initiating payment...');
  try {
    // Create Razorpay order for online payment
    const paymentData = await api.post('/api/payments/create-order', {
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
    });

    // Store order data for payment verification
    sessionStorage.setItem('pending_payment_order_data', JSON.stringify(paymentData.order_data));

    // DEMO MODE
    if (paymentData.demo_mode || paymentData.razorpay_key_id === 'DEMO_MODE') {
      showToast('Demo mode — simulating payment...', 'info');
      setTimeout(async () => {
        await verifyOnlinePayment({
          razorpay_order_id: paymentData.razorpay_order_id,
          razorpay_payment_id: 'demo_pay_' + Date.now(),
          razorpay_signature: 'demo_signature',
        });
      }, 1200);
      setLoading(btn, false, 'Place Order');
      return;
    }

    // PRODUCTION - Open Razorpay
    const user = getUser();
    const options = {
      key: paymentData.razorpay_key_id,
      amount: paymentData.amount,
      currency: paymentData.currency,
      name: 'Tikka Masala Chat Corner',
      description: 'Order Payment',
      image: 'https://images.unsplash.com/photo-1606491956689-2ea866880c84?w=100',
      order_id: paymentData.razorpay_order_id,
      handler: async function(response) {
        await verifyOnlinePayment(response);
      },
      prefill: {
        name: user.name || '',
        contact: user.mobile || '',
      },
      theme: { color: '#C8102E' },
      modal: {
        ondismiss: function() {
          showToast('Payment was cancelled.', 'warning');
          setLoading(btn, false, 'Place Order');
        }
      }
    };

    const rzp = new Razorpay(options);
    rzp.open();
    setLoading(btn, false, 'Place Order');
  } catch (err) {
    showToast(err.message, 'error');
    setLoading(btn, false, 'Place Order');
  }
}

async function verifyOnlinePayment(response) {
  const overlay = document.getElementById('loading-overlay');
  if (overlay) overlay.classList.remove('hidden');
  try {
    const orderData = JSON.parse(sessionStorage.getItem('pending_payment_order_data') || '{}');
    const result = await api.post('/api/payments/verify-online', {
      razorpay_order_id: response.razorpay_order_id,
      razorpay_payment_id: response.razorpay_payment_id,
      razorpay_signature: response.razorpay_signature,
      order_data: orderData,
    });

    // Clear session data
    sessionStorage.removeItem('pending_delivery_data');
    sessionStorage.removeItem('pending_payment_order_data');

    // Store order info
    sessionStorage.setItem('recent_order_id', result.order_id);
    sessionStorage.setItem('recent_order_number', result.order_number);
    sessionStorage.setItem('recent_payment_method', 'ONLINE');

    showToast('Payment successful! Order created.', 'success');
    setTimeout(() => window.location.href = `/customer/order-success.html?order_id=${result.order_id}&order_number=${result.order_number}`, 800);
  } catch (err) {
    showToast('Payment verification failed: ' + err.message, 'error');
    if (overlay) overlay.classList.add('hidden');
  }
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
