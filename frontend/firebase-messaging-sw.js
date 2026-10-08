/**
 * Firebase Cloud Messaging Service Worker
 * Handles push notifications when the browser/page is closed.
 * Located at root (frontend/) so it can be served at /firebase-messaging-sw.js
 */

importScripts('https://www.gstatic.com/firebasejs/10.8.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.8.0/firebase-messaging-compat.js');

// Firebase config - loaded from frontend environment
const firebaseConfig = {
  apiKey: self.importScripts ? "FIREBASE_API_KEY_PLACEHOLDER" : "",
  authDomain: "FIREBASE_AUTH_DOMAIN_PLACEHOLDER",
  projectId: "FIREBASE_PROJECT_ID_PLACEHOLDER",
  storageBucket: "FIREBASE_STORAGE_BUCKET_PLACEHOLDER",
  messagingSenderId: "FIREBASE_MESSAGING_SENDER_ID_PLACEHOLDER",
  appId: "FIREBASE_APP_ID_PLACEHOLDER",
};

// Initialize Firebase in service worker
firebase.initializeApp(firebaseConfig);

// Get messaging instance
const messaging = firebase.messaging();

// Handle background messages (when page/browser is closed)
messaging.onBackgroundMessage((payload) => {
  console.log('[firebase-messaging-sw] Received background message:', payload);

  const notificationTitle = payload.notification?.title || "New Order";
  const notificationOptions = {
    body: payload.notification?.body || "A new order has been placed.",
    icon: '/assets/tmcc-logo.jpg',
    badge: '/assets/tmcc-logo.jpg',
    tag: 'order-notification',
    requireInteraction: true,
    data: payload.data || {},
  };

  // Show notification
  self.registration.showNotification(notificationTitle, notificationOptions);
});

// Handle notification click
self.addEventListener('notificationclick', (event) => {
  console.log('[firebase-messaging-sw] Notification clicked:', event.notification);
  event.notification.close();

  // Open the admin orders page
  const urlToOpen = '/admin/orders.html';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // Check if there's already a window/tab with the target URL open
        for (let i = 0; i < clientList.length; i++) {
          const client = clientList[i];
          if (client.url === urlToOpen && 'focus' in client) {
            return client.focus();
          }
        }
        // If not, open a new window
        if (clients.openWindow) {
          return clients.openWindow(urlToOpen);
        }
      })
  );
});
