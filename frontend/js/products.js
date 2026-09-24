/**
 * Products — menu display.
 */
let _products = [];
let _categories = [];
let _activeCategory = null;
let _searchQuery = '';
let _inventorySocket = null;
let _inventoryReconnectTimer = null;

async function loadProducts() {
  const container = document.getElementById('products-grid');
  if (!container) return;
  container.innerHTML = '<p class="text-muted text-center" style="grid-column:1/-1;padding:3rem">Loading menu...</p>';
  try {
    [_products, _categories] = await Promise.all([
      api.get('/api/products'),
      api.get('/api/categories'),
    ]);
    renderCategoryPills();
    renderProducts();
    connectInventorySocket();
  } catch (err) {
    container.innerHTML = `<div class="alert alert-error" style="grid-column:1/-1">${err.message}</div>`;
  }
}

function renderCategoryPills() {
  const container = document.getElementById('category-pills');
  if (!container) return;
  container.innerHTML = `
    <button class="category-pill ${!_activeCategory ? 'active' : ''}" onclick="filterCategory(null)">All</button>
    ${_categories.map(c => `
      <button class="category-pill ${_activeCategory === c.id ? 'active' : ''}" onclick="filterCategory(${c.id})">${c.name}</button>
    `).join('')}
  `;
}

function renderProducts() {
  const container = document.getElementById('products-grid');
  if (!container) return;

  let filtered = _products;
  if (_activeCategory) filtered = filtered.filter(p => p.category_id === _activeCategory);
  const availOnly = document.getElementById('avail-only')?.checked;
  if (availOnly) filtered = filtered.filter(p => p.is_available);
  if (_searchQuery) filtered = filtered.filter(p => p.name.toLowerCase().includes(_searchQuery.toLowerCase()));

  if (!filtered.length) {
    container.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <div class="empty-icon">🔍</div>
        <h3>No items found</h3>
        <p>Try a different search or category.</p>
      </div>`;
    return;
  }
  container.innerHTML = filtered.map(p => renderProductCard(p)).join('');
}

function renderProductCard(p) {
  const imgSrc = p.image_url || 'https://images.unsplash.com/photo-1601050690597-df0568f70950?w=600';
  const catName = _categories.find(c => c.id === p.category_id)?.name || '';
  return `
    <div class="food-card">
      <div class="food-card-img">
        <img src="${imgSrc}" alt="${p.name}" loading="lazy">
        ${p.is_featured ? '<div class="food-card-badge"><span class="badge badge-warning">⭐ Popular</span></div>' : ''}
        ${p.stock_quantity <= 0 || !p.is_available ? '<div class="food-card-unavailable">OUT OF STOCK</div>' : ''}
      </div>
      <div class="food-card-body">
        <div class="food-card-category">${catName}</div>
        <div class="food-card-name">${p.name}</div>
        <div class="food-card-desc">${p.description || ''}</div>
        <div class="text-muted" style="font-size:.82rem;margin-top:.35rem">${p.stock_quantity > 0 && p.is_available ? `Available (${p.stock_quantity} left)` : 'OUT OF STOCK'}</div>
        <div class="food-card-footer">
          <div class="food-card-price">${typeof formatPrice === 'function' ? formatPrice(p.price) : '₹' + p.price}</div>
          ${p.is_available && p.stock_quantity > 0
            ? `<button class="btn btn-primary btn-sm" onclick="handleAddToCart(${p.id})">+ Add</button>`
            : `<span class="text-muted" style="font-size:.85rem">Unavailable</span>`
          }
        </div>
      </div>
    </div>`;
}

function filterCategory(catId) {
  _activeCategory = catId;
  renderCategoryPills();
  renderProducts();
}

function handleSearch(q) {
  _searchQuery = q;
  renderProducts();
}

async function handleAddToCart(productId) {
  if (!api.getToken()) {
    showToast('Please login to add items to cart.', 'warning');
    setTimeout(() => window.location.href = '/customer/login.html', 1500);
    return;
  }
  const product = _products.find(p => p.id === productId);
  if (!product || !product.is_available || product.stock_quantity <= 0) {
    showToast(`${product?.name || 'This product'} is currently out of stock.`, 'error');
    return;
  }
  await addToCart(productId, 1);
}

function connectInventorySocket() {
  if (_inventorySocket && [_inventorySocket.OPEN, _inventorySocket.CONNECTING].includes(_inventorySocket.readyState)) return;
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsHost = window.location.host;
  const wsUrl = `${wsProtocol}//${wsHost}/api/ws/inventory`;
  _inventorySocket = new WebSocket(wsUrl);
  _inventorySocket.onopen = () => clearTimeout(_inventoryReconnectTimer);
  _inventorySocket.onmessage = event => {
    try {
      const update = JSON.parse(event.data);
      if (update.type !== 'stock_update') return;
      const product = _products.find(item => item.id === update.product_id);
      if (!product) return;
      product.stock_quantity = update.stock_quantity;
      product.is_available = update.is_available;
      renderProducts();
    } catch (error) {
      console.warn('Inventory WebSocket message error:', error);
    }
  };
  _inventorySocket.onclose = () => {
    _inventoryReconnectTimer = setTimeout(connectInventorySocket, 3000);
  };
  _inventorySocket.onerror = () => _inventorySocket.close();
}
