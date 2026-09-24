/**
 * Geolocation + coordinates display.
 */
let _currentLocation = null;
let _deliveryEligible = null; // null = not yet checked, true/false = checked

async function loadDeliveryConfig() {
  try {
    const cfg = await api.get('/api/delivery/config');
    const radiusEl = document.getElementById('radius-text');
    const chargeEl = document.getElementById('delivery-charge-text');
    if (radiusEl) radiusEl.textContent = `${cfg.radius_km} km`;
    if (chargeEl) chargeEl.textContent = formatPrice(cfg.delivery_charge);
  } catch (err) {
    console.error('Failed to load delivery config:', err);
  }
}

async function checkDeliveryEligibility(lat, lng) {
  const statusEl = document.getElementById('delivery-eligibility-status');
  try {
    const result = await api.post('/api/delivery/check', { lat, lng });
    _deliveryEligible = result.eligible;
    if (statusEl) {
      statusEl.innerHTML = `<span style="color:var(--${result.eligible ? 'success' : 'error'})">${result.eligible ? '✅' : '🚫'} ${result.message}</span>`;
    }
    if (!result.eligible) {
      showToast(result.message, 'error');
    }
  } catch (err) {
    _deliveryEligible = false;
    if (statusEl) {
      statusEl.innerHTML = `<span style="color:var(--error)">⚠️ We couldn't verify your delivery location. Please try again.</span>`;
    }
  }
  return _deliveryEligible;
}

async function getCurrentLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Geolocation not supported by your browser.'));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      pos => {
        _currentLocation = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        resolve(_currentLocation);
      },
      err => {
        const msgs = {
          1: 'Location permission denied. Please allow location access.',
          2: 'Location unavailable.',
          3: 'Location request timed out.',
        };
        reject(new Error(msgs[err.code] || 'Location error.'));
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  });
}

async function handleGetLocation() {
  const btn = document.getElementById('location-btn');
  const statusEl = document.getElementById('location-status');
  setLoading(btn, true, 'Getting location...');
  try {
    const loc = await getCurrentLocation();
    _currentLocation = loc;
    if (statusEl) {
      statusEl.innerHTML = `<span style="color:var(--success)">📍 Location detected: ${loc.lat.toFixed(5)}, ${loc.lng.toFixed(5)}</span>`;
    }
    // Fill hidden fields
    const latEl = document.getElementById('delivery-lat');
    const lngEl = document.getElementById('delivery-lng');
    if (latEl) latEl.value = loc.lat;
    if (lngEl) lngEl.value = loc.lng;
    showToast('Location captured!', 'success');
    await checkDeliveryEligibility(loc.lat, loc.lng);
  } catch (err) {
    _deliveryEligible = false;
    showToast(err.message, 'error');
    if (statusEl) statusEl.innerHTML = `<span style="color:var(--error)">⚠️ ${err.message}</span>`;
  } finally {
    setLoading(btn, false, '📍 Use My Current Location');
  }
}

function getLocation() { return _currentLocation; }
