import session from 'express-session';
import { pool } from './db.js';

export class MysqlSessionStore extends session.Store {
  constructor() {
    super();
    this.timer = setInterval(() => pool.execute('DELETE FROM tf_sessions WHERE expires<=?', [Date.now()]).catch(error => console.error('Session cleanup failed:', error.code)), 15 * 60000);
    this.timer.unref();
  }
  expires(value) { return value.cookie?.expires ? new Date(value.cookie.expires).getTime() : Date.now() + 8 * 3600000; }
  get(sid, callback) {
    pool.execute('SELECT data FROM tf_sessions WHERE session_id=? AND expires>?', [sid, Date.now()])
      .then(([rows]) => callback(null, rows.length ? JSON.parse(rows[0].data) : null)).catch(callback);
  }
  set(sid, value, callback = () => {}) {
    const expires = this.expires(value), data = JSON.stringify(value);
    pool.execute('INSERT INTO tf_sessions (session_id,expires,data) VALUES (?,?,?) ON DUPLICATE KEY UPDATE expires=?,data=?', [sid, expires, data, expires, data])
      .then(() => callback(null)).catch(callback);
  }
  destroy(sid, callback = () => {}) {
    pool.execute('DELETE FROM tf_sessions WHERE session_id=?', [sid]).then(() => callback(null)).catch(callback);
  }
  touch(sid, value, callback = () => {}) {
    pool.execute('UPDATE tf_sessions SET expires=? WHERE session_id=?', [this.expires(value), sid]).then(() => callback(null)).catch(callback);
  }
  async close() { clearInterval(this.timer); }
}
