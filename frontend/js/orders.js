/**
 * Orders — list and detail display.
 */
async function loadMyOrders() {
  const container = document.getElementById('orders-container');
  if (!container) return;
  container.innerHTML = '<p class="text-muted text-center">Loading orders...</p>';
  try {
    const orders = await api.get('/api/orders');
    if (!orders.length) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🛵</div>
          <h3>No orders yet</h3>
          <p>Your order history will appear here.</p>
          <a href="/customer/menu.html" class="btn btn-primary mt-2">Order Now</a>
        </div>`;
      return;
    }
    container.innerHTML = orders.map(o => `
      <div class="card mb-2" style="cursor:pointer" onclick="window.location.href='/customer/track-order.html?order_id=${o.id}'">
        <div class="card-body" style="display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap">
          <div>
            <div style="font-weight:700;font-size:1.05rem">${o.order_number}</div>
            <div class="text-muted" style="font-size:.85rem">${o.placed_time || '—'}</div>
          </div>
          <div style="text-align:center">
            <span class="badge badge-${o.order_type === 'DELIVERY' ? 'info' : 'secondary'}">${o.order_type}</span>
          </div>
          <div class="price">${formatPrice(o.total)}</div>
          <span class="badge status-${o.status}">${o.status.replace(/_/g, ' ')}</span>
          <a href="/customer/track-order.html?order_id=${o.id}" class="btn btn-outline btn-sm">Track</a>
        </div>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  }
}

async function loadOrderDetail(orderId) {
  try {
    return await api.get(`/api/orders/${orderId}`);
  } catch (err) {
    showToast(err.message, 'error');
    return null;
  }
}

function renderOrderTimeline(status, history) {
  const histMap = {};
  (history || []).forEach(h => histMap[h.status] = h.created_at);

  // Explicit completion checks — avoids ambiguity of index-based currentIdx approach
  const orderPlacedCompleted = true; // every successfully created order has this done

  const paymentVerifiedStatuses = new Set([
    'PAYMENT_VERIFIED', 'ACCEPTED', 'PREPARING', 'READY', 'OUT_FOR_DELIVERY', 'DELIVERED'
  ]);
  const paymentVerifiedCompleted = paymentVerifiedStatuses.has(status);

  const deliveryCompleted = status === 'DELIVERED';

  const steps = [
    {
      icon: '📋',
      label: 'Order Placed',
      completed: orderPlacedCompleted,
      timeKey: 'PENDING',
    },
    {
      icon: '💳',
      label: 'Payment Verified',
      completed: paymentVerifiedCompleted,
      timeKey: 'PAYMENT_VERIFIED',
    },
    {
      icon: '🎉',
      label: 'Delivery Completed',
      completed: deliveryCompleted,
      timeKey: 'DELIVERED',
    },
  ];

  return `<div class="order-timeline">` + steps.map((step, i) => {
    const done   = step.completed;
    // A step is active if it is not yet completed but the previous step is completed
    const active = !done && (i === 0 || steps[i - 1].completed);
    const cls    = done ? 'completed' : active ? 'active' : '';
    const time   = histMap[step.timeKey] ? formatDate(histMap[step.timeKey]) : '';
    return `
      <div class="timeline-step ${cls}">
        <div class="timeline-dot">${done ? '✓' : step.icon}</div>
        <div class="timeline-content">
          <div class="timeline-label">${step.label}</div>
          ${time ? `<div class="timeline-time">${time}</div>` : ''}
        </div>
      </div>`;
  }).join('') + `</div>`;
}
