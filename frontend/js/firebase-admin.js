/**
 * Firebase Cloud Messaging integration for admin panel.
 * Handles FCM token registration and foreground message handling.
 */

let firebaseApp = null;
let messaging = null;

/**
 * Initialize Firebase for the admin panel.
 * Call this after the page loads and admin is authenticated.
 */
async function initializeFirebaseMessaging() {
  try {
    // Import Firebase SDK
    if (typeof firebase === 'undefined') {
      console.log('[FCM] Firebase SDK not loaded. Skipping FCM initialization.');
      return;
    }

    // Firebase config from environment or window
    const firebaseConfig = window.FIREBASE_CONFIG || {
      apiKey: window.__FIREBASE_API_KEY || "",
      authDomain: window.__FIREBASE_AUTH_DOMAIN || "",
      projectId: window.__FIREBASE_PROJECT_ID || "",
      storageBucket: window.__FIREBASE_STORAGE_BUCKET || "",
      messagingSenderId: window.__FIREBASE_MESSAGING_SENDER_ID || "",
      appId: window.__FIREBASE_APP_ID || "",
    };

    // Check if config is complete
    if (!firebaseConfig.projectId) {
      console.log('[FCM] Firebase config incomplete. Notifications disabled.');
      return;
    }

    // Initialize Firebase
    firebaseApp = firebase.initializeApp(firebaseConfig);
    messaging = firebase.messaging();

    console.log('[FCM] Firebase initialized successfully');

    // Register service worker first so the FCM token is bound to it
    if ('serviceWorker' in navigator) {
      try {
        const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
        console.log('[FCM] Service Worker registered:', registration);
        messaging.useServiceWorker(registration);
      } catch (err) {
        console.warn('[FCM] Service Worker registration failed:', err);
      }
    }

    // Browsers only show the permission prompt after a user click, so the admin
    // enables alerts with a button (enableFirebaseNotifications). Granted permission
    // is registered automatically on page load.
    if (Notification.permission === 'granted') {
      await registerFCMToken();
    } else {
      console.log('[FCM] Notification permission not granted yet');
    }

    // Handle foreground messages
    messaging.onMessage((payload) => {
      console.log('[FCM] Foreground message received:', payload);

      // Show in-browser notification
      if (Notification.permission === 'granted') {
        const title = payload.data?.title || 'New Order Received';
        const options = {
          body: payload.data?.body || 'A new order has been placed.',
          icon: '/assets/tmcc-logo.jpg',
          badge: '/assets/tmcc-logo.jpg',
          tag: 'order-notification',
          data: payload.data || {},
        };
        new Notification(title, options);
      }

      // Also dispatch custom event for page to handle
      const event = new CustomEvent('fcm:message', { detail: payload });
      document.dispatchEvent(event);
    });

  } catch (err) {
    console.error('[FCM] Firebase initialization error:', err);
  }
}

/**
 * Enable phone alerts for this device. Call from a button click so the
 * browser shows the permission prompt. Returns a message for the admin.
 */
async function enableFirebaseNotifications() {
  if (!messaging) {
    return 'Phone alerts are not configured on the server yet.';
  }
  if (!('Notification' in window)) {
    return 'This browser does not support notifications.';
  }
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') {
    return 'Notifications are blocked. Allow them in the browser site settings and try again.';
  }
  await registerFCMToken();
  return 'Phone alerts are on for this device.';
}

/**
 * Register FCM token with the backend.
 */
async function registerFCMToken() {
  try {
    if (!messaging) {
      console.log('[FCM] Messaging not initialized');
      return;
    }

    // Get the token
    const token = await messaging.getToken({
      vapidKey: window.__FIREBASE_VAPID_KEY || "",
    });

    if (!token) {
      console.warn('[FCM] Failed to get FCM token');
      return;
    }

    console.log('[FCM] Token obtained:', token.substring(0, 20) + '...');

    // Send token to backend
    const response = await fetch('/api/admin/notifications/register-device', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${api.getToken()}`,
      },
      body: JSON.stringify({
        token: token,
        platform: 'web',
      }),
    });

    if (response.ok) {
      console.log('[FCM] Device token registered successfully');
    } else {
      const error = await response.json();
      console.warn('[FCM] Failed to register device token:', error.detail);
    }
  } catch (err) {
    console.error('[FCM] Error registering FCM token:', err);
  }
}

/**
 * Unregister FCM token (optional - for logout or removing device).
 */
async function unregisterFCMToken(deviceId) {
  try {
    const response = await fetch(`/api/admin/notifications/devices/${deviceId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${api.getToken()}`,
      },
    });

    if (response.ok) {
      console.log('[FCM] Device token unregistered');
    } else {
      console.warn('[FCM] Failed to unregister device token');
    }
  } catch (err) {
    console.error('[FCM] Error unregistering FCM token:', err);
  }
}

/**
 * List all registered devices for current admin.
 */
async function listFCMDevices() {
  try {
    const response = await fetch('/api/admin/notifications/devices', {
      headers: {
        'Authorization': `Bearer ${api.getToken()}`,
      },
    });

    if (response.ok) {
      const devices = await response.json();
      console.log('[FCM] Registered devices:', devices);
      return devices;
    } else {
      console.warn('[FCM] Failed to list devices');
      return [];
    }
  } catch (err) {
    console.error('[FCM] Error listing devices:', err);
    return [];
  }
}
