import { createApp } from './app.js';
import { config } from './config.js';
import { pool } from './db.js';

await pool.query('SELECT 1');
const app = createApp();
const server = app.listen(config.port, config.host, () => console.log(`TeaFlow for BESTBREW: http://${config.host}:${config.port}`));
async function stop() {
  server.close(async () => { await app.locals.sessionStore.close(); await pool.end(); process.exit(0); });
}
process.on('SIGINT', stop);
process.on('SIGTERM', stop);
