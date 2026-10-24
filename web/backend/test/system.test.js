import { after, before, test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash, randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import net from 'node:net';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import request from 'supertest';

// Every test run gets its own database. No production orders or stock are altered.
const dbName = `teaflow_test_${randomUUID().replaceAll('-', '')}`;
process.env.NODE_ENV = 'test';
process.env.DB_NAME = dbName;
process.env.SESSION_SECRET = 'test-session-secret-that-is-long-enough-1234567890';
process.env.CASHIER_DEVICE_KEY = 'test-cashier-key';
process.env.KITCHEN_DEVICE_KEY = 'test-kitchen-key';
execFileSync(process.execPath, [path.resolve('scripts/setup.js')], { env: process.env, stdio: 'pipe' });
const { pool } = await import('../src/db.js');
const { config } = await import('../src/config.js');
const { createApp } = await import('../src/app.js');
const { passwordHash } = await import('../src/security.js');
const { createOrder, confirmPayment, dailySummary, updateStatus } = await import('../src/orders.js');
const app = createApp();
const agents = {};
let variant, secondVariant, ingredientId, addon;
let deviceToken;
async function terminalLogin(role = 'cashier', password = 'testing-password-123') {
  return request(app).post('/api/iot/auth/login').set('X-Device-Key', config.cashierKey)
    .send({ email: `${role}@tests.local`, password });
}

function csrf(response) {
  const match = response.text.match(/name="csrf-token" content="([^"]+)"/);
  assert.ok(match, `CSRF token missing: HTTP ${response.status}`);
  return match[1];
}
async function post(agent, url, data, page = '/') {
  const token = csrf(await agent.get(page));
  return agent.post(url).type('form').send({ ...data, _csrf: token });
}
function orderData(quantity = 1) {
  return { customer_name: 'Test Customer', request_key: randomUUID(), lines: [{ variant_id: variant, quantity, sugar: 50, ice: 'light', addon_ids: [] }] };
}
async function stock() { const [[row]] = await pool.execute('SELECT stock_milli FROM tf_ingredients WHERE id=?', [ingredientId]); return row.stock_milli; }

before(async () => {
  const [[v]] = await pool.query("SELECT id FROM tf_variants WHERE size='Small' ORDER BY id LIMIT 1");
  variant = v.id;
  const [[v2]] = await pool.query("SELECT id FROM tf_variants WHERE size='Large' ORDER BY id LIMIT 1"); secondVariant = v2.id;
  const [[base]] = await pool.query("SELECT id FROM tf_ingredients WHERE name='Drink base (sample)'"); ingredientId = base.id;
  const [[a]] = await pool.query('SELECT * FROM tf_addons ORDER BY id LIMIT 1'); addon = a;
  for (const role of ['admin', 'cashier', 'kitchen', 'customer']) {
    const email = `${role}@tests.local`;
    await pool.execute('INSERT INTO tf_users (name,email,password_hash,role) VALUES (?,?,?,?)', [`Test ${role}`, email, await passwordHash('testing-password-123'), role]);
    agents[role] = request.agent(app);
    const result = await post(agents[role], '/login', { email, password: 'testing-password-123' }, '/login');
    assert.equal(result.status, 302);
  }
  const terminal = await terminalLogin();
  assert.equal(terminal.status, 200);
  deviceToken = terminal.body.token;
});

after(async () => {
  await app.locals.sessionStore.close();
  await pool.end();
  const mysql = (await import('mysql2/promise')).default;
  const connection = await mysql.createConnection(config.mysql);
  try {
    assert.match(dbName, /^teaflow_test_[a-f0-9]{32}$/);
    await connection.query(`DROP DATABASE \`${dbName}\``);
  } finally { await connection.end(); }
});

test('menu renders BESTBREW products and all required drink options', async () => {
  const result = await request(app).get('/');
  assert.equal(result.status, 200);
  assert.match(result.text, /Wintermelon/);
  assert.match(result.text, /name="sugar"/);
  assert.match(result.text, /name="ice"/);
  assert.match(result.text, /Crushed Oreo/);
  assert.ok(result.headers['content-security-policy']);
});

test('daily sales use Manila payment boundaries, all channels and completed orders without multiplying money', async () => {
  const sample = orderData(2);
  sample.lines.push({ variant_id: secondVariant, quantity: 3, sugar: 100, ice: 'regular', addon_ids: [addon.id] });
  const first = await createOrder(sample, 'test:daily', 'cashier');
  const second = await createOrder(orderData(4), 'test:daily', 'web');
  const beforeDay = await createOrder(orderData(7), 'test:daily', 'cashier');
  const afterDay = await createOrder(orderData(8), 'test:daily', 'cashier');
  const unpaid = await createOrder(orderData(9), 'test:daily', 'cashier');
  // These fixtures belong exclusively to this run's temporary database.
  for (const [order, at, status] of [
    [first, '2001-04-01 16:00:00', 'completed'],
    [second, '2001-04-02 15:59:59', 'queued'],
    [beforeDay, '2001-04-01 15:59:59', 'completed'],
    [afterDay, '2001-04-02 16:00:00', 'queued'],
  ]) await pool.execute('UPDATE tf_orders SET paid_at=?,status=? WHERE id=?', [at, status, order.id]);
  const expected = { day: '2001-04-02', timezone: 'Asia/Manila', paid_orders: 2,
    drinks_sold: 9, total_cents: first.total_cents + second.total_cents };
  for (const instant of ['2001-04-01T16:00:00Z', '2001-04-02T15:59:59Z']) {
    const { generated_at, ...actual } = await dailySummary(new Date(instant));
    assert.equal(generated_at, instant.replace('Z', '.000Z'));
    assert.deepEqual(actual, expected);
  }
  const empty = await dailySummary(new Date('2001-03-01T00:00:00Z'));
  assert.equal(empty.paid_orders, 0); assert.equal(empty.drinks_sold, 0); assert.equal(empty.total_cents, 0);
  assert.equal((await pool.execute('SELECT paid_at FROM tf_orders WHERE id=?', [unpaid.id]))[0][0].paid_at, null);
});

test('daily summary is cashier-only, authenticated and never cached', async () => {
  assert.equal((await request(app).get('/api/iot/summary')).status, 401);
  assert.equal((await request(app).get('/api/iot/summary').set('X-Device-Key', config.kitchenKey)).status, 403);
  const response = await request(app).get('/api/iot/summary').set('X-Device-Key', config.cashierKey);
  assert.equal(response.status, 200); assert.equal(response.headers['cache-control'], 'no-store');
  assert.equal(response.body.timezone, 'Asia/Manila');
  assert.match(response.body.day, /^\d{4}-\d{2}-\d{2}$/);
  for (const field of ['paid_orders', 'drinks_sold', 'total_cents']) assert.ok(Number.isSafeInteger(response.body[field]));
});

test('all staff pages render for the owner', async () => {
  for (const route of ['/staff/orders', '/staff/kitchen', '/staff/inventory', '/staff/products']) {
    const result = await agents.admin.get(route);
    assert.equal(result.status, 200, route);
  }
});

test('web checkout requires login and state changes require CSRF', async () => {
  assert.equal((await request(app).post('/cart/add').type('form').send({ variant_id: variant })).status, 419);
  assert.equal((await request(app).get('/staff/orders')).status, 302);
  assert.equal((await agents.customer.get('/staff/orders')).status, 403);
});

test('registration always creates a customer even if an admin role is submitted', async () => {
  const agent = request.agent(app);
  agents.otherCustomer = agent;
  const result = await post(agent, '/register', { name: 'New Customer', email: 'new@tests.local', password: 'long-password-123', confirm_password: 'long-password-123', role: 'admin' }, '/register');
  assert.equal(result.status, 302);
  const [[row]] = await pool.execute('SELECT role,password_hash FROM tf_users WHERE email=?', ['new@tests.local']);
  assert.equal(row.role, 'customer'); assert.notEqual(row.password_hash, 'long-password-123');
});

test('customer cart, checkout, private tracking and history form one complete flow', async () => {
  const add = await post(agents.customer, '/cart/add', { variant_id: variant, quantity: 2, sugar: 25, ice: 'none', addon_ids: addon.id, unit_cents: 1 });
  assert.equal(add.status, 302);
  const page = await agents.customer.get('/cart'); assert.equal(page.status, 200);
  const key = page.text.match(/name="request_key" value="([^"]+)"/)[1];
  const total = page.text.match(/name="quoted_total_cents" value="(\d+)"/)[1];
  const checkout = await agents.customer.post('/checkout').type('form').send({ _csrf: csrf(page), request_key: key, quoted_total_cents: total, customer_name: 'Pickup Customer', total_cents: 1 });
  assert.equal(checkout.status, 302); assert.match(checkout.headers.location, /^\/orders\//);
  const track = await agents.customer.get(checkout.headers.location); assert.equal(track.status, 200);
  assert.match(track.text, /25% sugar/); assert.match(track.text, /none ice/); assert.match(track.text, /Awaiting payment/);
  const receipt = await agents.cashier.get(checkout.headers.location); assert.equal(receipt.status, 200);
  assert.equal((await agents.otherCustomer.get(checkout.headers.location)).status, 404);
  const duplicate = await agents.customer.post('/checkout').type('form').send({ _csrf: csrf(page), request_key: key, quoted_total_cents: total, customer_name: 'Pickup Customer' });
  assert.equal(duplicate.headers.location, checkout.headers.location);
  const [[count]] = await pool.execute('SELECT COUNT(*) AS count FROM tf_orders WHERE request_key=?', [key]); assert.equal(count.count, 1);
  assert.equal((await agents.customer.get('/my-orders')).status, 200);
  assert.equal((await request(app).get(checkout.headers.location)).status, 302);
});

test('server pricing ignores supplied item totals and records toppings', async () => {
  const data = orderData(2); data.lines[0].addon_ids = [addon.id]; data.lines[0].unit_cents = 1;
  const [[price]] = await pool.execute('SELECT price_cents FROM tf_variants WHERE id=?', [variant]);
  const order = await createOrder(data, 'test:price', 'cashier');
  assert.equal(order.total_cents, 2 * (price.price_cents + addon.price_cents));
  assert.equal(order.items[0].addons[0].name, addon.name);
});

test('creating an unpaid order neither deducts stock nor exposes it to kitchen', async () => {
  const before = await stock();
  const order = await createOrder(orderData(), 'test:unpaid', 'cashier');
  assert.equal(await stock(), before);
  const state = await request(app).get('/api/iot/state').set('X-Device-Key', config.kitchenKey);
  assert.equal(state.status, 200); assert.ok(!state.body.orders.some(row => row.id === order.id));
});

test('concurrent creation retries produce one order and conflicting payloads are rejected', async () => {
  const data = orderData();
  const [a, b] = await Promise.all([createOrder(data, 'test:retry', 'cashier'), createOrder(data, 'test:retry', 'cashier')]);
  assert.equal(a.id, b.id);
  await assert.rejects(createOrder({ ...data, customer_name: 'Other' }, 'test:retry', 'cashier'), error => error.status === 409);
});

test('simultaneous payment retries deduct once and publish one paid event', async () => {
  const order = await createOrder(orderData(2), 'test:payment', 'cashier');
  const before = await stock();
  const [a, b] = await Promise.all([confirmPayment(order.id), confirmPayment(order.id)]);
  assert.equal(a.status, 'queued'); assert.equal(b.status, 'queued'); assert.equal(await stock(), before - 2000);
  const [[event]] = await pool.execute("SELECT COUNT(*) AS count FROM tf_order_events WHERE order_id=? AND type='paid'", [order.id]); assert.equal(event.count, 1);
  const [[movement]] = await pool.execute('SELECT COUNT(*) AS count FROM tf_stock_movements WHERE order_id=? AND ingredient_id=?', [order.id, ingredientId]); assert.equal(movement.count, 1);
});

test('insufficient stock rolls back payment and all ingredient deductions', async () => {
  const order = await createOrder(orderData(2), 'test:insufficient', 'cashier');
  const saved = await stock(); await pool.execute('UPDATE tf_ingredients SET stock_milli=1000 WHERE id=?', [ingredientId]);
  try {
    await assert.rejects(confirmPayment(order.id), error => error.status === 409);
    assert.equal(await stock(), 1000);
    const [[paid]] = await pool.execute('SELECT status,paid_at FROM tf_orders WHERE id=?', [order.id]); assert.equal(paid.status, 'unpaid'); assert.equal(paid.paid_at, null);
    const [[movements]] = await pool.execute('SELECT COUNT(*) AS count FROM tf_stock_movements WHERE order_id=?', [order.id]); assert.equal(movements.count, 0);
  } finally { await pool.execute('UPDATE tf_ingredients SET stock_milli=? WHERE id=?', [saved, ingredientId]); }
});

test('kitchen and cashier roles enforce the status sequence and harmless retries', async () => {
  const order = await createOrder(orderData(), 'test:status', 'cashier');
  await assert.rejects(updateStatus(order.id, 'preparing', 'kitchen'), error => error.status === 409);
  await confirmPayment(order.id);
  await assert.rejects(updateStatus(order.id, 'ready', 'kitchen'), error => error.status === 409);
  await assert.rejects(updateStatus(order.id, 'preparing', 'cashier'), error => error.status === 403);
  await updateStatus(order.id, 'preparing', 'kitchen'); await updateStatus(order.id, 'preparing', 'kitchen');
  await updateStatus(order.id, 'ready', 'kitchen');
  await assert.rejects(updateStatus(order.id, 'completed', 'kitchen'), error => error.status === 403);
  await updateStatus(order.id, 'completed', 'cashier');
  const state = await request(app).get('/api/iot/state').set('X-Device-Key', config.kitchenKey);
  assert.ok(!state.body.orders.some(row => row.id === order.id));
});

test('device credentials and roles protect creation and payment endpoints', async () => {
  assert.equal((await request(app).get('/api/iot/state')).status, 401);
  assert.equal((await request(app).post('/api/iot/orders').set('X-Device-Key', config.kitchenKey).send(orderData())).status, 403);
  const created = await request(app).post('/api/iot/orders').set('X-Device-Key', config.cashierKey).set('X-Operator-Token', deviceToken).send(orderData()); assert.equal(created.status, 201);
  assert.equal((await request(app).post(`/api/iot/orders/${created.body.id}/pay`).set('X-Device-Key', config.kitchenKey).send({})).status, 403);
  const paid = await request(app).post(`/api/iot/orders/${created.body.id}/pay`).set('X-Device-Key', config.cashierKey).set('X-Operator-Token', deviceToken).send({}); assert.equal(paid.status, 200);
  const [[audit]] = await pool.execute('SELECT o.paid_by,u.email FROM tf_orders o JOIN tf_users u ON u.id=o.paid_by WHERE o.id=?', [created.body.id]);
  assert.equal(audit.email, 'cashier@tests.local');
});

test('device timing uses the original UTC payment time and ready orders stay visible until handover', async () => {
  const order = await createOrder(orderData(), 'test:device-timing', 'cashier');
  const readState = key => request(app).get('/api/iot/state').set('X-Device-Key', key);
  let response = await readState(config.cashierKey);
  assert.equal(response.body.orders.find(row => row.id === order.id).paid_at_unix, null);
  await confirmPayment(order.id);
  // Backdate only this isolated test database, never shop orders.
  await pool.execute('UPDATE tf_orders SET paid_at=DATE_SUB(UTC_TIMESTAMP(), INTERVAL 10 MINUTE) WHERE id=?', [order.id]);
  const [[saved]] = await pool.execute('SELECT paid_at FROM tf_orders WHERE id=?', [order.id]);
  const paidAt = Math.floor(saved.paid_at.getTime() / 1000);
  response = await readState(config.kitchenKey);
  assert.equal(response.status, 200);
  assert.equal(response.body.orders.find(row => row.id === order.id).paid_at_unix, paidAt);
  assert.equal(response.body.server_unix, Math.floor(Date.parse(response.body.server_time) / 1000));
  assert.ok(response.body.server_unix - paidAt >= 600 && response.body.server_unix - paidAt < 610);
  await updateStatus(order.id, 'preparing', 'kitchen');
  await updateStatus(order.id, 'ready', 'kitchen');
  for (const key of [config.kitchenKey, config.cashierKey]) {
    for (let i = 0; i < 2; ++i) {
      const snapshot = (await readState(key)).body.orders.find(row => row.id === order.id);
      assert.equal(snapshot.status, 'ready'); assert.equal(snapshot.paid, true);
      assert.equal(snapshot.paid_at_unix, paidAt);
    }
  }
  await updateStatus(order.id, 'completed', 'cashier');
  for (const key of [config.kitchenKey, config.cashierKey])
    assert.ok(!(await readState(key)).body.orders.some(row => row.id === order.id));
});

test('cashier terminal can load, create, pay and replay with its device key and no account login', async () => {
  const headers = { 'X-Device-Key': config.cashierKey };
  assert.equal((await request(app).get('/api/iot/menu').set(headers)).status, 200);
  assert.equal((await request(app).get('/api/iot/state').set(headers)).status, 200);
  const data = orderData();
  const created = await request(app).post('/api/iot/orders').set(headers).send(data);
  assert.equal(created.status, 201);
  const replay = await request(app).post('/api/iot/orders').set(headers).send(data);
  assert.equal(replay.body.id, created.body.id);
  const paid = await request(app).post(`/api/iot/orders/${created.body.id}/pay`).set(headers).send({});
  assert.equal(paid.status, 200);
  const [[audit]] = await pool.execute('SELECT paid_by FROM tf_orders WHERE id=?', [created.body.id]);
  assert.equal(audit.paid_by, null, 'Device-only operation must not invent an account attribution');
  assert.equal((await request(app).post('/api/iot/auth/logout').set(headers).send({})).status, 401);
});

test('terminal sign-in rejects wrong passwords and non-cashier accounts', async () => {
  assert.equal((await terminalLogin('cashier', 'wrong')).status, 401);
  assert.equal((await terminalLogin('customer')).status, 403);
  assert.equal((await terminalLogin('kitchen')).status, 403);
  assert.equal((await request(app).post('/api/iot/auth/login').send({ email: 'admin@tests.local', password: 'testing-password-123' })).status, 401);
  assert.equal((await request(app).get('/api/iot/state').set('X-Device-Key', config.cashierKey).set('X-Operator-Token', 'invalid')).status, 401);
});

test('terminal logout revokes the session and switching to admin preserves submission retries', async () => {
  const login = await terminalLogin(); assert.equal(login.status, 200);
  const headers = { 'X-Device-Key': config.cashierKey, 'X-Operator-Token': login.body.token };
  const data = orderData();
  const created = await request(app).post('/api/iot/orders').set(headers).send(data); assert.equal(created.status, 201);
  assert.equal((await request(app).post('/api/iot/auth/logout').set(headers).send({})).status, 200);
  assert.equal((await request(app).get('/api/iot/state').set(headers)).status, 401);
  const admin = await terminalLogin('admin'); assert.equal(admin.status, 200); assert.equal(admin.body.user.role, 'admin');
  const nextHeaders = { 'X-Device-Key': config.cashierKey, 'X-Operator-Token': admin.body.token };
  const replay = await request(app).post('/api/iot/orders').set(nextHeaders).send(data);
  assert.equal(replay.status, 201); assert.equal(replay.body.id, created.body.id);
  const paid = await request(app).post(`/api/iot/orders/${created.body.id}/pay`).set(nextHeaders).send({}); assert.equal(paid.status, 200);
  const [[audit]] = await pool.execute('SELECT u.email FROM tf_orders o JOIN tf_users u ON u.id=o.paid_by WHERE o.id=?', [created.body.id]);
  assert.equal(audit.email, 'admin@tests.local');
  assert.equal((await request(app).post('/api/iot/auth/logout').set(nextHeaders).send({})).status, 200);
});

test('expired, differently bound, and demoted terminal sessions cannot access orders', async () => {
  const login = await terminalLogin('admin');
  const sid = `device:${createHash('sha256').update(login.body.token).digest('hex')}`;
  const headers = { 'X-Device-Key': config.cashierKey, 'X-Operator-Token': login.body.token };
  const [[saved]] = await pool.execute('SELECT data FROM tf_sessions WHERE session_id=?', [sid]);
  assert.ok(!saved.data.includes(login.body.token), 'Store a token hash, not its usable value');
  const altered = JSON.parse(saved.data); altered.deviceKey = 'different-device';
  await pool.execute('UPDATE tf_sessions SET data=? WHERE session_id=?', [JSON.stringify(altered), sid]);
  assert.equal((await request(app).get('/api/iot/state').set(headers)).status, 401);
  await pool.execute('UPDATE tf_sessions SET data=? WHERE session_id=?', [saved.data, sid]);
  await pool.execute("UPDATE tf_users SET role='customer' WHERE email='admin@tests.local'");
  try { assert.equal((await request(app).get('/api/iot/state').set(headers)).status, 403); }
  finally { await pool.execute("UPDATE tf_users SET role='admin' WHERE email='admin@tests.local'"); }
  await pool.execute('UPDATE tf_sessions SET expires=? WHERE session_id=?', [Date.now() - 1, sid]);
  assert.equal((await request(app).get('/api/iot/state').set(headers)).status, 401);
});

test('invalid sugar, quantity, and ice values are rejected', async () => {
  for (const patch of [{ sugar: 99 }, { quantity: -1 }, { ice: 'bad' }, { addon_ids: [addon.id, addon.id] }]) {
    const data = orderData(); Object.assign(data.lines[0], patch);
    await assert.rejects(createOrder(data, 'test:invalid', 'cashier'), error => error.status === 422);
  }
});

test('recipe edits do not alter requirements for already submitted orders', async () => {
  const order = await createOrder(orderData(), 'test:snapshot', 'cashier');
  await pool.execute('UPDATE tf_recipes SET amount_milli=2000 WHERE variant_id=? AND ingredient_id=?', [variant, ingredientId]);
  try { const before = await stock(); await confirmPayment(order.id); assert.equal(await stock(), before - 1000); }
  finally { await pool.execute('UPDATE tf_recipes SET amount_milli=1000 WHERE variant_id=? AND ingredient_id=?', [variant, ingredientId]); }
});

test('low-stock notices use inclusive thresholds and refreshes keep the same event ID', async () => {
  const previous = await stock(); await pool.execute('UPDATE tf_ingredients SET stock_milli=low_milli WHERE id=?', [ingredientId]);
  try {
    const a = await request(app).get('/api/iot/state').set('X-Device-Key', config.kitchenKey);
    const b = await request(app).get('/api/iot/state').set('X-Device-Key', config.kitchenKey);
    assert.equal(a.body.low_stock, true); assert.ok(a.body.low_stock_items.some(row => row.id === ingredientId)); assert.equal(a.body.event_id, b.body.event_id);
  } finally { await pool.execute('UPDATE tf_ingredients SET stock_milli=? WHERE id=?', [previous, ingredientId]); }
});

test('staff restocks are audited and customers cannot adjust stock', async () => {
  assert.equal((await post(agents.customer, `/staff/inventory/${ingredientId}`, { kind: 'restock', quantity: '2', low_limit: '10', reason: 'Test restock' })).status, 403);
  const before = await stock();
  const result = await post(agents.cashier, `/staff/inventory/${ingredientId}`, { kind: 'restock', quantity: '2', low_limit: '10', reason: 'Test restock' }); assert.equal(result.status, 302); assert.equal(await stock(), before + 2000);
  execFileSync(process.execPath, [path.resolve('scripts/setup.js')], { env: process.env, stdio: 'pipe' });
  assert.equal(await stock(), before + 2000, 'Re-running setup must not reset recorded stock');
  const [[movement]] = await pool.execute('SELECT reason FROM tf_stock_movements WHERE ingredient_id=? ORDER BY id DESC LIMIT 1', [ingredientId]); assert.equal(movement.reason, 'Test restock');
});

test('owner can create, edit and remove a drink while cashier cannot manage products', async () => {
  const forbidden = await post(agents.cashier, '/staff/products', { name: 'Forbidden', category: 'Milktea', small: '29', large: '39' }); assert.equal(forbidden.status, 403);
  assert.equal((await post(agents.admin, '/staff/products', { name: 'Owner Test Drink', category: 'Milktea', small: '29', large: '39' })).status, 302);
  const [[product]] = await pool.query("SELECT id FROM tf_products WHERE name='Owner Test Drink'");
  assert.equal((await post(agents.admin, `/staff/products/${product.id}`, { name: 'Updated Drink', category: 'Milktea', small: '30', large: '40', active: '1' })).status, 302);
  assert.equal((await post(agents.admin, `/staff/products/${product.id}`, { action: 'delete' })).status, 302);
  const [[deleted]] = await pool.execute('SELECT active,archived FROM tf_products WHERE id=?', [product.id]); assert.equal(deleted.active, 0); assert.equal(deleted.archived, 1);
});

test('recipe quantities follow configured sugar and ice rules', async () => {
  const before = await stock();
  await pool.execute("UPDATE tf_recipes SET option_basis='sugar' WHERE variant_id=? AND ingredient_id=?", [variant, ingredientId]);
  try {
    const order = await createOrder(orderData(2), 'test:sugar', 'cashier');
    await confirmPayment(order.id);
    assert.equal(await stock(), before - 1000);
    await pool.execute("UPDATE tf_recipes SET option_basis='ice' WHERE variant_id=? AND ingredient_id=?", [variant, ingredientId]);
    const noIce = orderData(); noIce.lines[0].ice = 'none';
    const other = await createOrder(noIce, 'test:ice', 'cashier');
    await confirmPayment(other.id);
    assert.equal(await stock(), before - 1000);
  } finally { await pool.execute("UPDATE tf_recipes SET option_basis='fixed' WHERE variant_id=? AND ingredient_id=?", [variant, ingredientId]); }
});

test('Flask forwards real device requests to Express and reports backend outages', async () => {
  const server = app.listen(0, '127.0.0.1'); await once(server, 'listening');
  const portProbe = net.createServer(); portProbe.listen(0, '127.0.0.1'); await once(portProbe, 'listening');
  const flaskPort = portProbe.address().port;
  await new Promise(resolve => portProbe.close(resolve));
  const python = spawn(path.resolve('../../.tools/python/python.exe'), [path.resolve('../../iot/api/app.py')], {
    env: { ...process.env, EXPRESS_BASE_URL: `http://127.0.0.1:${server.address().port}`, FLASK_HOST: '127.0.0.1', FLASK_PORT: String(flaskPort) },
    windowsHide: true, stdio: 'pipe',
  });
  const base = `http://127.0.0.1:${flaskPort}`;
  const headers = { 'X-Device-Key': config.cashierKey, 'Content-Type': 'application/json' };
  try {
    let ready = false;
    for (let i = 0; i < 50; i++) {
      try { const response = await fetch(`${base}/iot/state`, { headers: { 'X-Device-Key': config.kitchenKey } }); if (response.ok) { ready = true; break; } } catch {}
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert.ok(ready, 'Flask relay did not become ready');
    const signedIn = await fetch(`${base}/auth/login`, { method: 'POST', headers, body: JSON.stringify({ email: 'admin@tests.local', password: 'testing-password-123' }) });
    assert.equal(signedIn.status, 200);
    headers['X-Operator-Token'] = (await signedIn.json()).token;
    const created = await fetch(`${base}/orders`, { method: 'POST', headers, body: JSON.stringify(orderData()) }); assert.equal(created.status, 201);
    const order = await created.json();
    const paid = await fetch(`${base}/orders/${order.id}/pay`, { method: 'POST', headers, body: '{}' }); assert.equal(paid.status, 200);
    const state = await fetch(`${base}/iot/state`, { headers: { 'X-Device-Key': config.kitchenKey } });
    assert.ok((await state.json()).orders.some(row => row.id === order.id));
    assert.equal((await fetch(`${base}/auth/logout`, { method: 'POST', headers, body: '{}' })).status, 200);
    assert.equal((await fetch(`${base}/iot/state`, { headers })).status, 401);
    await new Promise(resolve => server.close(resolve));
    assert.equal((await fetch(`${base}/iot/state`, { headers })).status, 503);
  } finally {
    python.kill();
    if (server.listening) await new Promise(resolve => server.close(resolve));
    await once(python, 'exit').catch(() => {});
  }
});

test('stored names are escaped in staff views and logout removes session access', async () => {
  const data = orderData(); data.customer_name = '<script>alert(1)</script>';
  await createOrder(data, 'test:escaping', 'cashier');
  const page = await agents.cashier.get('/staff/orders'); assert.match(page.text, /&lt;script&gt;/); assert.ok(!page.text.includes('<script>alert(1)</script>'));
  const customer = agents.customer;
  assert.equal((await post(customer, '/logout', {})).status, 302);
  assert.equal((await customer.get('/my-orders')).status, 302);
});
