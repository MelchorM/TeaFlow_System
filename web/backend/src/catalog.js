import { pool } from './db.js';

export async function catalog() {
  const [products] = await pool.query('SELECT * FROM tf_products WHERE archived=FALSE ORDER BY id');
  const [variants] = await pool.query(`SELECT v.*, EXISTS(SELECT 1 FROM tf_recipes r WHERE r.variant_id=v.id) AS has_recipe,
    NOT EXISTS(SELECT 1 FROM tf_recipes r JOIN tf_ingredients i ON i.id=r.ingredient_id WHERE r.variant_id=v.id AND i.stock_milli<r.amount_milli) AS in_stock
    FROM tf_variants v ORDER BY id`);
  const [addons] = await pool.query('SELECT a.*, i.stock_milli>=a.amount_milli AS in_stock FROM tf_addons a JOIN tf_ingredients i ON i.id=a.ingredient_id ORDER BY a.id');
  const [ingredients] = await pool.query('SELECT * FROM tf_ingredients ORDER BY name');
  const [recipes] = await pool.query('SELECT r.*,i.name,i.unit FROM tf_recipes r JOIN tf_ingredients i ON i.id=r.ingredient_id ORDER BY r.ingredient_id');
  return {
    products: products.map(product => ({ ...product, variants: variants.filter(v => v.product_id === product.id).map(v => ({ ...v, available: !!(product.active && v.has_recipe && v.in_stock), recipes: recipes.filter(r => r.variant_id === v.id) })) })),
    addons, ingredients,
  };
}
