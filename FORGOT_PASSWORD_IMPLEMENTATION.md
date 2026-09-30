# Forgot Password Feature Implementation

## Overview
Complete implementation of a customer forgot password flow with demo OTP. Designed for easy migration to real SMS provider.

**Commit:** 3ed52c8  
**Status:** ✓ Complete and tested

---

## Architecture

### Design Principles
- **OTP Generation & Verification:** Server-side only (secure)
- **Reset Tokens:** Short-lived (15 minutes), single-use
- **Password Hashing:** Reuses existing bcrypt implementation
- **Provider Abstraction:** SMS provider interface allows easy real SMS integration
- **Demo Mode:** Returns demo OTP in response for testing without SMS

---

## Backend Implementation

### New Models

#### `PasswordResetToken` (`backend/app/models/password_reset_token.py`)
Stores short-lived password reset tokens after OTP verification.

```python
- id: Integer (primary key)
- mobile: String(15) - registered phone number
- token: String(255) - unique reset token
- expires_at: DateTime - token expiration time
- is_used: Boolean - single-use flag
- created_at: DateTime - creation timestamp
```

**Expiration:** 15 minutes  
**Properties:** Indexed on mobile and token for fast lookup

### New Services

#### Password Reset Service (`backend/app/services/password_reset_service.py`)

Three main functions:

1. **`request_password_reset(db, mobile)`**
   - Validates phone is registered and account is active
   - Generates 6-digit OTP using existing OTP service
   - Sends demo OTP via SMS service
   - Returns OTP code for demo mode display
   - Throws HTTPException if phone not found or account inactive

2. **`verify_reset_otp_and_create_token(db, mobile, otp_code)`**
   - Verifies OTP using existing OTP service
   - Creates unique reset token (32-char URL-safe)
   - Stores in database with 15-minute expiration
   - Returns reset token for password form
   - Throws HTTPException if OTP invalid/expired/attempts exceeded

3. **`reset_password(db, reset_token, new_password)`**
   - Validates reset token exists and hasn't expired
   - Checks token hasn't already been used
   - Updates user password using existing hash_password()
   - Marks token as used (prevents reuse)
   - Throws HTTPException if token invalid/expired/already used

**Key Design:** OTP verification is handled by existing OTP service, which already supports:
- Multiple purposes (REGISTRATION, LOGIN, DELIVERY, PASSWORD_RESET)
- 10-minute expiration
- 3 failed attempt limit
- Single-use enforcement

### Updated Services

#### SMS Service (`backend/app/services/sms_service.py`)

Added function:
```python
async def send_password_reset_otp_sms(mobile: str, otp: str) -> bool
```
- Reuses existing SMS provider abstraction (Mock or MSG91)
- Returns OTP for demo mode, SMS for production
- Message clearly indicates password reset context

### Updated Routes

#### Auth Routes (`backend/app/routes/auth.py`)

Three new endpoints added to `/api/auth`:

1. **`POST /api/auth/forgot-password`**
   - Request: `{ "mobile": "9876543210" }`
   - Response (demo mode):
     ```json
     {
       "message": "OTP sent for password reset.",
       "demo_otp": "123456"
     }
     ```
   - Response (production):
     ```json
     {
       "message": "OTP sent for password reset."
     }
     ```
   - Status Codes:
     - 200: OTP generated
     - 400: Phone not registered / account inactive
     - 429: Too many requests (cooldown 60s)

2. **`POST /api/auth/verify-reset-otp`**
   - Request: `{ "mobile": "9876543210", "code": "123456" }`
   - Response:
     ```json
     {
       "message": "OTP verified.",
       "reset_token": "..." 
     }
     ```
   - Status Codes:
     - 200: OTP verified, token created
     - 400: Invalid/expired OTP, too many attempts
     - 429: Rate limited

3. **`POST /api/auth/reset-password`**
   - Request: `{ "reset_token": "...", "new_password": "NewPass123" }`
   - Response:
     ```json
     {
       "message": "Password reset successful."
     }
     ```
   - Status Codes:
     - 200: Password updated successfully
     - 400: Invalid/expired token, already used, or account not found

### Updated Schemas

#### Auth Schemas (`backend/app/schemas/auth.py`)

Three new request schemas:

1. **`ForgotPasswordRequest`**
   - mobile: validated 10-digit Indian phone number

2. **`VerifyResetOTPRequest`**
   - mobile: phone number
   - code: 6-digit OTP

3. **`ResetPasswordRequest`**
   - reset_token: returned from verify OTP step
   - new_password: minimum 6 characters (reuses existing validator)

---

## Frontend Implementation

### Login Page Updates (`frontend/customer/login.html`)

#### Changes
1. Added "Forgot Password?" link below password field
2. Added multi-step forgot password section (initially hidden)

#### Form Steps (inline in login page):

**Step 1: Phone Entry**
- Input: Registered mobile number
- Button: "Request OTP"
- Validation: Mobile field required

**Step 2: OTP Entry**
- Six individual OTP input boxes
- Button: "Verify OTP"
- Secondary: "Resend OTP" button
- Features: Auto-focus between boxes, paste support

**Step 3: New Password**
- Input: New password (min 6 chars)
- Input: Confirm password
- Button: "Reset Password"
- Validation: Passwords must match

**Step 4: Success**
- Confirmation message
- Button: Back to Login

### JavaScript Functions (`frontend/js/auth.js`)

#### New Functions

1. **`showForgotPasswordForm(e)`**
   - Hide login form
   - Show phone entry step
   - Reset all state variables

2. **`backToLogin()`**
   - Return to login form
   - Clear all input fields
   - Reset state variables

3. **`handleForgotPassword(e)`**
   - Sends POST to `/api/auth/forgot-password`
   - Shows demo OTP in toast (demo mode)
   - Transitions to OTP entry step
   - Initializes OTP box event handlers
   - Error handling with toasts

4. **`handleVerifyResetOTP(e)`**
   - Collects 6-digit OTP from boxes (scoped to forgot password section)
   - Sends POST to `/api/auth/verify-reset-otp`
   - Stores reset token in memory
   - Transitions to password entry step
   - Error handling

5. **`handleResetPassword(e)`**
   - Validates password/confirm password match
   - Validates minimum length
   - Sends POST to `/api/auth/reset-password`
   - Shows success state
   - Clears reset token after success

#### Key Features
- Uses existing toast notification system
- Follows existing form handling patterns
- Reuses OTP box initialization (auto-focus, paste handling)
- Client-side validation with server-side enforcement
- All UI matches existing auth page styling
- Proper error handling with user-friendly messages

---

## Data Flow

### Complete User Journey

```
┌─────────────────────────────────────────────────────────────┐
│ Customer clicks "Forgot Password?" on login page            │
└────────────────────┬────────────────────────────────────────┘
                     ↓
        ┌─────────────────────────────┐
        │ Enter registered phone       │
        │ POST /api/auth/forgot-password
        └─────────────┬───────────────┘
                      ↓
           ┌──────────────────────────┐
           │ Backend:                 │
           │ • Verify phone exists    │
           │ • Generate OTP (6 digit) │
           │ • Store in DB with 10min expiry
           │ • Send via SMS           │
           │ • Return demo OTP        │
           └──────────┬───────────────┘
                      ↓
        ┌─────────────────────────────┐
        │ User receives OTP           │
        │ Demo: shown in toast        │
        │ Production: via SMS         │
        └─────────────┬───────────────┘
                      ↓
        ┌─────────────────────────────┐
        │ User enters 6-digit OTP     │
        │ POST /api/auth/verify-reset-otp
        └─────────────┬───────────────┘
                      ↓
           ┌──────────────────────────┐
           │ Backend:                 │
           │ • Find OTP by mobile     │
           │ • Check expiry (10 min)  │
           │ • Check attempts (max 3) │
           │ • Verify code matches    │
           │ • Mark OTP as used       │
           │ • Generate reset token   │
           │ • Store with 15min expiry
           │ • Return reset token     │
           └──────────┬───────────────┘
                      ↓
        ┌─────────────────────────────┐
        │ User enters new password    │
        │ Confirm password            │
        │ POST /api/auth/reset-password
        └─────────────┬───────────────┘
                      ↓
           ┌──────────────────────────┐
           │ Backend:                 │
           │ • Find reset token       │
           │ • Check expiry (15 min)  │
           │ • Check not already used │
           │ • Hash new password      │
           │ • Update user.password_hash
           │ • Mark token as used     │
           │ • Return success         │
           └──────────┬───────────────┘
                      ↓
        ┌─────────────────────────────┐
        │ Show success message        │
        │ Button: Back to Login       │
        └─────────────┬───────────────┘
                      ↓
        ┌─────────────────────────────┐
        │ User logs in with new       │
        │ password                    │
        └─────────────────────────────┘
```

---

## Testing Guide

### Test Case 1: Complete Happy Path
```
1. Navigate to /customer/login.html
2. Click "Forgot Password?"
3. Enter registered mobile (e.g., 9876543210)
4. Click "Request OTP"
5. ✓ See success toast "OTP sent to your mobile!"
6. ✓ See demo OTP in info toast (demo mode only)
7. Enter the 6-digit OTP from toast
8. Click "Verify OTP"
9. ✓ See success toast "OTP verified!"
10. Enter new password (e.g., NewPass123)
11. Confirm password
12. Click "Reset Password"
13. ✓ See success message and "Back to Login" button
14. Click "Back to Login"
15. ✓ Return to login form
16. Login with mobile and NEW password
17. ✓ Login successful, redirected to home
18. Try login with OLD password
19. ✗ Login fails (old password invalid)
```

### Test Case 2: Invalid Phone
```
1. Click "Forgot Password?"
2. Enter unregistered phone (e.g., 9111111111)
3. Click "Request OTP"
4. ✗ Error: "Phone number not registered. Please create an account."
5. ✓ Form stays on phone entry
```

### Test Case 3: Wrong OTP
```
1. Request OTP for valid phone
2. Enter WRONG 6-digit code
3. Click "Verify OTP"
4. ✗ Error: "Invalid OTP. X attempts remaining."
5. Can retry up to 3 attempts total
6. After 3 attempts, error: "Too many failed attempts..."
7. Must request new OTP
```

### Test Case 4: Expired OTP
```
1. Request OTP (expires in 10 minutes)
2. Wait 10+ minutes
3. Enter OTP code
4. Click "Verify OTP"
5. ✗ Error: "OTP has expired. Please request a new one."
```

### Test Case 5: Expired Reset Token
```
1. Request OTP and verify OTP successfully
2. Note: Reset token expires in 15 minutes
3. Wait 15+ minutes
4. Enter new password
5. Click "Reset Password"
6. ✗ Error: "Reset token has expired. Please request a new password reset."
```

### Test Case 6: Reused Reset Token
```
1. Request OTP and verify OTP successfully
2. Get reset token
3. Use token to set password (success)
4. Try to use same token again to set different password
5. ✗ Error: "Reset token has already been used. Please request a new password reset."
```

### Test Case 7: Password Validation
```
1. Complete OTP verification
2. Enter password less than 6 characters
3. ✗ Client-side error: "Password must be at least 6 characters."
4. Enter new password (min 6 chars)
5. Enter different confirmation
6. ✗ Error: "Passwords do not match."
```

### Test Case 8: Existing Authentication Still Works
```
1. Login normally (without password reset)
2. ✓ Works as before
3. Register with existing flow
4. ✓ OTP registration works
5. Delivery OTP flow
6. ✓ Still works
```

---

## API Reference

### Request/Response Examples

#### 1. Request OTP
```
POST /api/auth/forgot-password
Content-Type: application/json

{
  "mobile": "9876543210"
}

Response (200 - Demo Mode):
{
  "message": "OTP sent for password reset.",
  "demo_otp": "123456"
}

Response (200 - Production):
{
  "message": "OTP sent for password reset."
}

Error (400):
{
  "detail": "Phone number not registered. Please create an account."
}

Error (429):
{
  "detail": "Please wait 60s before requesting a new OTP."
}
```

#### 2. Verify OTP
```
POST /api/auth/verify-reset-otp
Content-Type: application/json

{
  "mobile": "9876543210",
  "code": "123456"
}

Response (200):
{
  "message": "OTP verified.",
  "reset_token": "abcd1234..."
}

Error (400):
{
  "detail": "Invalid OTP. 2 attempts remaining."
}

Error (400):
{
  "detail": "OTP has expired. Please request a new one."
}

Error (400):
{
  "detail": "Too many failed attempts. Please request a new OTP."
}
```

#### 3. Reset Password
```
POST /api/auth/reset-password
Content-Type: application/json

{
  "reset_token": "abcd1234...",
  "new_password": "NewPass123"
}

Response (200):
{
  "message": "Password reset successful."
}

Error (400):
{
  "detail": "Invalid reset token. Please request a new password reset."
}

Error (400):
{
  "detail": "Reset token has expired. Please request a new password reset."
}

Error (400):
{
  "detail": "Reset token has already been used. Please request a new password reset."
}
```

---

## Security Features

### Server-Side Validation
- ✓ Phone number verified to exist in database
- ✓ OTP generated and verified server-side only
- ✓ OTP expires after 10 minutes
- ✓ Maximum 3 failed OTP attempts
- ✓ Reset token expires after 15 minutes
- ✓ Reset token is single-use only
- ✓ Password hashing uses bcrypt (existing implementation)
- ✓ No plain-text passwords stored or logged

### Client-Side Validation
- ✓ Mobile number format validation (10-digit Indian)
- ✓ Password minimum length check
- ✓ Password confirmation match
- ✓ OTP required before password reset
- ✓ Reset token required for password update

### Demo Mode Security
- Demo OTP returned in response ONLY for testing
- Would be removed for production SMS integration
- Clear indication that OTP is demo

---

## Future SMS Integration

The implementation is designed for easy migration to real SMS provider.

### Current Setup (Demo Mode)
```
SMS_PROVIDER=mock  (in .env)
```

### To Switch to Real SMS
1. Update `.env` to `SMS_PROVIDER=msg91`
2. Add `SMS_API_KEY` to `.env`
3. Remove demo OTP from forgot-password response
4. Password reset logic remains unchanged

### Code Structure for Migration
- `send_password_reset_otp_sms()` uses provider abstraction
- Backend logic separated from SMS delivery
- Frontend knows nothing of provider implementation
- No changes needed to authentication flow

---

## Files Modified/Created

### Created
- `backend/app/models/password_reset_token.py` (28 lines)
- `backend/app/services/password_reset_service.py` (103 lines)

### Modified
- `backend/app/models/__init__.py` - Added PasswordResetToken import
- `backend/app/routes/auth.py` - Added 3 new routes, updated imports
- `backend/app/schemas/auth.py` - Added 3 new request schemas
- `backend/app/services/sms_service.py` - Added password reset SMS function
- `frontend/customer/login.html` - Added forgot password link and form
- `frontend/js/auth.js` - Added 5 new JavaScript functions

### Not Modified (as required)
- ✓ Existing authentication routes untouched
- ✓ Password hashing mechanism unchanged
- ✓ User registration flow unchanged
- ✓ Customer login logic unchanged
- ✓ Admin authentication unchanged
- ✓ Delivery features unchanged
- ✓ Cart/checkout features unchanged
- ✓ Payment processing unchanged
- ✓ Database schema (except new table) unchanged

---

## Configuration

### Environment Variables
```
SMS_PROVIDER=mock           # For demo mode
DEMO_MODE=true              # Returns demo OTP in response
JWT_EXPIRE_MINUTES=1440     # Token expiry (unchanged)
```

### OTP Settings (in password_reset_service.py)
```
OTP_EXPIRE_MINUTES = 10          # OTP valid for 10 minutes
RESET_TOKEN_EXPIRE_MINUTES = 15  # Reset token valid for 15 minutes
```

### OTP Service Settings (existing)
```
MAX_ATTEMPTS = 3                 # Failed verification attempts
RESEND_COOLDOWN_SECONDS = 60     # Wait before requesting new OTP
```

---

## Deployment Notes

### Database Migration
- PasswordResetToken table auto-created on app startup
- Uses existing SQLAlchemy ORM
- No manual migration scripts needed

### Backward Compatibility
- ✓ All existing authentication continues to work
- ✓ Existing OTP purposes (REGISTRATION, LOGIN, DELIVERY) unchanged
- ✓ No changes to user login/registration flows
- ✓ Existing routes unmodified

### Performance Considerations
- Reset tokens indexed on (mobile, token) for O(1) lookup
- OTP lookup by mobile and purpose (existing optimization)
- Minimal database footprint per reset attempt
- No impact on other authentication flows

---

## Maintenance

### Monitoring
- Check backend logs for failed reset attempts
- Monitor OTP request rate (should be reasonable)
- Track reset token expiration events

### Cleanup
- OTP records auto-marked as used when verified
- Reset tokens auto-marked as used when password updated
- Old expired tokens can be purged from database if needed

### Troubleshooting

**OTP not appearing in demo mode?**
- Check DEMO_MODE=true in .env
- Verify SMS_PROVIDER=mock in .env
- Check browser console for API response

**Phone number not recognized?**
- Verify phone is registered under different number
- Check user record in database
- Ensure account is verified (is_verified=true)

**Reset token expired too quickly?**
- Default is 15 minutes - adjust RESET_TOKEN_EXPIRE_MINUTES if needed
- Consider longer expiry for real-world scenario

**OTP requests rate limited?**
- Default cooldown is 60 seconds
- Adjust RESEND_COOLDOWN_SECONDS if needed
- Message appears: "Please wait 60s before requesting a new OTP"

---

## Summary

✓ Complete implementation of customer forgot password flow  
✓ Demo OTP for testing without SMS provider  
✓ Server-side OTP generation and verification  
✓ Short-lived reset tokens with single-use enforcement  
✓ Password hashing using existing bcrypt utility  
✓ SMS provider abstraction for easy real SMS migration  
✓ Comprehensive error handling and validation  
✓ UI matches existing customer page styling  
✓ All existing authentication remains functional  
✓ Strict scope adherence - no unrelated changes  

**Status:** Production ready with demo SMS  
**Ready for:** Real SMS integration and production deployment
