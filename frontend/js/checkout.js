/**
 * Checkout flow.
 */
let _checkoutOrderId = null;
let _orderType = 'DELIVERY';
let _addressMode = 'manual'; // 'manual' or 'gps'
let _loggedInUser = null;

function setOrderType(type) {
  _orderType = type;
  const deliverySection = document.getElementById('delivery-section');
  const pickupNote = document.getElementById('pickup-note');
  const deliveryBtn = document.getElementById('type-delivery');
  const pickupBtn = document.getElementById('type-pickup');

  if (type === 'DELIVERY') {
    deliverySection && deliverySection.classList.remove('hidden');
    pickupNote && pickupNote.classList.add('hidden');
    deliveryBtn && deliveryBtn.classList.add('active');
    pickupBtn && pickupBtn.classList.remove('active');
  } else {
    deliverySection && deliverySection.classList.add('hidden');
    pickupNote && pickupNote.classList.remove('hidden');
    pickupBtn && pickupBtn.classList.add('active');
    deliveryBtn && deliveryBtn.classList.remove('active');
  }
}

function setAddressMode(mode) {
  _addressMode = mode;
  const manualBtn = document.getElementById('manual-address-btn');
  const gpsBtn = document.getElementById('gps-address-btn');
  const manualSection = document.getElementById('manual-address-section');
  const gpsSection = document.getElementById('gps-address-section');

  if (mode === 'manual') {
    manualSection && manualSection.classList.remove('hidden');
    gpsSection && gpsSection.classList.add('hidden');
    manualBtn && manualBtn.classList.remove('btn-outline');
    manualBtn && manualBtn.classList.add('btn-primary');
    gpsBtn && gpsBtn.classList.add('btn-outline');
    gpsBtn && gpsBtn.classList.remove('btn-primary');
  } else {
    manualSection && manualSection.classList.add('hidden');
    gpsSection && gpsSection.classList.remove('hidden');
    gpsBtn && gpsBtn.classList.remove('btn-outline');
    gpsBtn && gpsBtn.classList.add('btn-primary');
    manualBtn && manualBtn.classList.add('btn-outline');
    manualBtn && manualBtn.classList.remove('btn-primary');
  }
}

async function handleContinueToPayment() {
  const btn = document.getElementById('continue-btn');

  // Validate customer details
  const customerName = document.getElementById('customer-name')?.value?.trim();
  const customerMobile = document.getElementById('customer-mobile')?.value?.trim();

  if (!customerName) {
    showToast('Please enter your full name.', 'warning');
    return;
  }

  if (!customerMobile || customerMobile.length < 10) {
    showToast('Please enter a valid mobile number.', 'warning');
    return;
  }

  const deliveryData = {
    order_type: _orderType,
    notes: document.getElementById('notes')?.value || '',
    customer_name: customerName,
    customer_mobile: customerMobile,
  };

  if (_orderType === 'DELIVERY') {
    const lat = parseFloat(document.getElementById('delivery-lat')?.value || '');
    const lng = parseFloat(document.getElementById('delivery-lng')?.value || '');

    if (!lat || !lng) {
      showToast('Please select your delivery location (either type address or use GPS).', 'warning');
      return;
    }

    if (_deliveryEligible === false) {
      showToast('Sorry, delivery is available only within 5 km of our shop.', 'error');
      return;
    }

    // Collect address fields
    if (_addressMode === 'manual') {
      const houseFlatDoor = document.getElementById('delivery-house-flat-door')?.value?.trim();
      const streetArea = document.getElementById('delivery-street-area')?.value?.trim();
      const city = document.getElementById('delivery-city')?.value?.trim();
      const state = document.getElementById('delivery-state')?.value?.trim();
      const pincode = document.getElementById('delivery-pincode')?.value?.trim();
      const landmark = document.getElementById('delivery-landmark')?.value?.trim();

      if (!houseFlatDoor || !streetArea || !city || !state || !pincode) {
        showToast('Please fill all required address fields.', 'warning');
        return;
      }

      const completeAddress = `${houseFlatDoor}, ${streetArea}, ${city} - ${pincode}${landmark ? ', ' + landmark : ''}`;

      deliveryData.delivery_address = completeAddress;
      deliveryData.delivery_house_flat_door = houseFlatDoor;
      deliveryData.delivery_street_area = streetArea;
      deliveryData.delivery_city = city;
      deliveryData.delivery_state = state;
      deliveryData.delivery_pincode = pincode;
      if (landmark) deliveryData.delivery_landmark = landmark;
    } else {
      if (!document.getElementById('delivery-address')?.value) {
        showToast('Please detect your location first.', 'warning');
        return;
      }
      // For GPS mode, use the Google Maps link as the address
      deliveryData.delivery_address = document.getElementById('delivery-address').value;
    }

    deliveryData.delivery_lat = lat;
    deliveryData.delivery_lng = lng;
  }

  // Save delivery data to session storage for payment method page
  sessionStorage.setItem('pending_delivery_data', JSON.stringify(deliveryData));

  setLoading(btn, true, 'Proceeding...');
  try {
    showToast('Proceeding to payment method...', 'success');
    setTimeout(() => window.location.href = '/customer/payment-method.html', 500);
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    setLoading(btn, false, 'Continue to Payment →');
  }
}

async function loadCheckoutSummary() {
  try {
    const cart = await api.get('/api/cart');
    const itemsEl = document.getElementById('checkout-items');
    const subtotalEl = document.getElementById('checkout-subtotal');
    const deliveryEl = document.getElementById('checkout-delivery');
    const totalEl = document.getElementById('checkout-total');

    if (itemsEl) {
      itemsEl.innerHTML = cart.items.map(item =>
        `<div style="display:flex;justify-content:space-between;padding:.3rem 0;font-size:.9rem">
          <span>${item.product_name} × ${item.quantity}</span>
          <span>${formatPrice(item.subtotal)}</span>
        </div>`
      ).join('');
    }
    if (subtotalEl) subtotalEl.textContent = formatPrice(cart.subtotal);
    if (deliveryEl) deliveryEl.textContent = _orderType === 'DELIVERY' ? '₹30' : '₹0';
    if (totalEl) {
      const total = cart.subtotal + (_orderType === 'DELIVERY' ? 30 : 0);
      totalEl.textContent = formatPrice(total);
    }
  } catch (err) {
    console.error('Checkout summary error:', err);
  }
}

async function loadCustomerDetails() {
  try {
    const user = JSON.parse(localStorage.getItem('tm_user') || '{}');
    _loggedInUser = user;
    // Pre-fill from login data, but allow editing
    const nameEl = document.getElementById('customer-name');
    const mobileEl = document.getElementById('customer-mobile');

    if (nameEl && user.name) {
      nameEl.value = user.name;
    }
    if (mobileEl && user.mobile) {
      mobileEl.value = user.mobile;
    }

    console.log('Customer details loaded:', { name: user.name, mobile: user.mobile });
  } catch (err) {
    console.error('Failed to load customer details:', err);
  }
}
