import { createHash, randomBytes } from 'node:crypto';
import { pool } from './db.js';
import { equalSecret, verifyPassword } from './security.js';
import { requireValue } from './errors.js';

const digest = value => createHash('sha256').update(value).digest('hex');
const sessionId = token => `device:${digest(token)}`;
const operator = user => ({ id: user.id, name: user.name, email: user.email, role: user.role });

// Reuse the expiring session table, in a separate namespace from browser sessions.
// Only a token hash is stored. Tokens are bound to this device key and the live role.
export async function deviceLogin(req, res) {
  requireValue(req.deviceRole === 'cashier', 'Sign in on the cashier terminal.', 403);
  const { email, password } = req.body;
  requireValue(typeof email === 'string' && email.trim().length > 0 && email.length <= 190
    && typeof password === 'string' && password.length > 0 && password.length <= 128, 'Enter your email and password.');
  const [[user]] = await pool.execute('SELECT * FROM tf_users WHERE email=?', [email.trim().toLowerCase()]);
  requireValue(user && await verifyPassword(password, user.password_hash), 'The email or password is incorrect.', 401);
  requireValue(['admin', 'cashier'].includes(user.role), 'This cashier terminal requires an admin or cashier account.', 403);
  const token = randomBytes(32).toString('hex');
  const expires = Date.now() + 8 * 3600000;
  await pool.execute('INSERT INTO tf_sessions (session_id,expires,data) VALUES (?,?,?)',
    [sessionId(token), expires, JSON.stringify({ userId: user.id, deviceKey: digest(req.get('X-Device-Key')) })]);
  res.json({ token, expires_in: 8 * 3600, user: operator(user) });
}

export async function optionalDeviceOperator(req, res, next) {
  if (req.deviceRole !== 'cashier') return next(); // Kitchen Serial firmware retains its device permissions.
  const token = req.get('X-Operator-Token') || '';
  // Touchscreen cashier operation uses its device key, without account login.
  // Validate a token when an older client explicitly supplies one.
  if (!token) return next();
  requireValue(/^[a-f0-9]{64}$/.test(token), 'Sign in on the cashier terminal.', 401);
  const [[row]] = await pool.execute('SELECT data FROM tf_sessions WHERE session_id=? AND expires>?', [sessionId(token), Date.now()]);
  const data = row && JSON.parse(row.data);
  requireValue(data && equalSecret(data.deviceKey, digest(req.get('X-Device-Key'))), 'Your terminal session expired. Sign in again.', 401);
  const [[user]] = await pool.execute('SELECT id,name,email,role FROM tf_users WHERE id=?', [data.userId]);
  requireValue(user && ['admin', 'cashier'].includes(user.role), 'This account no longer has cashier access.', 403);
  req.operator = user;
  next();
}

export async function deviceLogout(req, res) {
  requireValue(req.deviceRole === 'cashier', 'Sign out on the cashier terminal.', 403);
  requireValue(/^[a-f0-9]{64}$/.test(req.get('X-Operator-Token') || ''), 'No operator session was supplied.', 401);
  await pool.execute('DELETE FROM tf_sessions WHERE session_id=?', [sessionId(req.get('X-Operator-Token'))]);
  res.json({ signed_out: true });
}
