/**
 * Cart management — all prices come from the server.
 */
let _cart = { id: null, items: [], subtotal: 0, item_count: 0 };

async function loadCart() {
  try {
    _cart = await api.get('/api/cart');
    updateCartUI();
    updateCartBadge();
    return _cart;
  } catch (err) {
    console.error('Cart load error:', err);
    return _cart;
  }
}

let _addingToCart = false;
let _cartOperations = new Set();
let _showingAddedToastId = null;

async function addToCart(productId, quantity = 1) {
  const opKey = `add-${productId}`;
  if (_cartOperations.has(opKey)) return false;
  _cartOperations.add(opKey);
  try {
    _cart = await api.post('/api/cart/items', { product_id: productId, quantity });
    updateCartUI();
    updateCartBadge();
    showAddedToCartToast();
    return true;
  } catch (err) {
    showToast(err.message, 'error');
    return false;
  } finally {
    _cartOperations.delete(opKey);
  }
}

async function updateCartItem(itemId, quantity) {
  const opKey = `update-${itemId}`;
  if (_cartOperations.has(opKey)) return false;
  _cartOperations.add(opKey);
  try {
    _cart = await api.patch(`/api/cart/items/${itemId}`, { quantity });
    updateCartUI();
    updateCartBadge();
    return true;
  } catch (err) {
    showToast(err.message, 'error');
    return false;
  } finally {
    _cartOperations.delete(opKey);
  }
}

async function removeCartItem(itemId) {
  const opKey = `remove-${itemId}`;
  if (_cartOperations.has(opKey)) return false;
  _cartOperations.add(opKey);
  try {
    _cart = await api.del(`/api/cart/items/${itemId}`);
    updateCartUI();
    updateCartBadge();
    return true;
  } catch (err) {
    showToast(err.message, 'error');
    return false;
  } finally {
    _cartOperations.delete(opKey);
  }
}

async function clearCart() {
  try {
    await api.del('/api/cart');
    _cart = { id: null, items: [], subtotal: 0, item_count: 0 };
    updateCartUI();
    updateCartBadge();
    return true;
  } catch (err) {
    showToast(err.message, 'error');
    return false;
  }
}

function updateCartBadge() {
  document.querySelectorAll('.cart-badge').forEach(el => {
    el.textContent = _cart.item_count || 0;
    if (_cart.item_count > 0) el.classList.remove('hidden');
    else el.classList.add('hidden');
  });
}

function updateCartUI() {
  // cart.html specific
  const listEl = document.getElementById('cart-items-list');
  const emptyEl = document.getElementById('cart-empty');
  const summaryEl = document.getElementById('cart-summary');

  if (!listEl) return;

  if (!_cart.items || _cart.items.length === 0) {
    listEl.innerHTML = '';
    emptyEl && emptyEl.classList.remove('hidden');
    summaryEl && summaryEl.classList.add('hidden');
    return;
  }
  emptyEl && emptyEl.classList.add('hidden');
  summaryEl && summaryEl.classList.remove('hidden');

  listEl.innerHTML = _cart.items.map(item => `
    <div class="cart-item" data-item-id="${item.id}">
      <img class="cart-item-img" src="${item.product_image || 'https://images.unsplash.com/photo-1601050690597-df0568f70950?w=150'}" alt="${item.product_name}" loading="lazy">
      <div>
        <div class="cart-item-name">${item.product_name}</div>
        ${item.stock_error ? `<div class="alert alert-error" style="margin-top:.4rem;padding:.45rem .6rem;font-size:.82rem">${item.stock_error}</div>` : ''}
        <div class="cart-item-price">${formatPrice(item.unit_price)} each</div>
        <div class="qty-control" style="margin-top:.5rem;display:inline-flex;">
          <button class="qty-btn" onclick="changeQty(${item.id}, ${item.quantity - 1})">−</button>
          <span class="qty-val">${item.quantity}</span>
          <button class="qty-btn" onclick="changeQty(${item.id}, ${item.quantity + 1})">+</button>
        </div>
      </div>
      <div class="cart-item-actions">
        <div class="cart-item-subtotal">${formatPrice(item.subtotal)}</div>
        <button class="cart-remove-btn" onclick="removeItem(${item.id})">🗑 Remove</button>
      </div>
    </div>
  `).join('');

  // Update summary
  const deliveryFee = 30; // preview — actual is server-computed at checkout
  document.getElementById('summary-subtotal').textContent = formatPrice(_cart.subtotal);
  document.getElementById('summary-items').textContent = _cart.item_count + ' item(s)';
  const checkoutLink = document.getElementById('checkout-link');
  const hasStockIssue = _cart.items.some(item => item.stock_error);
  if (checkoutLink) {
    checkoutLink.classList.toggle('disabled', hasStockIssue);
    checkoutLink.setAttribute('aria-disabled', hasStockIssue ? 'true' : 'false');
    checkoutLink.title = hasStockIssue ? 'Remove or reduce out-of-stock items before checkout.' : '';
  }
}

function goToCheckout(event) {
  if (_cart.items.some(item => item.stock_error)) {
    event.preventDefault();
    showToast('Please remove or reduce out-of-stock items before checkout.', 'error');
  }
}

async function changeQty(itemId, qty) {
  if (qty < 1) {
    if (confirm('Remove this item from cart?')) await removeCartItem(itemId);
    return;
  }
  const item = _cart.items.find(i => i.id === itemId);
  if (item && qty > item.stock_quantity) {
    showToast(`You're already at the maximum available quantity. Only ${item.stock_quantity} ${item.product_name} ${item.stock_quantity === 1 ? 'is' : 'are'} currently in stock.`, 'info');
    return;
  }
  await updateCartItem(itemId, qty);
}

async function removeItem(itemId) {
  await removeCartItem(itemId);
}

function showAddedToCartToast() {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  // Remove existing "Added to cart" toast if present
  if (_showingAddedToastId) {
    const existingToast = document.getElementById(_showingAddedToastId);
    if (existingToast && existingToast.parentElement) {
      if (existingToast.timeoutId) clearTimeout(existingToast.timeoutId);
      if (existingToast.slideoutTimeoutId) clearTimeout(existingToast.slideoutTimeoutId);
      existingToast.remove();
    }
    _showingAddedToastId = null;
  }

  const toastId = 'added-to-cart-toast-' + Date.now();
  const toast = document.createElement('div');
  toast.id = toastId;
  toast.className = 'toast toast-success toast-cart';
  toast.innerHTML = `
    <span class="toast-icon">✅</span>
    <div class="toast-cart-body">
      <div class="toast-msg">Added to cart!</div>
      <button type="button" class="toast-view-cart">View Cart →</button>
    </div>
    <button type="button" class="toast-close" aria-label="Close">×</button>
  `;

  const closeBtn = toast.querySelector('.toast-close');
  const viewBtn = toast.querySelector('.toast-view-cart');

  closeBtn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (toast.timeoutId) clearTimeout(toast.timeoutId);
    if (toast.slideoutTimeoutId) clearTimeout(toast.slideoutTimeoutId);
    toast.remove();
    _showingAddedToastId = null;
  });

  viewBtn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    window.location.href = '/customer/cart.html';
  });

  _showingAddedToastId = toastId;
  container.appendChild(toast);
  toast.timeoutId = setTimeout(() => {
    if (!toast.isConnected) return;
    toast.style.animation = 'slideOutRight .3s ease forwards';
    toast.slideoutTimeoutId = setTimeout(() => {
      toast.remove();
      _showingAddedToastId = null;
    }, 300);
  }, 6000);
}
