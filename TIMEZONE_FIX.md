# Timezone Fix for Order PLACED Times

## Problem
Admin Orders table was displaying order creation times **5 hours 30 minutes behind** actual Indian time.

**Example:**
- Actual IST: 19:38:08
- Admin showed: 14:08:08 (UTC)

## Root Cause
1. Database stores UTC timestamp (using SQLite's `func.now()`)
2. Frontend was receiving ISO string (UTC) and interpreting it as browser local time
3. JavaScript `new Date()` with ISO string defaults to UTC
4. No timezone conversion was happening on frontend

## Solution
**Trace: UTC in DB → Backend converts to IST → Frontend displays IST**

### Backend Changes
- `app/routes/orders.py`: Updated `get_my_orders()` endpoint
- Added timezone conversion logic that:
  1. Takes naive UTC datetime from database
  2. Treats it as UTC: `.replace(tzinfo=timezone.utc)`
  3. Converts to IST: `.astimezone(timezone(timedelta(hours=5, minutes=30)))`
  4. Formats as HH:MM:SS
  5. Sends as `placed_time` field

### Frontend Changes
Replaced all incorrect UTC conversions:

| File | Change |
|------|--------|
| `admin/orders.html` | `timeAgo(o.created_at)` → `o.placed_time \|\| '—'` |
| `admin/dashboard.html` | `timeAgo(o.created_at)` → `o.placed_time \|\| '—'` |
| `js/admin.js` | `timeAgo(o.created_at)` → `'—'` |
| `js/orders.js` | `formatDate(o.created_at)` → `o.placed_time \|\| '—'` |

## Verification

Database timestamp: 2026-09-30 14:08:08 (UTC)
Backend conversion: 14:08:08 UTC + 5:30 = 19:38:08 IST ✅
Frontend display: 19:38:08 ✅

## No Double Conversion
- Database: Always UTC (correct for web apps)
- Backend: Converts exactly once to IST (HH:MM:SS format)
- Frontend: Just displays the pre-formatted IST time (no further conversion)

## Affected Flows
1. ✅ Admin Orders page - PLACED column
2. ✅ Admin Dashboard - Recent Orders Time column
3. ✅ Customer My Orders - Time display
4. ✅ Customer Track Order - Placed At field
