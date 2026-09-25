# 🧪 Testing Guide - Enhanced Delivery Feature

## Quick Start Testing

### Prerequisites
- Backend running on `http://localhost:8000`
- Frontend accessible on `http://localhost:5500` (or similar)
- Database migration will run automatically on startup

---

## 🧑‍💻 CUSTOMER TESTING

### Test Case 1: Manual Address Entry
1. **Login as Customer**
   - Navigate to `/customer/login.html`
   - Mobile: `9876543210` (or any registered customer)
   - Password: (customer password)

2. **Add Items to Cart**
   - Go to `/customer/menu.html`
   - Add some items to cart

3. **Proceed to Checkout**
   - Click "Checkout" or go to `/customer/checkout.html`
   - You should see:
     - ✅ Customer name & mobile pre-filled (from login)
     - ✅ "Type Address" button selected (default)
     - ✅ Address form fields visible

4. **Enter Address**
   ```
   House/Flat: 12/3
   Street/Area: Purasawalkam Street
   City: Chennai
   State: Tamil Nadu
   Pincode: 600012
   Landmark: Near XYZ Hospital (optional)
   ```

5. **Place Order**
   - Click "Place Order & Pay"
   - Should see: ✅ "Delivery available at your location"
   - Should redirect to payment page

### Test Case 2: GPS-Based Address Entry
1. **Login and Go to Checkout** (same as above)

2. **Switch to GPS Mode**
   - Click "📍 Use My Location" button
   - Accept browser location permission popup
   - Should see:
     - ✅ "Location detected successfully"
     - ✅ Coordinates displayed (e.g., 13.123456, 80.234567)
     - ✅ "View on Google Maps" link
     - ✅ Delivery eligibility message

3. **Test 5 km Radius**
   - If location is **inside 5 km**: ✅ "Delivery available"
   - If location is **outside 5 km**: ❌ "Outside delivery radius" (can't checkout)

4. **Place Order (if eligible)**
   - Click "Place Order & Pay"
   - Should redirect to payment page

### Test Case 3: Validation Testing
1. **Try missing fields**
   - Leave some required fields empty
   - Click "Place Order & Pay"
   - Should see: ⚠️ "Please fill all required address fields"

2. **Try without coordinates**
   - Fill address but don't click GPS button
   - Click "Place Order & Pay"
   - Should see: ⚠️ "Please select your delivery location"

---

## 👨‍💼 ADMIN TESTING

### Test Case 1: View Order Details
1. **Login as Admin**
   - Navigate to `/admin/login.html`
   - Username: `admin`
   - Password: `Admin@123`

2. **Go to Orders**
   - Click "Orders" in sidebar
   - You should see all orders in a table

3. **Open an Order**
   - Click the 🔍 (eye) icon on any delivery order
   - Should see order detail modal with:
     - ✅ Customer name & mobile
     - ✅ Order type (DELIVERY)
     - ✅ Full delivery address
     - ✅ Pincode
     - ✅ Landmark (if provided)
     - ✅ Coordinates (if available)
     - ✅ "🗺️ Open Location in Google Maps" button
     - ✅ Order items list
     - ✅ Order total
     - ✅ "📲 Share on WhatsApp" button

### Test Case 2: Google Maps Link
1. **Open Order Details** (from Test Case 1)
2. **Click Map Button**
   - Click "🗺️ Open Location in Google Maps"
   - Should open Google Maps in new tab showing the delivery location

### Test Case 3: WhatsApp Sharing
1. **Open Order Details** (from Test Case 1)
2. **Click WhatsApp Button**
   - Click "📲 Share on WhatsApp"
   - Should open WhatsApp Web (or app) with pre-filled message
   - Message should contain:
     - ✅ Order ID (#ABC123)
     - ✅ Customer name
     - ✅ Customer mobile
     - ✅ Full delivery address
     - ✅ Pincode
     - ✅ Landmark
     - ✅ Google Maps link
     - ✅ Order total
     - ✅ Order status
   - Message should **NOT** be auto-sent
   - Admin can review and send manually

### Test Case 4: Pickup Orders (No Delivery Info)
1. **Create a Pickup Order** (if possible)
   - Or filter for pickup orders in admin panel
2. **Open Order Details**
   - Should **NOT** show delivery section
   - Should show order items and total only

---

## 🔌 API TESTING (Using Postman/cURL)

### Test Order Creation with New Fields
```bash
curl -X POST http://localhost:8000/api/orders \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "order_type": "DELIVERY",
    "delivery_address": "12/3 Purasawalkam, Chennai",
    "delivery_house_flat_door": "12/3",
    "delivery_street_area": "Purasawalkam Street",
    "delivery_city": "Chennai",
    "delivery_state": "Tamil Nadu",
    "delivery_pincode": "600012",
    "delivery_landmark": "Near Hospital",
    "delivery_lat": 13.096627,
    "delivery_lng": 80.259209,
    "notes": "Extra spicy"
  }'
```

### Test Admin Orders Endpoint
```bash
curl -X GET http://localhost:8000/api/admin/orders \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

**Expected Response includes:**
```json
{
  "delivery_house_flat_door": "12/3",
  "delivery_street_area": "Purasawalkam Street",
  "delivery_city": "Chennai",
  "delivery_state": "Tamil Nadu",
  "delivery_pincode": "600012",
  "delivery_landmark": "Near Hospital",
  "delivery_lat": 13.096627,
  "delivery_lng": 80.259209,
  "google_maps_link": "https://www.google.com/maps?q=13.096627,80.259209"
}
```

---

## 🐛 DEBUGGING TIPS

### Customer Side
- **Check browser console** (F12 → Console) for any errors
- **Location permission denied?** Check browser location settings
- **Coordinates not appearing?** Ensure geolocation is enabled in browser
- **Form not submitting?** Check all required fields are filled

### Admin Side
- **WhatsApp not opening?** Check customer mobile is stored correctly (no special chars)
- **Map link not working?** Check coordinates are not NULL in database
- **Modal not closing?** Press Escape or click the × button

### Backend
- **Check server logs** for any validation errors
- **Database migration issues?** Restart backend (migration runs on startup)
- **API errors?** Check response in browser Network tab (F12 → Network)

---

## ✅ Regression Testing

Ensure these **still work** after the new features:

- [ ] Customer login/register
- [ ] OTP verification
- [ ] Product browsing
- [ ] Add/remove items from cart
- [ ] Pickup orders (without address)
- [ ] Payment processing
- [ ] Admin dashboard
- [ ] Inventory management
- [ ] Order status updates
- [ ] Delivery OTP verification
- [ ] All existing admin features

---

## 📊 Data Validation

### Valid Address Example
```
House/Flat: 12/3
Street/Area: Purasawalkam Street
City: Chennai
State: Tamil Nadu
Pincode: 600012
Landmark: Near XYZ Hospital
```

### Valid Coordinates
- **Inside 5 km** (from 13.096627, 80.259209): 13.0966, 80.2592
- **Outside 5 km** (test rejection): 13.1, 80.1 (roughly 5+ km away)

---

## 🔒 Security Checklist

- [ ] No sensitive data exposed to customers
- [ ] Customer mobile only visible to admins
- [ ] 5 km radius enforced server-side (can't bypass)
- [ ] Address data validated before storage
- [ ] WhatsApp messages not auto-sent
- [ ] All API endpoints require authentication

---

## 📱 Mobile Testing

Test on actual mobile device:
1. Open `/customer/checkout.html` on phone
2. Test manual address entry (should be touch-friendly)
3. Test GPS location:
   - Allow permission
   - Should work without HTTPS (localhost is safe)
   - Google Maps link should open Maps app (if installed)
4. Test WhatsApp sharing (should open WhatsApp app)

---

## 🎯 Expected Outcomes

### Customer Flow ✅
1. Cart → Checkout
2. See pre-filled name/mobile ✅
3. Enter address manually OR use GPS ✅
4. See delivery eligibility ✅
5. Place order with all details ✅
6. Order confirmation with address ✅

### Admin Flow ✅
1. See complete delivery details ✅
2. Click map to view location ✅
3. Click WhatsApp to message customer ✅
4. Update order status ✅

### Data Flow ✅
1. Address stored in database ✅
2. Google Maps link generated ✅
3. 5 km radius validated ✅
4. No data loss in existing orders ✅

---

## 📞 Issues?

If something doesn't work:
1. **Check the backend logs** for error messages
2. **Check browser console** (F12) for JavaScript errors
3. **Verify database migration** ran (check `tikkamasala.db`)
4. **Check localStorage** (F12 → Application → Local Storage) for user data
5. **Try hard refresh** (Ctrl+Shift+R on Windows, Cmd+Shift+R on Mac)

---

**Happy Testing! 🚀**
