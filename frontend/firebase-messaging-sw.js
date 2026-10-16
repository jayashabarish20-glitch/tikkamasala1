/**
 * Firebase Cloud Messaging Service Worker
 * Handles push notifications when the browser/page is closed.
 * Located at root (frontend/) so it can be served at /firebase-messaging-sw.js
 */

importScripts('https://www.gstatic.com/firebasejs/10.8.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.8.0/firebase-messaging-compat.js');

// Public Firebase web config served by the backend (sets self.FIREBASE_CONFIG)
importScripts('/api/admin/notifications/web-config.js');

// Initialize Firebase in service worker
firebase.initializeApp(self.FIREBASE_CONFIG);

// Get messaging instance
const messaging = firebase.messaging();

// Handle background messages (when page/browser is closed)
messaging.onBackgroundMessage((payload) => {
  console.log('[firebase-messaging-sw] Received background message:', payload);

  // Backend sends data-only messages, so this is the only notification shown
  const notificationTitle = payload.data?.title || "New Order Received";
  const notificationOptions = {
    body: payload.data?.body || "A new order has been placed.",
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
          if (client.url.endsWith(urlToOpen) && 'focus' in client) {
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
