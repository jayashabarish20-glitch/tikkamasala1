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
      reject(new Error('Geolocation API not supported by your browser.'));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      pos => {
        _currentLocation = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        console.log('Location obtained:', _currentLocation);
        resolve(_currentLocation);
      },
      err => {
        const msgs = {
          1: 'Location permission denied. Please allow location access and try again.',
          2: 'Location is unavailable. Please check if location services are enabled on your device.',
          3: 'Location request timed out. Please try again.',
        };
        const errorMsg = msgs[err.code] || 'Location error: ' + err.message;
        console.error('Geolocation error code:', err.code, 'message:', err.message);
        reject(new Error(errorMsg));
      },
      { timeout: 15000, enableHighAccuracy: true, maximumAge: 0 }
    );
  });
}

async function handleGetLocation() {
  const btn = document.getElementById('location-btn');
  const statusEl = document.getElementById('location-status');
  const displayEl = document.getElementById('gps-address-display');
  const coordEl = document.getElementById('gps-coordinates');
  const mapsEl = document.getElementById('gps-maps-link');
  const addressEl = document.getElementById('delivery-address');

  setLoading(btn, true, 'Getting location...');
  try {
    const loc = await getCurrentLocation();
    _currentLocation = loc;

    if (statusEl) {
      statusEl.innerHTML = `<span style="color:var(--success)">✅ Location detected successfully</span>`;
    }

    // Fill hidden fields
    const latEl = document.getElementById('delivery-lat');
    const lngEl = document.getElementById('delivery-lng');
    if (latEl) latEl.value = loc.lat;
    if (lngEl) lngEl.value = loc.lng;

    // Generate and display Google Maps link
    const googleMapsLink = `https://www.google.com/maps?q=${loc.lat.toFixed(6)},${loc.lng.toFixed(6)}`;
    if (addressEl) addressEl.value = googleMapsLink;

    // Display coordinates and maps link
    if (coordEl) {
      coordEl.textContent = `${loc.lat.toFixed(6)}, ${loc.lng.toFixed(6)}`;
    }
    if (mapsEl) {
      mapsEl.innerHTML = `<a href="${googleMapsLink}" target="_blank" style="display:inline-block;padding:.5rem 1rem;background:var(--primary);color:white;border-radius:4px;text-decoration:none;font-size:.85rem">🗺️ View on Google Maps</a>`;
    }
    if (displayEl) {
      displayEl.classList.remove('hidden');
    }

    showToast('Location captured! Checking delivery availability...', 'success');
    await checkDeliveryEligibility(loc.lat, loc.lng);
  } catch (err) {
    _deliveryEligible = false;
    showToast(err.message, 'error');
    if (statusEl) statusEl.innerHTML = `<span style="color:var(--error)">⚠️ ${err.message}</span>`;
    if (displayEl) displayEl.classList.add('hidden');
  } finally {
    setLoading(btn, false, '📍 Get My Current Location');
  }
}

function getLocation() { return _currentLocation; }
