# FCM Testing — Quick Start Guide

## Overview
Three types of tests available:
- **Automated Tests** — No Firebase needed, no phone needed
- **Browser Tests** — Requires browser + notification permission
- **Phone Tests** — Requires real Firebase project + admin phone

---

## QUICK START: Automated Tests

### 1. Install dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Run automated test script
```bash
python test_fcm_implementation.py
```

### Expected Output
```
═══════════════════════════════════════════════════════════
      FIREBASE FCM IMPLEMENTATION - AUTOMATED TEST SUITE
═══════════════════════════════════════════════════════════

✓ PASS A1: Package Check
✓ PASS A2: Model Import
✓ PASS A3: Service Import
✓ PASS A4: Router Import
✓ PASS A5: Model Initialization
✓ PASS A6: Settings Configuration
✓ PASS A7: Orders Integration
✓ PASS A8: FastAPI App Router
✓ PASS A9: Firebase Fallback
✓ PASS A10: .env File
✓ PASS A11: .env.example File

═══════════════════════════════════════════════════════════
TEST SUMMARY
═══════════════════════════════════════════════════════════

✓ PASS Results: 11/11 passed (100%)

═══════════════════════════════════════════════════════════
✓ ALL TESTS PASSED - IMPLEMENTATION VERIFIED
═══════════════════════════════════════════════════════════
```

### 3. Check Database Table Creation
```bash
# Start the server
python -m uvicorn app.main:app --reload

# In another terminal, verify table exists
sqlite3 tikkamasala.db ".tables"
# Should show: admin_notification_devices
```

---

## QUICK START: Endpoint Tests (via curl)

### 1. Get Admin Token
```bash
curl -X POST http://localhost:8000/api/auth/admin-login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@123"}'
```

**Response:**
```json
{"access_token": "eyJ...", "token_type": "Bearer"}
```

Copy the token:
```bash
export ADMIN_TOKEN="<paste_token_here>"
```

### 2. Register a Test Device
```bash
curl -X POST http://localhost:8000/api/admin/notifications/register-device \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token":"test_fcm_token_1234567890","platform":"web"}'
```

**Expected Response (200):**
```json
{
  "message": "Device token registered successfully.",
  "platform": "web"
}
```

### 3. List Registered Devices
```bash
curl -X GET http://localhost:8000/api/admin/notifications/devices \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Expected Response:**
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

### 4. Test Order Creation with FCM
```bash
# Customer login
curl -X POST http://localhost:8000/api/auth/send-otp \
  -H "Content-Type: application/json" \
  -d '{"mobile":"9876543210","purpose":"REGISTRATION"}'

# Follow auth flow to create customer and place order
# Order creation should trigger FCM notification attempt
```

**Check logs for:**
```
[FCM] Notification sent to token
[FCM] New order notification sent to 1/1 devices
```

### 5. Test Error Cases

**Missing auth:**
```bash
curl -X POST http://localhost:8000/api/admin/notifications/register-device \
  -H "Content-Type: application/json" \
  -d '{"token":"test"}'
# Expected: 401 Not authenticated
```

**Invalid token (too short):**
```bash
curl -X POST http://localhost:8000/api/admin/notifications/register-device \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token":"short"}'
# Expected: 400 Invalid device token
```

---

## QUICK START: Browser Tests

### 1. Start Backend
```bash
cd backend
python -m uvicorn app.main:app --reload
```

### 2. Open Admin Panel
Navigate to: `http://localhost:8000/admin/orders.html`

### 3. Login
- Username: `admin`
- Password: `Admin@123`

### 4. Check Browser Console
Open DevTools → Console (F12)

**Look for:**
```
[FCM] Firebase initialized successfully
[FCM] Service Worker registered
```

### 5. Check Service Worker
DevTools → Application → Service Workers

**Look for:**
- `/firebase-messaging-sw.js` listed
- Status: `ACTIVE AND RUNNING`

### 6. Allow Notifications
When browser asks for notification permission, click **Allow**

---

## QUICK START: Phone Tests (With Real Firebase)

### Prerequisites
1. Real Firebase project configured
2. Firebase service account JSON downloaded
3. Frontend Firebase Web config available
4. Set in `.env`:
   ```
   FIREBASE_SERVICE_ACCOUNT_JSON=/path/to/firebase-service-account.json
   ```

### 1. Register Admin Phone
1. Open admin panel on phone browser
2. Login with admin credentials
3. Accept notification permission
4. Check DevTools Console for:
   ```
   [FCM] Device token registered successfully
   ```

### 2. Place Test Order
1. On customer device: Place a COD order
2. On admin phone: Check for OS notification
3. Notification should show:
   ```
   🔔 New Order
   Order TM20261008XXX — ₹250
   ```

### 3. Click Notification
- Notification should open `/admin/orders.html`
- New order visible in admin panel

### 4. Test Browser Closed
1. Close admin browser on phone completely
2. Place another customer order
3. Notification should still arrive (Service Worker handles it)

---

## Debugging

### Server Logs
The backend logs show FCM activity:

```
# Successful notification
[FCM] Notification sent to token (response: ...)
[FCM] New order notification sent to 1/1 devices

# Missing Firebase
[FCM] Firebase not initialized. Notification skipped.

# Invalid token
[FCM] Failed to send to token
[FCM] Failed tokens for potential cleanup: 1
```

### Database Queries
```bash
# Check registered devices
sqlite3 tikkamasala.db "SELECT * FROM admin_notification_devices;"

# Check orders created
sqlite3 tikkamasala.db "SELECT order_number, total FROM orders ORDER BY id DESC LIMIT 5;"
```

### Browser Console Messages
```javascript
[FCM] Firebase initialized successfully
[FCM] Service Worker registered
[FCM] Token obtained: eyJ...
[FCM] Device token registered successfully
[FCM] Foreground message received
```

---

## Troubleshooting

### "firebase-admin not installed"
```bash
pip install firebase-admin
```

### Service Worker not registering
- Check that `/firebase-messaging-sw.js` exists in frontend/
- Check browser DevTools for errors
- May need to restart browser

### Notifications not appearing
- Check notification permission in browser settings
- Check Firebase credentials configured correctly
- Check FCM token is valid and registered

### Order creation fails
**This should NEVER happen.** If it does:
- FCM failures are caught and logged
- Orders are created regardless
- Check backend logs for the actual error

---

## Test Report

After testing, copy this template and fill in results:

```
TEST DATE: YYYY-MM-DD
TESTER: [Your Name]

AUTOMATED TESTS (Part A):
  A1 Package Check:           [✓ PASS / ✗ FAIL]
  A2 Model Import:            [✓ PASS / ✗ FAIL]
  A3 Service Import:          [✓ PASS / ✗ FAIL]
  A4 Router Import:           [✓ PASS / ✗ FAIL]
  A5 Model Init:              [✓ PASS / ✗ FAIL]
  A6 Settings:                [✓ PASS / ✗ FAIL]
  A7 Orders Integration:      [✓ PASS / ✗ FAIL]
  A8 FastAPI App:             [✓ PASS / ✗ FAIL]
  A9 Firebase Fallback:       [✓ PASS / ✗ FAIL]
  A10 .env File:              [✓ PASS / ✗ FAIL]
  A11 .env.example:           [✓ PASS / ✗ FAIL]

BROWSER TESTS (Part B):
  B1 Admin Login:             [✓ PASS / ✗ FAIL]
  B2 Notification Permission: [✓ PASS / ✗ FAIL]
  B3 Service Worker:          [✓ PASS / ✗ FAIL]
  B5 Device Registration:     [✓ PASS / ✗ FAIL]
  B6 List Devices:            [✓ PASS / ✗ FAIL]
  B7 Unregister Device:       [✓ PASS / ✗ FAIL]

PHONE TESTS (Part C):
  C1 Register Phone:          [✓ PASS / ✗ FAIL / ⊘ SKIPPED]
  C2 Order → Notification:    [✓ PASS / ✗ FAIL / ⊘ SKIPPED]
  C3 Browser Closed:          [✓ PASS / ✗ FAIL / ⊘ SKIPPED]
  C4 Click Notification:      [✓ PASS / ✗ FAIL / ⊘ SKIPPED]
  C5 Multiple Orders:         [✓ PASS / ✗ FAIL / ⊘ SKIPPED]

SUMMARY: X/11 automated tests passed

ISSUES FOUND:
[List any failures]

NOTES:
[Any observations]

STATUS: [ ] Ready for production [ ] Needs fixes
```

---

## Important Notes

⚠️ **DO NOT:**
- Modify application code during testing
- Commit test changes to git
- Push to remote
- Use production Firebase credentials for testing

✅ **DO:**
- Test locally first
- Use demo/test Firebase project
- Check logs for errors
- Verify order creation always succeeds

---

## Next Steps

1. Run automated tests → `python test_fcm_implementation.py`
2. If all pass, proceed to browser tests
3. If Firebase available, run phone tests
4. Report results in test report template
5. Ready to commit implementation

