import express from 'express';
import session from 'express-session';
import { MysqlSessionStore } from './session-store.js';
import helmet from 'helmet';
import { rateLimit } from 'express-rate-limit';
import path from 'node:path';
import { randomBytes, randomUUID } from 'node:crypto';
import { config, root, webRoot, backendRoot } from './config.js';
import { pool, transaction } from './db.js';
import { AppError, amount, id, requireValue } from './errors.js';
import { equalSecret, passwordHash, regenerate, save, verifyPassword } from './security.js';
import { catalog } from './catalog.js';
import { deviceLogin, deviceLogout, optionalDeviceOperator } from './device-auth.js';
import { confirmPayment, createOrder, dailySummary, deviceOrder, getOrder, listOrders, lowStock, paidEventId, quote, updateStatus, validateLines } from './orders.js';

export function createApp() {
  requireValue(config.sessionSecret?.length >= 32, 'Run setup to create the session secret.', 500);
  const app = express();
  Object.assign(app.locals, { user: null, csrf: '', flash: null, cartCount: 0 });
  const store = new MysqlSessionStore();
  app.locals.sessionStore = store;
  app.disable('x-powered-by');
  app.set('view engine', 'ejs');
  app.set('views', path.join(webRoot, 'frontend/views'));
  app.use(helmet({ contentSecurityPolicy: { directives: { 'upgrade-insecure-requests': null } }, crossOriginEmbedderPolicy: false }));
  app.use('/assets', express.static(path.join(webRoot, 'frontend/public'), { index: false }));
  app.use('/images/menu', express.static(path.join(root, 'shared/assets/menu'), { index: false }));
  app.get('/vendor/bootstrap.css', (req, res) => res.sendFile(path.join(backendRoot, 'node_modules/bootstrap/dist/css/bootstrap.min.css')));
  app.get('/vendor/bootstrap.js', (req, res) => res.sendFile(path.join(backendRoot, 'node_modules/bootstrap/dist/js/bootstrap.bundle.min.js')));
  app.get('/up', async (req, res) => { await pool.query('SELECT 1'); res.json({ status: 'ok' }); });
  app.use(express.urlencoded({ extended: false, limit: '100kb' }));
  app.use(express.json({ limit: '100kb' }));

  const device = (req, res, next) => {
    const key = req.get('X-Device-Key');
    req.deviceRole = equalSecret(key, config.cashierKey) ? 'cashier' : equalSecret(key, config.kitchenKey) ? 'kitchen' : null;
    if (!req.deviceRole) return res.status(401).json({ message: 'Unauthorized device.' });
    next();
  };
  const deviceRate = rateLimit({ windowMs: 60000, limit: 120, standardHeaders: 'draft-8', legacyHeaders: false });
  app.use('/api/iot', deviceRate, device);
  app.use('/api/iot', (req, res, next) => { res.set('Cache-Control', 'no-store'); next(); });
  const deviceAuthRate = rateLimit({ windowMs: 60000, limit: 8, skipSuccessfulRequests: true,
    standardHeaders: 'draft-8', legacyHeaders: false, message: { message: 'Too many sign-in attempts. Wait one minute.' } });
  app.post('/api/iot/auth/login', deviceAuthRate, deviceLogin);
  app.use('/api/iot', optionalDeviceOperator);
  app.post('/api/iot/auth/logout', deviceLogout);
  app.get('/api/iot/menu', async (req, res) => {
    const data = await catalog();
    res.json({ products: data.products.filter(p => p.active), addons: data.addons.filter(a => a.active && a.in_stock) });
  });
  app.get('/api/iot/state', async (req, res) => {
    const orders = await listOrders({ kitchen: req.deviceRole === 'kitchen' });
    const low = await lowStock();
    const [[base]] = await pool.query("SELECT stock_milli FROM tf_ingredients WHERE name='Drink base (sample)'");
    const eventId = await paidEventId();
    const now = new Date();
    res.set('Cache-Control', 'no-store').json({ orders: orders.map(deviceOrder), low_stock: !!low.length, low_stock_items: low, stock: base ? base.stock_milli / 1000 : null, event_id: eventId, server_time: now.toISOString(), server_unix: Math.floor(now.getTime() / 1000) });
  });
  app.get('/api/iot/summary', async (req, res) => {
    requireValue(req.deviceRole === 'cashier', 'Only the cashier device can view sales totals.', 403);
    res.json(await dailySummary());
  });
  app.post('/api/iot/orders', async (req, res) => {
    requireValue(req.deviceRole === 'cashier', 'Only the cashier device can create orders.', 403);
    res.status(201).json(deviceOrder(await createOrder(req.body, 'device:cashier', 'cashier')));
  });
  app.post('/api/iot/orders/:id/pay', async (req, res) => {
    requireValue(req.deviceRole === 'cashier', 'Only the cashier device can confirm payment.', 403);
    res.json(deviceOrder(await confirmPayment(req.params.id, req.operator?.id ?? null)));
  });
  app.post('/api/iot/orders/:id/status', async (req, res) => res.json(deviceOrder(await updateStatus(req.params.id, req.body.status, req.deviceRole))));

  app.use(session({ name: 'teaflow.sid', secret: config.sessionSecret, store, resave: false, saveUninitialized: false,
    cookie: { httpOnly: true, sameSite: 'lax', secure: process.env.NODE_ENV === 'production', maxAge: 8 * 3600 * 1000 } }));
  app.use(async (req, res, next) => {
    if (req.session.userId) {
      const [[user]] = await pool.execute('SELECT id,name,email,role FROM tf_users WHERE id=?', [req.session.userId]);
      req.user = user;
    }
    req.session.csrf ||= randomBytes(32).toString('hex');
    Object.assign(res.locals, { user: req.user, csrf: req.session.csrf, flash: req.session.flash,
      money: cents => `₱${(Number(cents) / 100).toFixed(2)}`,
      stock: milli => (Number(milli) / 1000).toLocaleString('en-PH', { maximumFractionDigits: 3 }),
      when: date => new Date(date).toLocaleString('en-PH', { timeZone: 'Asia/Manila', dateStyle: 'medium', timeStyle: 'short' }),
      sampleRecipes: config.sampleRecipes, cartCount: (req.session.cart || []).reduce((sum, line) => sum + Number(line.quantity), 0),
    });
    delete req.session.flash;
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method) && !equalSecret(req.session.csrf, req.body._csrf)) return next(new AppError('Your session has expired. Reload the page and try again.', 419));
    next();
  });
  const login = (req, res, next) => {
    if (!req.user) { req.session.flash = { type: 'info', message: 'Please sign in to continue.' }; return res.redirect('/login'); }
    next();
  };
  const roles = (...allowed) => (req, res, next) => {
    if (!req.user) return res.redirect('/login');
    if (!allowed.includes(req.user.role)) return next(new AppError('You do not have access to this page.', 403));
    next();
  };
  const flash = (req, message) => { req.session.flash = { type: 'success', message }; };
  const authRate = rateLimit({ windowMs: 60000, limit: 8, standardHeaders: 'draft-8', legacyHeaders: false });
  app.get('/login', (req, res) => res.render('auth', { mode: 'login', title: 'Sign in' }));
  app.get('/register', (req, res) => res.render('auth', { mode: 'register', title: 'Create an account' }));
  app.post('/register', authRate, async (req, res) => {
    requireValue(typeof req.body.name === 'string' && req.body.name.trim().length >= 1 && req.body.name.trim().length <= 80, 'Enter your name (up to 80 characters).');
    requireValue(/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(req.body.email || '') && req.body.email.length <= 190, 'Enter a valid email.');
    requireValue(typeof req.body.password === 'string' && req.body.password.length >= 8 && req.body.password.length <= 128 && req.body.password === req.body.confirm_password, 'Passwords must match and contain 8 to 128 characters.');
    const email = req.body.email.trim().toLowerCase();
    const [[existing]] = await pool.execute('SELECT id FROM tf_users WHERE email=?', [email]);
    requireValue(!existing, 'An account already uses that email.');
    const [result] = await pool.execute("INSERT INTO tf_users (name,email,password_hash,role) VALUES (?,?,?,'customer')", [req.body.name.trim(), email, await passwordHash(req.body.password)]);
    const cart = req.session.cart || [];
    await regenerate(req.session);
    req.session.userId = result.insertId; req.session.cart = cart;
    flash(req, 'Welcome to BESTBREW. Your account is ready.');
    res.redirect('/');
  });
  app.post('/login', authRate, async (req, res) => {
    requireValue(typeof req.body.email === 'string' && req.body.email.length <= 190 && typeof req.body.password === 'string' && req.body.password.length <= 128, 'Enter your email and password.');
    const [[user]] = await pool.execute('SELECT * FROM tf_users WHERE email=?', [req.body.email.trim().toLowerCase()]);
    requireValue(user && await verifyPassword(req.body.password, user.password_hash), 'The email or password is incorrect.', 401);
    const cart = req.session.cart || [];
    await regenerate(req.session);
    req.session.userId = user.id; req.session.cart = cart;
    res.redirect(user.role === 'customer' ? '/' : user.role === 'kitchen' ? '/staff/kitchen' : '/staff/orders');
  });
  app.post('/logout', async (req, res) => {
    await new Promise((resolve, reject) => req.session.destroy(error => error ? reject(error) : resolve()));
    res.clearCookie('teaflow.sid'); res.redirect('/');
  });

  app.get('/', async (req, res) => res.render('menu', { ...(await catalog()), title: 'Your everyday favorite' }));
  app.post('/cart/add', async (req, res) => {
    const addons = req.body.addon_ids === undefined ? [] : Array.isArray(req.body.addon_ids) ? req.body.addon_ids : [req.body.addon_ids];
    const line = validateLines([{ ...req.body, addon_ids: addons }])[0];
    const cart = [...(req.session.cart || []), line];
    requireValue(cart.length <= 30, 'Your cart is full. Please check out first.');
    await quote(cart);
    req.session.cart = cart; delete req.session.checkoutKey;
    flash(req, 'Drink added to your cart.'); res.redirect('/');
  });
  app.post('/cart/:index/remove', (req, res) => {
    const index = Number(req.params.index);
    requireValue(Number.isInteger(index) && index >= 0, 'Invalid cart item.');
    req.session.cart = (req.session.cart || []).filter((_, position) => position !== index);
    delete req.session.checkoutKey; res.redirect('/cart');
  });
  app.get('/cart', async (req, res) => {
    const items = []; let total = 0, available = true;
    for (const line of req.session.cart || []) {
      try {
        const priced = await quote([line]); items.push(priced.items[0]); total += priced.total_cents;
      } catch (error) {
        if (!(error instanceof AppError)) throw error;
        available = false; items.push({ ...line, product_name: 'Unavailable item', size: '', addons: [], unit_cents: 0, error: error.message });
      }
    }
    req.session.checkoutKey ||= randomUUID();
    res.render('cart', { title: 'Your cart', items, total, available, requestKey: req.session.checkoutKey });
  });
  app.post('/checkout', login, async (req, res) => {
    requireValue(['customer', 'admin', 'cashier'].includes(req.user.role), 'This account cannot place orders.', 403);
    const last = req.session.lastCheckout;
    if (last?.key === req.body.request_key && last.userId === req.user.id) {
      requireValue(last.name === req.body.customer_name?.trim(), 'This checkout was already used for another order.', 409);
      return res.redirect(`/orders/${last.token}`);
    }
    requireValue(req.session.checkoutKey && equalSecret(req.session.checkoutKey, req.body.request_key), 'Your checkout has expired. Reload the cart.', 419);
    requireValue(/^\d+$/.test(String(req.body.quoted_total_cents)), 'Review your cart total.');
    const source = req.session.walkIn && ['admin', 'cashier'].includes(req.user.role) ? 'cashier' : 'web';
    const order = await createOrder({ ...req.body, lines: req.session.cart || [] }, `user:${req.user.id}`, source, source === 'web' ? req.user.id : null);
    req.session.lastCheckout = { key: req.body.request_key, token: order.tracking_token, name: req.body.customer_name.trim(), userId: req.user.id };
    req.session.cart = []; delete req.session.checkoutKey; delete req.session.walkIn;
    await save(req.session);
    res.redirect(`/orders/${order.tracking_token}`);
  });
  app.get('/orders/:token', login, async (req, res) => {
    const [[row]] = await pool.execute('SELECT id,customer_id FROM tf_orders WHERE tracking_token=?', [req.params.token]);
    requireValue(row && (row.customer_id === req.user.id || ['admin', 'cashier', 'kitchen'].includes(req.user.role)), 'Order not found.', 404);
    res.set('Cache-Control', 'no-store').render('track', { title: 'Your order', order: await getOrder(row.id) });
  });
  app.get('/my-orders', roles('customer'), async (req, res) => {
    const [ids] = await pool.execute('SELECT id FROM tf_orders WHERE customer_id=? ORDER BY id DESC LIMIT 100', [req.user.id]);
    res.render('orders', { title: 'My orders', orders: await Promise.all(ids.map(row => getOrder(row.id))), history: true, customerView: true });
  });

  app.get('/staff', roles('admin', 'cashier', 'kitchen'), (req, res) => res.redirect(req.user.role === 'kitchen' ? '/staff/kitchen' : '/staff/orders'));
  app.get('/staff/orders', roles('admin', 'cashier'), async (req, res) => res.render('orders', { title: 'Cashier orders', orders: await listOrders({ completed: req.query.history === '1' }), history: req.query.history === '1', customerView: false, low: await lowStock() }));
  app.post('/staff/walk-in', roles('admin', 'cashier'), (req, res) => { req.session.walkIn = true; flash(req, 'Walk-in order started. Choose drinks, then check out.'); res.redirect('/'); });
  app.post('/staff/orders/:id/pay', roles('admin', 'cashier'), async (req, res) => {
    await confirmPayment(req.params.id, req.user.id); flash(req, 'Payment confirmed. The order is in the kitchen queue.'); res.redirect('/staff/orders');
  });
  app.post('/staff/orders/:id/status', roles('admin', 'cashier', 'kitchen'), async (req, res) => {
    await updateStatus(req.params.id, req.body.status, req.user.role); flash(req, 'Order status updated.');
    res.redirect(req.body.status === 'completed' ? '/staff/orders' : '/staff/kitchen');
  });
  app.get('/staff/kitchen', roles('admin', 'kitchen'), async (req, res) => res.render('kitchen', { title: 'Kitchen queue', orders: await listOrders({ kitchen: true }), eventId: await paidEventId(), low: await lowStock() }));
  app.get('/staff/inventory', roles('admin', 'cashier'), async (req, res) => {
    const [ingredients] = await pool.query('SELECT * FROM tf_ingredients ORDER BY name');
    const [movements] = await pool.query('SELECT s.*, i.name, i.unit FROM tf_stock_movements s JOIN tf_ingredients i ON i.id=s.ingredient_id ORDER BY s.id DESC LIMIT 30');
    res.render('inventory', { title: 'Inventory', ingredients, movements });
  });
  app.post('/staff/ingredients', roles('admin', 'cashier'), async (req, res) => {
    requireValue(req.body.name?.trim().length > 0 && req.body.name.length <= 100 && req.body.unit?.trim().length > 0 && req.body.unit.length <= 30, 'Enter an ingredient name and stock unit.');
    await pool.execute('INSERT INTO tf_ingredients (name,unit) VALUES (?,?)', [req.body.name.trim(), req.body.unit.trim()]);
    flash(req, 'Ingredient added. Record its stock before using it.'); res.redirect('/staff/inventory');
  });
  app.post('/staff/inventory/:id', roles('admin', 'cashier'), async (req, res) => {
    requireValue(['restock', 'count'].includes(req.body.kind) && req.body.reason?.trim().length >= 3 && req.body.reason.length <= 200, 'Choose an adjustment type and give a reason.');
    const value = amount(req.body.quantity, 3), low = amount(req.body.low_limit, 3);
    await transaction(async db => {
      const [[ingredient]] = await db.execute('SELECT * FROM tf_ingredients WHERE id=? FOR UPDATE', [id(req.params.id)]);
      requireValue(ingredient, 'Ingredient not found.', 404);
      const delta = req.body.kind === 'restock' ? value : value - ingredient.stock_milli;
      await db.execute('UPDATE tf_ingredients SET stock_milli=stock_milli+?,low_milli=? WHERE id=?', [delta, low, ingredient.id]);
      await db.execute('INSERT INTO tf_stock_movements (ingredient_id,user_id,delta_milli,reason) VALUES (?,?,?,?)', [ingredient.id, req.user.id, delta, req.body.reason.trim()]);
    });
    flash(req, 'Stock updated and recorded.'); res.redirect('/staff/inventory');
  });
  app.get('/staff/products', roles('admin'), async (req, res) => res.render('products', { ...(await catalog()), title: 'Products & recipes' }));
  app.post('/staff/products', roles('admin'), async (req, res) => {
    requireValue(req.body.name?.trim().length > 0 && req.body.name.length <= 100 && req.body.category?.trim().length > 0 && req.body.category.length <= 100, 'Enter the product name and category.');
    const small = amount(req.body.small), large = amount(req.body.large);
    await transaction(async db => {
      const [result] = await db.execute('INSERT INTO tf_products (name,category,active) VALUES (?,?,FALSE)', [req.body.name.trim(), req.body.category.trim()]);
      await db.execute("INSERT INTO tf_variants (product_id,size,price_cents) VALUES (?,'Small',?),(?,'Large',?)", [result.insertId, small, result.insertId, large]);
    });
    flash(req, 'Product added. Configure its recipes, then enable availability.'); res.redirect('/staff/products');
  });
  app.post('/staff/products/:id', roles('admin'), async (req, res) => {
    const productId = id(req.params.id);
    if (req.body.action === 'delete') {
      await pool.execute('UPDATE tf_products SET active=FALSE,archived=TRUE WHERE id=?', [productId]);
      flash(req, 'Product removed from the menu. Existing order records are preserved.');
    } else {
      requireValue(req.body.name?.trim().length > 0 && req.body.name.length <= 100 && req.body.category?.trim().length > 0 && req.body.category.length <= 100, 'Enter the product name and category.');
      const small = amount(req.body.small), large = amount(req.body.large);
      await transaction(async db => {
        await db.execute('UPDATE tf_products SET name=?,category=?,active=? WHERE id=? AND archived=FALSE', [req.body.name.trim(), req.body.category.trim(), req.body.active === '1', productId]);
        await db.execute("UPDATE tf_variants SET price_cents=? WHERE product_id=? AND size='Small'", [small, productId]);
        await db.execute("UPDATE tf_variants SET price_cents=? WHERE product_id=? AND size='Large'", [large, productId]);
      });
      flash(req, 'Product updated.');
    }
    res.redirect('/staff/products');
  });
  app.post('/staff/addons/:id', roles('admin'), async (req, res) => {
    const price = amount(req.body.price), quantity = amount(req.body.amount, 3);
    requireValue(quantity > 0, 'A topping recipe quantity must be greater than zero.');
    await pool.execute('UPDATE tf_addons SET price_cents=?,active=?,ingredient_id=?,amount_milli=? WHERE id=?', [price, req.body.active === '1', id(req.body.ingredient_id), quantity, id(req.params.id)]);
    flash(req, 'Topping price and recipe updated.'); res.redirect('/staff/products');
  });
  app.post('/staff/recipes/:id', roles('admin'), async (req, res) => {
    const quantity = amount(req.body.amount, 3), variant = id(req.params.id), ingredient = id(req.body.ingredient_id);
    const basis = req.body.option_basis || 'fixed';
    requireValue(['fixed', 'sugar', 'ice'].includes(basis), 'Choose how the ingredient quantity changes with drink options.');
    if (quantity === 0) await pool.execute('DELETE FROM tf_recipes WHERE variant_id=? AND ingredient_id=?', [variant, ingredient]);
    else await pool.execute('INSERT INTO tf_recipes (variant_id,ingredient_id,amount_milli,option_basis) VALUES (?,?,?,?) ON DUPLICATE KEY UPDATE amount_milli=?,option_basis=?', [variant, ingredient, quantity, basis, quantity, basis]);
    flash(req, 'Recipe updated for newly submitted orders.'); res.redirect('/staff/products');
  });

  app.use((req, res, next) => next(new AppError('Page not found.', 404)));
  app.use((error, req, res, next) => {
    const status = error.status || (['ER_DUP_ENTRY', 'ER_NO_REFERENCED_ROW_2'].includes(error.code) ? 422 : 500);
    const message = status === 500 ? 'Something went wrong. Please try again.' : error.code === 'ER_DUP_ENTRY' ? 'That record already exists.' : error.code === 'ER_NO_REFERENCED_ROW_2' ? 'The selected record is unavailable.' : error.message;
    if (status === 500) console.error(error);
    if (req.path.startsWith('/api/')) return res.status(status).json({ message });
    res.status(status).render('error', { title: 'Please check your request', message, status });
  });
  return app;
}
