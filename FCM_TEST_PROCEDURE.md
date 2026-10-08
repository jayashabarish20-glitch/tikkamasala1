# Firebase Cloud Messaging (FCM) Test Procedure

## Overview
This document outlines both automated and manual testing procedures for the FCM admin phone notification implementation.

**Test Categories:**
- **A: Automated Backend Tests** — Can run without real Firebase
- **B: Manual Browser Tests** — Requires browser + notification permission
- **C: Manual Phone Tests** — Requires real Firebase project + admin phone

---

## PART A: AUTOMATED BACKEND TESTS

These tests verify the backend implementation without requiring Firebase credentials.

### Prerequisites
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Test A1: Firebase Admin SDK Package Check
**Verify:** firebase-admin is installed

```bash
python -c "import firebase_admin; print('✓ firebase-admin imported successfully')"
```

**Expected Output:**
```
✓ firebase-admin imported successfully
```

**Test Status:** 
- [ ] PASS
- [ ] FAIL

---

### Test A2: Model Creation Verification
**Verify:** AdminNotificationDevice model exists and imports correctly

```bash
python -c "from app.models.admin_notification_device import AdminNotificationDevice; print('✓ Model imported'); print(f'✓ Table name: {AdminNotificationDevice.__tablename__}')"
```

**Expected Output:**
```
✓ Model imported
✓ Table name: admin_notification_devices
```

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test A3: Service Layer Imports
**Verify:** Notification service imports without Firebase credentials

```bash
python -c "from app.services.notification_service import send_admin_new_order_notification; print('✓ Notification service imported')"
```

**Expected Output:**
```
✓ Notification service imported
```

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test A4: Admin Notifications Router Import
**Verify:** Notifications router imports correctly

```bash
python -c "from app.routes.admin.notifications import router; print('✓ Notifications router imported'); print(f'✓ Routes: {[str(r) for r in router.routes]}')"
```

**Expected Output:**
```
✓ Notifications router imported
✓ Routes: [...]
```

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test A5: Database Table Creation
**Verify:** AdminNotificationDevice table is created on startup

**Steps:**
1. Start the backend server:
```bash
cd backend
python -m uvicorn app.main:app --reload
```

2. In another terminal, verify table exists:
```bash
sqlite3 tikkamasala.db ".tables | grep admin_notification_devices"
```

**Expected Output:**
```
admin_notification_devices
```

3. Check schema:
```bash
sqlite3 tikkamasala.db ".schema admin_notification_devices"
```

**Expected Output:**
```sql
CREATE TABLE admin_notification_devices (
  id INTEGER NOT NULL, 
  admin_id INTEGER NOT NULL, 
  device_token VARCHAR(500) NOT NULL, 
  platform VARCHAR(20) NOT NULL, 
  is_active BOOLEAN NOT NULL, 
  created_at DATETIME, 
  updated_at DATETIME, 
  PRIMARY KEY (id), 
  FOREIGN KEY(admin_id) REFERENCES admins (id), 
  UNIQUE (device_token)
)
```

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test A6: Orders Route Integration
**Verify:** Orders.py imports notification service without errors

```bash
python -c "from app.routes.orders import router; print('✓ Orders router imported with notification service')"
```

**Expected Output:**
```
✓ Orders router imported with notification service
```

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test A7: Environment Variable Loading
**Verify:** Firebase setting loads from environment

**Step 1:** Verify .env has the setting
```bash
grep FIREBASE_SERVICE_ACCOUNT_JSON .env
```

**Expected Output:**
```
FIREBASE_SERVICE_ACCOUNT_JSON=
```

**Step 2:** Verify settings.py loads it
```bash
python -c "from app.config.settings import settings; print(f'FIREBASE_SERVICE_ACCOUNT_JSON: {settings.FIREBASE_SERVICE_ACCOUNT_JSON}')"
```

**Expected Output:**
```
FIREBASE_SERVICE_ACCOUNT_JSON: 
```

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test A8: Firebase Initialization Graceful Fallback
**Verify:** Notification service handles missing Firebase gracefully

**With server running, check logs:**
```bash
# In the terminal where server is running, you should see:
# [FCM] Firebase not initialized. Notification skipped.
# when no FIREBASE_SERVICE_ACCOUNT_JSON is set
```

**Test Status:**
- [ ] PASS (Check logs when running server)
- [ ] FAIL

---

## PART B: MANUAL BROWSER TESTS

These tests require a working browser and permission to show notifications.

### Test B1: Admin Authentication
**Verify:** Admin can login to admin panel

**Steps:**
1. Open http://localhost:8000/admin/orders.html
2. Enter admin credentials:
   - Username: `admin`
   - Password: `Admin@123`
3. Click Login

**Expected Result:**
- Admin dashboard loads
- See "Order Management" page
- Sidebar shows admin user

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test B2: Notification Permission Request
**Verify:** Browser asks for notification permission on admin page load

**Steps:**
1. After logging in to admin panel
2. Open browser console (F12 → Console)
3. Look for messages like:
   ```
   [FCM] Firebase initialized successfully
   ```

**Expected Result:**
- Browser shows notification permission prompt
- Console shows Firebase initialization messages
- Permission prompt appears (Allow/Block/Dismiss)

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test B3: Firebase Service Worker Registration
**Verify:** Service worker registers successfully

**Steps:**
1. Open DevTools → Application → Service Workers
2. Refresh admin page
3. Look for `/firebase-messaging-sw.js`

**Expected Result:**
- Service Worker listed as "ACTIVE AND RUNNING"
- Status shows green checkmark
- Service Worker URL: `http://localhost:8000/firebase-messaging-sw.js`

**Console Output:**
```
[FCM] Service Worker registered: ServiceWorkerRegistration {...}
```

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test B4: FCM Token Generation (Requires Real Firebase)
**Verify:** FCM token is obtained from Firebase

**Prerequisites:**
- Real Firebase project credentials configured in .env
- `FIREBASE_SERVICE_ACCOUNT_JSON` points to valid service account JSON
- Frontend Firebase config in frontend environment

**Steps:**
1. Admin logged in with notification permission granted
2. Open DevTools → Network tab
3. Look for requests to Firebase endpoints
4. Check Console for token messages:
   ```
   [FCM] Token obtained: eyJ...
   ```

**Expected Result:**
- Console shows token obtained
- POST request to `/api/admin/notifications/register-device` succeeds
- Response: `{"message": "Device token registered successfully.", "platform": "web"}`

**Test Status:**
- [ ] PASS (with Firebase credentials only)
- [ ] FAIL

---

### Test B5: Device Token Registration Endpoint
**Verify:** POST /api/admin/notifications/register-device works with admin auth

**Manual Test with curl:**
```bash
# First, login to get admin token
curl -X POST http://localhost:8000/api/auth/admin-login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@123"}'

# Copy the token from response
export ADMIN_TOKEN="<paste_token_here>"

# Register a test device
curl -X POST http://localhost:8000/api/admin/notifications/register-device \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token":"test_fcm_token_12345678901234567890","platform":"web"}'
```

**Expected Response (200):**
```json
{
  "message": "Device token registered successfully.",
  "platform": "web"
}
```

**Test Status:**
- [ ] PASS
- [ ] FAIL

**Error Cases to Test:**

**Test B5a: Missing Admin Auth**
```bash
curl -X POST http://localhost:8000/api/admin/notifications/register-device \
  -H "Content-Type: application/json" \
  -d '{"token":"test_token"}'
```

**Expected Response (401):**
```json
{"detail": "Not authenticated."}
```

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

**Test B5b: Invalid Token (too short)**
```bash
curl -X POST http://localhost:8000/api/admin/notifications/register-device \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token":"short"}'
```

**Expected Response (400):**
```json
{"detail": "Invalid device token."}
```

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test B6: List Registered Devices
**Verify:** GET /api/admin/notifications/devices returns registered devices

```bash
curl -X GET http://localhost:8000/api/admin/notifications/devices \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Expected Response (200):**
```json
[
  {
    "id": 1,
    "platform": "web",
    "is_active": true,
    "created_at": "2026-10-08T10:30:00"
  }
]
```

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test B7: Unregister Device
**Verify:** DELETE /api/admin/notifications/devices/{id} deactivates device

```bash
curl -X DELETE http://localhost:8000/api/admin/notifications/devices/1 \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Expected Response (200):**
```json
{"message": "Device token unregistered successfully."}
```

**Verify with GET:**
```bash
curl -X GET http://localhost:8000/api/admin/notifications/devices \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Device should have `"is_active": false`

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

## PART C: MANUAL PHONE TESTS

These tests require a real Firebase project, real admin phone, and actual push notifications.

### Prerequisites for Phone Tests
1. Firebase project created and configured
2. Firebase service account JSON downloaded and configured
3. Frontend Firebase Web config available
4. Admin phone with browser (Chrome, Firefox, etc.)
5. Admin phone on same network or accessible via domain

### Test C1: Register Phone Device
**Steps:**
1. On admin phone, navigate to admin panel
2. Login with admin credentials
3. Accept notification permission when prompted
4. Open DevTools (F12)
5. Check Console for message:
   ```
   [FCM] Device token registered successfully
   ```
6. Verify in backend:
   ```bash
   sqlite3 tikkamasala.db "SELECT COUNT(*) FROM admin_notification_devices WHERE is_active = 1;"
   ```

**Expected Result:**
- Count shows at least 1 active device
- Console shows successful registration

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test C2: Customer Places Order → Phone Notification
**Steps:**

**Step 1: Ensure Admin Device Registered**
- Admin phone browser: Check `/api/admin/notifications/devices`
- Should show at least 1 active device

**Step 2: Customer Places Order**
- Customer app: Place a COD order
- Note the order number (e.g., TM20261008001)

**Step 3: Check All Notification Channels**

**Admin Browser (if open):**
- WebSocket notification appears in orders panel
- Notification badge increments

**Admin Phone (any state):**
- OS notification appears (even if browser minimized/closed)
- Title: "🔔 New Order"
- Body: "Order TM20261008001 — ₹250"

**Backend Database:**
```bash
sqlite3 tikkamasala.db "SELECT * FROM orders ORDER BY id DESC LIMIT 1;"
```
- Order exists in database

**Backend Logs:**
```
[FCM] Notification sent to token (response: ...)
[FCM] New order notification sent to 1/1 devices
```

**Expected Result:**
- Order created successfully ✓
- WebSocket notification on admin browser ✓
- FCM notification on admin phone ✓
- Order visible in database ✓
- Logs show successful FCM send ✓

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test C3: Admin Browser Closed → Phone Still Gets Notification
**Steps:**

**Step 1: Close Admin Browser Completely**
- On admin phone, close the browser tab/app
- Verify service worker is still running (can check in browser app cache)

**Step 2: Customer Places Another Order**
- Different customer places COD order
- Note order number

**Step 3: Verify Phone Notification**
- Phone should show OS notification
- Even though browser was completely closed
- Service Worker in background handles the notification

**Expected Result:**
- Order created ✓
- No browser open, so no WebSocket ✓
- FCM notification still delivered to phone ✓
- OS notification appears ✓

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test C4: Notification Click Opens Admin Panel
**Steps:**

**Step 1: Ensure Notification Received**
- Customer places order
- Admin phone shows FCM notification

**Step 2: Click Notification**
- Tap the notification on admin phone

**Expected Result:**
- Browser opens (or tab opens in already-open browser)
- Navigates to `/admin/orders.html`
- New order is visible in orders list
- Notification closes

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test C5: Multiple Rapid Orders → Multiple Notifications
**Steps:**

**Step 1: Clear Previous Notifications**
- Clear all notifications from admin phone

**Step 2: Place 3 Orders Rapidly**
- Customer 1 places COD order
- Customer 2 places COD order (within 5 seconds)
- Customer 3 places COD order (within 5 seconds)

**Step 3: Check Notifications**
- Admin phone should receive 3 separate notifications
- Each with different order number
- Each with correct total

**Step 4: Verify Database**
```bash
sqlite3 tikkamasala.db "SELECT order_number, total FROM orders ORDER BY id DESC LIMIT 3;"
```

**Expected Result:**
- 3 notifications received on phone
- Each notification has correct order data
- All 3 orders exist in database
- Backend logs show 3 successful FCM sends

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test C6: Invalid/Expired FCM Token Handling
**Steps:**

**Step 1: Note Current Token**
- Get device ID from admin panel
- Check token in database

**Step 2: Invalidate Token (Simulate)**
- In Firebase Console, unsubscribe the device
- OR manually delete the device from FCM console
- (OR use Firebase Admin SDK to mark it invalid)

**Step 3: Place Order**
- Customer places COD order
- Backend tries to send FCM to invalid token

**Step 4: Verify Graceful Failure**

**Check Logs:**
```
[FCM] Failed to send to token
[FCM] Failed tokens for potential cleanup
```

**Expected Result:**
- Order created successfully ✓
- FCM send fails gracefully ✓
- Error logged but not exposed ✓
- Order NOT rolled back ✓
- API returns 200 to customer ✓

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test C7: Admin Deregisters Device
**Steps:**

**Step 1: List Devices**
```bash
curl -X GET http://localhost:8000/api/admin/notifications/devices \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Step 2: Deregister Device**
```bash
curl -X DELETE http://localhost:8000/api/admin/notifications/devices/1 \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Step 3: Place Order**
- Customer places new order

**Step 4: Verify**
- Order created ✓
- WebSocket notification still works (if browser open) ✓
- FCM notification NOT sent (device is_active = false) ✓
- Logs show no tokens to send to

**Expected Result:**
- Device deactivated in database
- Subsequent FCM attempts skip deactivated device
- Order creation not affected

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

## PART D: FCM FAILURE SCENARIO TESTS

### Test D1: Firebase Credentials Missing
**Verify:** FCM disabled gracefully when credentials absent

**Setup:**
1. Remove/clear `FIREBASE_SERVICE_ACCOUNT_JSON` in .env
2. Restart backend server
3. Customer places order

**Expected Result:**
- Order created successfully ✓
- Log message: `[FCM] Firebase not initialized. Notification skipped.` ✓
- API returns success to customer ✓

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test D2: Firebase Service Unavailable
**Verify:** Transient Firebase failures don't break orders

**Setup:**
1. Configure valid Firebase credentials
2. Temporarily block Firebase API (unplug network OR use firewall rule)
3. Customer places order

**Expected Result:**
- Order created ✓
- FCM call times out ✓
- Timeout handled in try-except ✓
- Log shows exception caught ✓
- Order still succeeds ✓

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

### Test D3: Malformed Firebase Config
**Verify:** Invalid JSON path handled gracefully

**Setup:**
1. Set `FIREBASE_SERVICE_ACCOUNT_JSON` to invalid path:
   ```
   FIREBASE_SERVICE_ACCOUNT_JSON=/nonexistent/path.json
   ```
2. Restart server
3. Customer places order

**Expected Result:**
- Server logs error on initialization attempt
- FCM disabled (graceful fallback)
- Order creation still works
- No crash

**Test Status:**
- [ ] PASS
- [ ] FAIL

---

## SUMMARY CHECKLIST

### Automated Tests (No Firebase Needed)
- [ ] A1: Package check
- [ ] A2: Model import
- [ ] A3: Service import
- [ ] A4: Router import
- [ ] A5: Database table creation
- [ ] A6: Orders integration
- [ ] A7: Environment loading
- [ ] A8: Graceful fallback

### Browser Tests (Browser Required)
- [ ] B1: Admin login
- [ ] B2: Notification permission
- [ ] B3: Service worker registration
- [ ] B4: FCM token generation (with Firebase)
- [ ] B5: Device registration endpoint
- [ ] B5a: Auth required validation
- [ ] B5b: Token validation
- [ ] B6: List devices endpoint
- [ ] B7: Unregister device endpoint

### Phone Tests (Real Firebase + Phone Required)
- [ ] C1: Register phone device
- [ ] C2: Order → Phone notification
- [ ] C3: Browser closed → Still works
- [ ] C4: Notification click navigation
- [ ] C5: Multiple rapid orders
- [ ] C6: Invalid token handling
- [ ] C7: Device deregistration

### Failure Scenario Tests
- [ ] D1: Missing credentials
- [ ] D2: Service unavailable
- [ ] D3: Malformed config

---

## Notes for Testers

### Important
- **DO NOT modify application code** during testing
- **DO NOT commit test changes** to git
- **DO NOT push** to remote
- Only test the implementation as-is

### Test Environment
- Backend: `http://localhost:8000`
- Frontend: Browser at `http://localhost:8000/admin/orders.html`
- Database: `tikkamasala.db` (SQLite)

### Debugging
- Backend logs: Check server console output
- Frontend logs: Browser DevTools → Console
- Database queries: `sqlite3 tikkamasala.db ".schema"` or `.tables`
- Network requests: Browser DevTools → Network tab

### Firebase Debugging
- Firebase Console: https://console.firebase.google.com
- Cloud Messaging tab: Check device subscriptions
- Service Worker: DevTools → Application → Service Workers

---

## Test Report Template

After completing testing, report:

```
═══════════════════════════════════════════════════════════
FIREBASE FCM IMPLEMENTATION TEST REPORT
═══════════════════════════════════════════════════════════

Test Date: YYYY-MM-DD
Tester: [Name]
Environment: [Local/Staging/Production]

PART A: AUTOMATED BACKEND TESTS
─────────────────────────────────
A1 Package Check:              [ ] PASS [ ] FAIL
A2 Model Import:               [ ] PASS [ ] FAIL
A3 Service Import:             [ ] PASS [ ] FAIL
A4 Router Import:              [ ] PASS [ ] FAIL
A5 Database Table:             [ ] PASS [ ] FAIL
A6 Orders Integration:         [ ] PASS [ ] FAIL
A7 Environment Loading:        [ ] PASS [ ] FAIL
A8 Graceful Fallback:          [ ] PASS [ ] FAIL

PART B: MANUAL BROWSER TESTS
─────────────────────────────
B1 Admin Authentication:       [ ] PASS [ ] FAIL
B2 Notification Permission:    [ ] PASS [ ] FAIL
B3 Service Worker:             [ ] PASS [ ] FAIL
B4 FCM Token Generation:       [ ] PASS [ ] FAIL (Firebase req)
B5 Device Registration:        [ ] PASS [ ] FAIL
B5a Auth Required:             [ ] PASS [ ] FAIL
B5b Token Validation:          [ ] PASS [ ] FAIL
B6 List Devices:               [ ] PASS [ ] FAIL
B7 Unregister Device:          [ ] PASS [ ] FAIL

PART C: MANUAL PHONE TESTS
──────────────────────────
C1 Register Phone Device:      [ ] PASS [ ] FAIL
C2 Order → Notification:       [ ] PASS [ ] FAIL
C3 Browser Closed Works:       [ ] PASS [ ] FAIL
C4 Notification Click:         [ ] PASS [ ] FAIL
C5 Multiple Orders:            [ ] PASS [ ] FAIL
C6 Invalid Token Handling:     [ ] PASS [ ] FAIL
C7 Device Deregistration:      [ ] PASS [ ] FAIL

PART D: FAILURE SCENARIOS
─────────────────────────
D1 Missing Credentials:        [ ] PASS [ ] FAIL
D2 Service Unavailable:        [ ] PASS [ ] FAIL
D3 Malformed Config:           [ ] PASS [ ] FAIL

═══════════════════════════════════════════════════════════

ISSUES FOUND:
─────────────
[List any failures with exact error messages and logs]

NOTES:
──────
[Any observations about the implementation]

CONCLUSION:
───────────
[ ] READY FOR PRODUCTION
[ ] NEEDS FIXES
[ ] REQUIRES MANUAL INTERVENTION
```

