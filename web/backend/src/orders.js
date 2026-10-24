import { createHash, randomUUID } from 'node:crypto';
import { pool, transaction } from './db.js';
import { AppError, id, requireValue } from './errors.js';

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
export const orderCode = value => `BB-${String(value).padStart(5, '0')}`;
export const json = value => typeof value === 'string' ? JSON.parse(value) : value;

export function validateLines(input) {
  requireValue(Array.isArray(input) && input.length > 0 && input.length <= 30, 'Choose between 1 and 30 cart items.');
  return input.map(line => {
    const quantity = Number(line.quantity), sugar = Number(line.sugar);
    requireValue(Number.isInteger(quantity) && quantity >= 1 && quantity <= 20, 'Quantity must be between 1 and 20.');
    requireValue([0, 25, 50, 75, 100].includes(sugar), 'Choose a valid sugar level.');
    requireValue(['none', 'light', 'regular'].includes(line.ice), 'Choose a valid ice level.');
    requireValue(Array.isArray(line.addon_ids) && line.addon_ids.length <= 4, 'Choose up to four toppings.');
    const addons = line.addon_ids.map(id).sort((a, b) => a - b);
    requireValue(new Set(addons).size === addons.length, 'A topping can only be selected once per drink.');
    return { variant_id: id(line.variant_id), quantity, sugar, ice: line.ice, addon_ids: addons };
  });
}

export async function quote(input, db = pool) {
  const lines = validateLines(input), items = [], requirements = new Map();
  let total = 0;
  for (const line of lines) {
    const [variants] = await db.execute('SELECT v.*, p.name, p.active, p.archived FROM tf_variants v JOIN tf_products p ON p.id=v.product_id WHERE v.id=?', [line.variant_id]);
    const variant = variants[0];
    requireValue(variant && variant.active && !variant.archived, 'A drink is unavailable. Remove it from your cart.');
    const [recipes] = await db.execute('SELECT * FROM tf_recipes WHERE variant_id=? ORDER BY ingredient_id', [variant.id]);
    requireValue(recipes.length, `${variant.name} has no recipe configured and is currently unavailable.`);
    let unit = variant.price_cents;
    const addons = [];
    for (const addonId of line.addon_ids) {
      const [rows] = await db.execute('SELECT * FROM tf_addons WHERE id=?', [addonId]);
      const addon = rows[0];
      requireValue(addon && addon.active, 'A topping is unavailable. Remove it from your cart.');
      unit += addon.price_cents;
      addons.push({ id: addon.id, name: addon.name, price_cents: addon.price_cents });
      requirements.set(addon.ingredient_id, (requirements.get(addon.ingredient_id) || 0) + addon.amount_milli * line.quantity);
    }
    for (const recipe of recipes) {
      const percent = recipe.option_basis === 'sugar' ? line.sugar : recipe.option_basis === 'ice' ? ({ none: 0, light: 50, regular: 100 })[line.ice] : 100;
      const used = Math.round(recipe.amount_milli * percent / 100) * line.quantity;
      if (used) requirements.set(recipe.ingredient_id, (requirements.get(recipe.ingredient_id) || 0) + used);
    }
    items.push({ ...line, product_name: variant.name, size: variant.size, unit_cents: unit, addons });
    total += unit * line.quantity;
  }
  return { items, requirements, total_cents: total };
}

export async function getOrder(orderId, db = pool) {
  const [orders] = await db.execute('SELECT * FROM tf_orders WHERE id=?', [id(orderId)]);
  requireValue(orders.length, 'Order not found.', 404);
  const order = orders[0];
  const [items] = await db.execute('SELECT * FROM tf_order_items WHERE order_id=? ORDER BY id', [order.id]);
  return { ...order, code: orderCode(order.id), items: items.map(item => ({ ...item, addons: json(item.addons) })) };
}

export async function createOrder(data, actor, source, customerId = null) {
  requireValue(typeof data.customer_name === 'string' && data.customer_name.trim().length >= 1 && data.customer_name.trim().length <= 80, 'Enter a customer name of up to 80 characters.');
  requireValue(uuidPattern.test(data.request_key || ''), 'Your checkout has expired. Reload the cart.');
  const lines = validateLines(data.lines), name = data.customer_name.trim();
  const hash = createHash('sha256').update(JSON.stringify([actor, source, name, lines])).digest('hex');
  const replay = existing => {
    requireValue(existing.actor === actor && existing.request_hash === hash, 'This checkout identifier belongs to a different order.', 409);
    return getOrder(existing.id);
  };
  try {
    const result = await transaction(async db => {
      const [existing] = await db.execute('SELECT * FROM tf_orders WHERE request_key=?', [data.request_key]);
      if (existing.length) {
        requireValue(existing[0].actor === actor && existing[0].request_hash === hash, 'This checkout identifier belongs to a different order.', 409);
        return existing[0].id;
      }
      const priced = await quote(lines, db);
      if (data.quoted_total_cents !== undefined) requireValue(Number(data.quoted_total_cents) === priced.total_cents, 'Menu prices changed. Review your cart total before submitting.');
      const [insert] = await db.execute('INSERT INTO tf_orders (request_key,request_hash,tracking_token,customer_id,customer_name,actor,source,total_cents) VALUES (?,?,?,?,?,?,?,?)', [data.request_key, hash, randomUUID(), customerId, name, actor, source, priced.total_cents]);
      for (const item of priced.items) {
        await db.execute('INSERT INTO tf_order_items (order_id,product_name,size,sugar,ice,quantity,unit_cents,addons) VALUES (?,?,?,?,?,?,?,?)', [insert.insertId, item.product_name, item.size, item.sugar, item.ice, item.quantity, item.unit_cents, JSON.stringify(item.addons)]);
      }
      for (const [ingredientId, quantity] of priced.requirements) {
        await db.execute('INSERT INTO tf_requirements (order_id,ingredient_id,amount_milli) VALUES (?,?,?)', [insert.insertId, ingredientId, quantity]);
      }
      return insert.insertId;
    });
    return getOrder(result);
  } catch (error) {
    if (error.code === 'ER_DUP_ENTRY') {
      const [existing] = await pool.execute('SELECT * FROM tf_orders WHERE request_key=?', [data.request_key]);
      if (existing.length) return replay(existing[0]);
    }
    throw error;
  }
}

export async function confirmPayment(orderId, paidBy = null) {
  await transaction(async db => {
    const [orders] = await db.execute('SELECT * FROM tf_orders WHERE id=? FOR UPDATE', [id(orderId)]);
    requireValue(orders.length, 'Order not found.', 404);
    const order = orders[0];
    if (order.paid_at) return;
    requireValue(order.status === 'unpaid', 'This order cannot be paid.', 409);
    const [needs] = await db.execute('SELECT * FROM tf_requirements WHERE order_id=? ORDER BY ingredient_id', [order.id]);
    requireValue(needs.length, 'This order has no ingredient requirements.', 409);
    const locked = [];
    for (const need of needs) {
      const [ingredients] = await db.execute('SELECT * FROM tf_ingredients WHERE id=? FOR UPDATE', [need.ingredient_id]);
      const ingredient = ingredients[0];
      requireValue(ingredient && ingredient.stock_milli >= need.amount_milli, `Insufficient stock: ${ingredient?.name || 'missing ingredient'}. Payment was not confirmed.`, 409);
      locked.push([need, ingredient]);
    }
    for (const [need, ingredient] of locked) {
      await db.execute('UPDATE tf_ingredients SET stock_milli=stock_milli-? WHERE id=?', [need.amount_milli, ingredient.id]);
      await db.execute('INSERT INTO tf_stock_movements (ingredient_id,order_id,user_id,delta_milli,reason) VALUES (?,?,?,?,?)', [ingredient.id, order.id, paidBy, -need.amount_milli, `Payment confirmed: ${orderCode(order.id)}`]);
    }
    await db.execute("UPDATE tf_orders SET status='queued',paid_at=UTC_TIMESTAMP(),paid_by=? WHERE id=?", [paidBy, order.id]);
    await db.execute("INSERT INTO tf_order_events (order_id,type) VALUES (?,'paid')", [order.id]);
  });
  return getOrder(orderId);
}

export async function updateStatus(orderId, target, role) {
  const allowed = { admin: ['preparing', 'ready', 'completed'], kitchen: ['preparing', 'ready'], cashier: ['completed'] };
  requireValue(allowed[role]?.includes(target), 'Your role cannot perform this action.', 403);
  await transaction(async db => {
    const [orders] = await db.execute('SELECT * FROM tf_orders WHERE id=? FOR UPDATE', [id(orderId)]);
    requireValue(orders.length, 'Order not found.', 404);
    const order = orders[0];
    requireValue(order.paid_at, 'Payment must be confirmed first.', 409);
    if (order.status === target) return;
    const next = { queued: 'preparing', preparing: 'ready', ready: 'completed' };
    requireValue(next[order.status] === target, 'This order cannot move to that status. Refresh and try again.', 409);
    await db.execute('UPDATE tf_orders SET status=? WHERE id=?', [target, order.id]);
    await db.execute('INSERT INTO tf_order_events (order_id,type) VALUES (?,?)', [order.id, target]);
  });
  return getOrder(orderId);
}

export async function listOrders({ kitchen = false, completed = false, customerId } = {}) {
  let sql = 'SELECT id FROM tf_orders WHERE 1=1'; const parameters = [];
  if (customerId) { sql += ' AND customer_id=?'; parameters.push(customerId); }
  if (kitchen) sql += " AND paid_at IS NOT NULL AND status IN ('queued','preparing','ready')";
  else if (completed) sql += " AND status='completed'";
  else sql += " AND status!='completed'";
  sql += kitchen ? ' ORDER BY paid_at,id LIMIT 100' : ' ORDER BY id DESC LIMIT 100';
  const [rows] = await pool.execute(sql, parameters);
  return Promise.all(rows.map(row => getOrder(row.id)));
}

export async function lowStock(db = pool) {
  const [rows] = await db.execute('SELECT * FROM tf_ingredients WHERE stock_milli<=low_milli ORDER BY name');
  return rows;
}

export async function paidEventId() {
  const [[row]] = await pool.query("SELECT COALESCE(MAX(id),0) AS id FROM tf_order_events WHERE type='paid'");
  return String(row.id);
}

// Payments are stored in UTC. A Manila business day starts at 16:00 UTC
// on the preceding date. Aggregate every paid order, including handovers.
export async function dailySummary(now = new Date()) {
  const offset = 8 * 3600 * 1000;
  const day = new Date(now.getTime() + offset).toISOString().slice(0, 10);
  const start = new Date(Date.parse(`${day}T00:00:00Z`) - offset);
  const end = new Date(start.getTime() + 86400000);
  // One statement gives a consistent snapshot. Count item quantities in a
  // scalar subquery so multi-line orders cannot multiply the sales total.
  const [[row]] = await pool.execute(`SELECT COUNT(*) AS paid_orders,
    COALESCE(SUM(o.total_cents),0) AS total_cents,
    COALESCE(SUM((SELECT COALESCE(SUM(i.quantity),0) FROM tf_order_items i WHERE i.order_id=o.id)),0) AS drinks_sold
    FROM tf_orders o WHERE o.paid_at>=? AND o.paid_at<?`, [start, end]);
  const totals = Object.fromEntries(['paid_orders', 'total_cents', 'drinks_sold'].map(field => [field, Number(row[field])]));
  requireValue(Object.values(totals).every(value => Number.isSafeInteger(value) && value >= 0), 'Sales totals are outside the supported range.', 500);
  return { day, timezone: 'Asia/Manila', ...totals, generated_at: now.toISOString() };
}

export function deviceOrder(order) {
  // mysql2 reads DATETIME as UTC (config.mysql.timezone). Send an absolute
  // payment time so terminal restarts and reconnects do not reset waiting time.
  const paidAt = order.paid_at ? Math.floor(new Date(order.paid_at).getTime() / 1000) : null;
  return { id: order.id, code: order.code, customer_name: order.customer_name, status: order.status, paid: !!order.paid_at, paid_at_unix: Number.isFinite(paidAt) ? paidAt : null, total_cents: order.total_cents, item: order.items.map(item => item.product_name).join(', '), qty: order.items.reduce((total, item) => total + item.quantity, 0), items: order.items };
}
