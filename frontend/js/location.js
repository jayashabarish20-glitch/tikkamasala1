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

    const GOOD_ENOUGH_M = 50;      // stop sampling early once this accurate
    const MAX_ACCEPTABLE_M = 500;  // reject anything worse than this
    const SAMPLE_WINDOW_MS = 3000;  // 3 seconds — fail fast on desktop without GPS

    let best = null;
    let done = false;
    let watchId = null;

    const finish = () => {
      done = true;
      clearTimeout(timer);
      if (watchId !== null) navigator.geolocation.clearWatch(watchId);
      if (!best) {
        reject(new Error('Location request timed out. Please try again.'));
        return;
      }
      console.log(`Best location: lat=${best.lat} lng=${best.lng} accuracy=${Math.round(best.accuracy)} meters`);
      if (best.accuracy > MAX_ACCEPTABLE_M) {
        reject(new Error(
          `Your current location accuracy is too low (±${Math.round(best.accuracy)} m). ` +
          'Please enable device location/GPS and try again.'
        ));
        return;
      }
      _currentLocation = best;
      resolve(best);
    };

    const timer = setTimeout(finish, SAMPLE_WINDOW_MS);

    watchId = navigator.geolocation.watchPosition(
      pos => {
        if (done) return;
        const { latitude: lat, longitude: lng, accuracy } = pos.coords;
        console.log(
          `Location obtained: lat=${lat} lng=${lng} accuracy=${Math.round(accuracy)} meters ` +
          `timestamp=${new Date(pos.timestamp).toISOString()}`
        );
        if (!best || accuracy < best.accuracy) best = { lat, lng, accuracy };
        if (best.accuracy <= GOOD_ENOUGH_M) finish();
      },
      err => {
        if (done) return;
        console.error('Geolocation error code:', err.code, 'message:', err.message);
        // A timeout on one sample is not fatal while the window is still open.
        if (err.code === 3 && best) return;
        done = true;
        clearTimeout(timer);
        if (watchId !== null) navigator.geolocation.clearWatch(watchId);
        const msgs = {
          1: 'Location permission denied. Please allow location access and try again.',
          2: 'Location is unavailable. Please check if location services are enabled on your device.',
          3: 'Location request timed out. Please try again.',
        };
        reject(new Error(msgs[err.code] || 'Location error: ' + err.message));
      },
      { timeout: SAMPLE_WINDOW_MS, enableHighAccuracy: true, maximumAge: 0 }
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
    if (statusEl) {
      statusEl.innerHTML = `<span style="color:var(--text-muted)">📍 Requesting location...</span>`;
    }

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
      coordEl.textContent = `${loc.lat.toFixed(6)}, ${loc.lng.toFixed(6)} (±${Math.round(loc.accuracy)} m)`;
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
