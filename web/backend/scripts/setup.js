import fs from 'node:fs/promises';
import path from 'node:path';
import { randomBytes } from 'node:crypto';

const webRoot = path.resolve(import.meta.dirname, '..');
const envPath = path.join(webRoot, '.env');
try { await fs.access(envPath); }
catch {
  let template = await fs.readFile(path.join(webRoot, '.env.example'), 'utf8');
  for (const name of ['SESSION_SECRET', 'CASHIER_DEVICE_KEY', 'KITCHEN_DEVICE_KEY']) template = template.replace(`${name}=\n`, `${name}=${randomBytes(32).toString('hex')}\n`);
  await fs.writeFile(envPath, template, { mode: 0o600 });
}
const { config, root } = await import('../src/config.js');
const { passwordHash } = await import('../src/security.js');
const mysql = (await import('mysql2/promise')).default;
if (!/^[a-zA-Z0-9_]+$/.test(config.database)) throw new Error('DB_NAME must contain only letters, digits, and underscores.');
const db = await mysql.createConnection(config.mysql);
try {
  const [tables] = await db.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=?', [config.database]);
  if (tables.length && !tables.some(t => t.TABLE_NAME === 'tf_meta')) throw new Error('The selected database already belongs to another application. Choose an empty DB_NAME.');
  await db.query(`CREATE DATABASE IF NOT EXISTS \`${config.database}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`);
  await db.query(`USE \`${config.database}\``);
  const schema = await fs.readFile(path.join(webRoot, 'src/schema.sql'), 'utf8');
  for (const statement of schema.split(';').map(s => s.trim()).filter(Boolean)) await db.query(statement);
  const [recipeColumns] = await db.query("SHOW COLUMNS FROM tf_recipes LIKE 'option_basis'");
  if (!recipeColumns.length) await db.query("ALTER TABLE tf_recipes ADD COLUMN option_basis ENUM('fixed','sugar','ice') NOT NULL DEFAULT 'fixed'");
  const [seeded] = await db.execute("SELECT value FROM tf_meta WHERE name='catalog_seeded'");
  if (!seeded.length) {
    await db.beginTransaction();
    try {
      const makeIngredient = async (name, stock, low) => {
        const [row] = await db.execute('INSERT INTO tf_ingredients (name,unit,stock_milli,low_milli) VALUES (?,?,?,?)', [name, name.includes('cups') ? 'pieces' : 'portions', stock, low]);
        return row.insertId;
      };
      const base = await makeIngredient('Drink base (sample)', 100000, 10000);
      const small = await makeIngredient('Small cups', 100000, 10000);
      const large = await makeIngredient('Large cups', 100000, 10000);
      const products = JSON.parse(await fs.readFile(path.join(root, 'shared/catalog/bestbrew-menu.json'), 'utf8'));
      for (const product of products) {
        const [result] = await db.execute('INSERT INTO tf_products (reference_id,name,category,image,active) VALUES (?,?,?,?,?)', [product.reference_id, product.name, product.category, product.image, product.active]);
        for (const [size, price, cup] of [['Small', product.small_cents, small], ['Large', product.large_cents, large]]) {
          const [variant] = await db.execute('INSERT INTO tf_variants (product_id,size,price_cents) VALUES (?,?,?)', [result.insertId, size, price]);
          await db.execute('INSERT INTO tf_recipes (variant_id,ingredient_id,amount_milli) VALUES (?,?,1000),(?,?,1000)', [variant.insertId, base, variant.insertId, cup]);
        }
      }
      for (const name of ['Pearl', 'Crushed Oreo', 'Crushed Graham', 'Crystal']) {
        const ingredient = await makeIngredient(`${name} (sample)`, 30000, 5000);
        await db.execute('INSERT INTO tf_addons (name,price_cents,ingredient_id,amount_milli) VALUES (?,900,?,1000)', [name, ingredient]);
      }
      await db.execute("INSERT INTO tf_meta (name,value) VALUES ('catalog_seeded','1')");
      await db.commit();
      console.log(`Seeded ${products.length} BESTBREW products, temporary topping prices, and sample recipes. No legacy order/user records were imported.`);
    } catch (error) { await db.rollback(); throw error; }
  }
  const credentials = [];
  for (const role of process.env.NODE_ENV === 'test' ? [] : ['admin', 'cashier', 'kitchen']) {
    const email = `${role}@bestbrew.local`;
    const [existing] = await db.execute('SELECT id FROM tf_users WHERE email=?', [email]);
    if (!existing.length) {
      const password = randomBytes(12).toString('base64url');
      await db.execute('INSERT INTO tf_users (name,email,password_hash,role) VALUES (?,?,?,?)', [`BESTBREW ${role}`, email, await passwordHash(password), role]);
      credentials.push(`${role}\nEmail: ${email}\nPassword: ${password}\n`);
    }
  }
  if (credentials.length) {
    await fs.mkdir(path.join(root, '.tools'), { recursive: true });
    await fs.appendFile(path.join(root, '.tools/staff-access.txt'), credentials.join('\n'), { mode: 0o600 });
    console.log('Local staff access saved to .tools/staff-access.txt. Existing accounts were not changed.');
  }
  console.log('MySQL setup complete.');
} finally { await db.end(); }
