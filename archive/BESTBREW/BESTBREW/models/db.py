import hashlib
import os
import sqlite3
import time
from datetime import datetime
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from shutil import copy2


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
SQLITE_DB_PATH = os.path.join(DATA_DIR, "bestbrew.db")
LEGACY_SQLITE_DB_PATH = os.path.join(PROJECT_ROOT, "bestbrew.db")
DEFAULT_OPENING_TIME = "08:00:00"
DEFAULT_CLOSING_TIME = "23:00:00"
MYSQL_HOST = os.getenv("BESTBREW_DB_HOST", "localhost")
MYSQL_PORT = int(os.getenv("BESTBREW_DB_PORT", "3306"))
MYSQL_USER = os.getenv("BESTBREW_DB_USER", "root")
MYSQL_PASSWORD = os.getenv("BESTBREW_DB_PASSWORD", "")
MYSQL_DATABASE = os.getenv("BESTBREW_DB_NAME", "bestbrew_db")
DEFAULT_USERS = [
    {
        "username": "admin",
        "password": "admin123",
        "role": "admin",
        "full_name": "Administrator",
    },
    {
        "username": "cashier",
        "password": "cashier123",
        "role": "cashier",
        "full_name": "Cashier",
    },
]
LAST_MYSQL_PULL_TS = 0.0


def force_sqlite_mode():
    return str(os.getenv("BESTBREW_FORCE_SQLITE", "")).strip().lower() in {"1", "true", "yes", "on"}


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)


def migrate_legacy_sqlite_location():
    ensure_data_dir()
    if os.path.exists(LEGACY_SQLITE_DB_PATH) and not os.path.exists(SQLITE_DB_PATH):
        copy2(LEGACY_SQLITE_DB_PATH, SQLITE_DB_PATH)


def get_connection():
    migrate_legacy_sqlite_location()
    ensure_data_dir()
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def write_table_backup(table_name, select_sql, backup_name):
    ensure_data_dir()
    try:
        rows = execute_query(select_sql, fetch=True)
        if not rows:
            return
        payload = {
            "table": table_name,
            "row_count": len(rows),
            "rows": rows,
        }
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        with open(backup_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=True)
    except Exception:
        pass


def backup_inventory_and_addons(tag="manual"):
    safe_tag = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(tag or "manual"))
    write_table_backup(
        "inventory",
        """
        SELECT inventory_id, inventory_name, category, unit_name, quantity_on_hand, reorder_level, last_restocked
        FROM inventory
        ORDER BY inventory_id
        """,
        f"inventory_{safe_tag}.json",
    )
    write_table_backup(
        "addons",
        """
        SELECT addon_id, addon_name, price, addon_price, is_active
        FROM addons
        ORDER BY addon_id
        """,
        f"addons_{safe_tag}.json",
    )


def execute_query(sql, params=None, fetch=False):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params or ())
        if fetch:
            result = [dict(row) for row in cursor.fetchall()]
        else:
            conn.commit()
            result = cursor.lastrowid
        return result
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def ensure_default_users_sqlite(cursor):
    for user in DEFAULT_USERS:
        cursor.execute(
            """
            INSERT OR IGNORE INTO users (username, password_hash, role, full_name, is_active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (
                user["username"],
                hash_password(user["password"]),
                user["role"],
                user["full_name"],
            ),
        )
        cursor.execute(
            """
            UPDATE users
            SET role = ?,
                is_active = 1,
                full_name = CASE
                    WHEN TRIM(COALESCE(full_name, '')) = '' THEN ?
                    ELSE full_name
                END
            WHERE username = ?
            """,
            (
                user["role"],
                user["full_name"],
                user["username"],
            ),
        )


def ensure_default_users_mysql():
    if not mysql_is_available():
        return
    conn = mysql_connection(with_database=True)
    cursor = conn.cursor()
    try:
        for user in DEFAULT_USERS:
            cursor.execute(
                """
                INSERT IGNORE INTO users (username, password_hash, role, full_name, is_active)
                VALUES (%s, %s, %s, %s, 1)
                """,
                (
                    user["username"],
                    hash_password(user["password"]),
                user["role"],
                user["full_name"],
            ),
        )
            cursor.execute(
                """
                UPDATE users
                SET role = %s,
                    is_active = 1,
                    full_name = CASE
                        WHEN TRIM(COALESCE(full_name, '')) = '' THEN %s
                        ELSE full_name
                    END
                WHERE username = %s
                """,
                (
                    user["role"],
                    user["full_name"],
                    user["username"],
                ),
            )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def mysql_connector_module():
    try:
        import mysql.connector  # type: ignore
    except Exception:
        return None
    return mysql.connector


def mysql_config(with_database=True):
    config = {
        "host": MYSQL_HOST,
        "port": MYSQL_PORT,
        "user": MYSQL_USER,
        "password": MYSQL_PASSWORD,
        "connection_timeout": 3,
        "use_pure": True,
    }
    if with_database:
        config["database"] = MYSQL_DATABASE
    return config


def mysql_connection(with_database=True):
    mysql_connector = mysql_connector_module()
    if mysql_connector is None:
        return None
    return mysql_connector.connect(**mysql_config(with_database=with_database))


def mysql_is_available():
    if force_sqlite_mode():
        return False
    try:
        conn = mysql_connection(with_database=False)
        if conn is None:
            return False
        conn.close()
        return True
    except Exception:
        return False


def mysql_table_count(table_name):
    if not mysql_is_available():
        return 0
    conn = mysql_connection(with_database=True)
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(f"SELECT COUNT(*) AS count FROM {table_name}")
        row = cursor.fetchone() or {}
        return int(row.get("count", 0) or 0)
    finally:
        cursor.close()
        conn.close()


def sqlite_resequence_inventory_ids():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT inventory_id FROM inventory ORDER BY inventory_id")
        rows = cursor.fetchall()
        expected_pairs = [(row["inventory_id"], index + 1) for index, row in enumerate(rows)]
        needs_id_resequence = not all(old_id == new_id for old_id, new_id in expected_pairs)

        if needs_id_resequence:
            for old_id, new_id in expected_pairs:
                cursor.execute(
                    "UPDATE inventory SET inventory_id = ? WHERE inventory_id = ?",
                    (-new_id, old_id),
                )
            for _, new_id in expected_pairs:
                cursor.execute(
                    "UPDATE inventory SET inventory_id = ? WHERE inventory_id = ?",
                    (new_id, -new_id),
                )
        cursor.execute(
            "UPDATE sqlite_sequence SET seq = ? WHERE name = 'inventory'",
            (len(expected_pairs),),
        )
        if cursor.rowcount == 0:
            cursor.execute(
                "INSERT OR REPLACE INTO sqlite_sequence (name, seq) VALUES ('inventory', ?)",
                (len(expected_pairs),),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def mysql_resequence_inventory_ids():
    if not mysql_is_available():
        return
    conn = mysql_connection(with_database=True)
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT inventory_id FROM inventory ORDER BY inventory_id")
        rows = cursor.fetchall()
        expected_pairs = [(row["inventory_id"], index + 1) for index, row in enumerate(rows)]
        needs_id_resequence = not all(old_id == new_id for old_id, new_id in expected_pairs)

        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        if needs_id_resequence:
            for old_id, new_id in expected_pairs:
                cursor.execute(
                    "UPDATE inventory SET inventory_id = %s WHERE inventory_id = %s",
                    (-new_id, old_id),
                )
            for _, new_id in expected_pairs:
                cursor.execute(
                    "UPDATE inventory SET inventory_id = %s WHERE inventory_id = %s",
                    (new_id, -new_id),
                )
        cursor.execute(f"ALTER TABLE inventory AUTO_INCREMENT = {max(1, len(expected_pairs) + 1)}")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
    except Exception:
        conn.rollback()
        try:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            conn.commit()
        except Exception:
            pass
        raise
    finally:
        cursor.close()
        conn.close()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, hashed):
    return hash_password(password) == hashed


def _normalize_product_record(product, index=0):
    return {
        "id": product.get("id") or product.get("product_id") or index + 1,
        "display_id": index + 1,
        "name": product.get("name") or product.get("product_name") or "New Product",
        "category": product.get("category") or product.get("category_name") or "Classic",
        "price_text": str(product.get("price_text") or product.get("min_price") or "0"),
        "desc": product.get("desc") or product.get("description") or "No description",
        "image": product.get("image", "") or "",
        "available": bool(product.get("available", product.get("is_available", True))),
    }


def _to_decimal(value):
    cleaned = str(value or "0").replace("₱", "").replace(",", "").strip()
    try:
        return Decimal(cleaned or "0")
    except InvalidOperation:
        return Decimal("0")


def _parse_price_text(price_text):
    raw = str(price_text or "0").strip()
    if "/" in raw:
        first, second = raw.split("/", 1)
        small = _to_decimal(first)
        large = _to_decimal(second)
        base = small
    else:
        base = _to_decimal(raw)
        small = base
        large = base
    return base, small, large

def validate_product_data(product_data):
    name = str((product_data or {}).get("name") or "").strip()
    category = str((product_data or {}).get("category") or "").strip()
    price_text = str((product_data or {}).get("price_text") or "").strip()

    if not name:
        raise ValueError("Product name is required.")
    if not category:
        raise ValueError("Product category is required.")
    if not price_text:
        raise ValueError("Product price is required.")

    parts = [part.strip() for part in price_text.split("/")]
    if len(parts) > 2 or any(not part for part in parts):
        raise ValueError("Product price must be in the format 99 or 99/120.")

    try:
        values = [Decimal(part.replace(",", "")) for part in parts]
    except InvalidOperation as exc:
        raise ValueError("Product price must contain valid numbers.") from exc

    if any(value <= 0 for value in values):
        raise ValueError("Product price must be greater than 0.")



def _coerce_number(value, default=0):
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_sqlite_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat(sep=" ")
        except TypeError:
            return value.isoformat()
    return value


def _current_time_text():
    return datetime.now().strftime("%H:%M:%S")


def _normalize_time_text(raw_value, fallback):
    raw = str(raw_value or fallback).strip() or fallback
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(raw, fmt).strftime("%H:%M:%S")
        except ValueError:
            continue
    return fallback


def _shop_status_for_time(current_time, opening_time, closing_time):
    current_value = _normalize_time_text(current_time, _current_time_text())
    opening_value = _normalize_time_text(opening_time, DEFAULT_OPENING_TIME)
    closing_value = _normalize_time_text(closing_time, DEFAULT_CLOSING_TIME)
    return "OPEN" if opening_value <= current_value < closing_value else "CLOSED"


def ensure_base_schema():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'admin',
                full_name TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS categories (
                category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_name TEXT NOT NULL UNIQUE,
                description TEXT,
                price_small REAL,
                price_large REAL,
                icon_emoji TEXT DEFAULT '?',
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                price REAL NOT NULL DEFAULT 0,
                price_small REAL,
                price_large REAL,
                icon_emoji TEXT DEFAULT '?',
                is_active INTEGER NOT NULL DEFAULT 1,
                description TEXT,
                image_path TEXT,
                FOREIGN KEY (category_id) REFERENCES categories(category_id)
            );

            CREATE TABLE IF NOT EXISTS inventory (
                inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                inventory_name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'General',
                unit_name TEXT NOT NULL DEFAULT 'pieces',
                quantity_on_hand INTEGER NOT NULL DEFAULT 0,
                reorder_level INTEGER NOT NULL DEFAULT 0,
                last_restocked TEXT
            );

            CREATE TABLE IF NOT EXISTS addons (
                addon_id INTEGER PRIMARY KEY AUTOINCREMENT,
                addon_name TEXT NOT NULL UNIQUE,
                price REAL,
                addon_price REAL,
                is_active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                total_amount REAL NOT NULL DEFAULT 0,
                cash_tendered REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS order_items (
                order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                size_label TEXT NOT NULL DEFAULT 'Small',
                quantity INTEGER NOT NULL DEFAULT 1,
                unit_price REAL NOT NULL DEFAULT 0,
                line_total REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            );

            CREATE TABLE IF NOT EXISTS order_item_addons (
                order_item_addon_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_item_id INTEGER NOT NULL,
                addon_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                line_total REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (order_item_id) REFERENCES order_items(order_item_id) ON DELETE CASCADE,
                FOREIGN KEY (addon_id) REFERENCES addons(addon_id)
            );

            CREATE TABLE IF NOT EXISTS daily_reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL UNIQUE,
                total_sales REAL NOT NULL DEFAULT 0,
                total_orders INTEGER NOT NULL DEFAULT 0,
                generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS product_inventory (
                product_id INTEGER NOT NULL,
                inventory_id INTEGER NOT NULL,
                quantity_required REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (product_id, inventory_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,
                FOREIGN KEY (inventory_id) REFERENCES inventory(inventory_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS shop_schedule (
                schedule_id INTEGER PRIMARY KEY,
                opening_time TEXT NOT NULL DEFAULT '08:00:00',
                closing_time TEXT NOT NULL DEFAULT '23:00:00',
                shop_status TEXT NOT NULL DEFAULT 'CLOSED',
                last_status_change TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS app_meta (
                meta_key TEXT PRIMARY KEY,
                meta_value TEXT
            );
            """
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def seed_default_data():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        ensure_default_users_sqlite(cursor)

        cursor.execute("SELECT COUNT(*) AS count FROM categories")
        if cursor.fetchone()["count"] == 0:
            categories = [
                ("Classic", "Classic milk tea products"),
                ("Fruit Tea", "Fruit tea products"),
                ("Coffee", "Coffee products"),
                ("Milkshake", "Milkshake products"),
            ]
            cursor.executemany(
                "INSERT OR IGNORE INTO categories (category_name, description, is_active) VALUES (?, ?, 1)",
                categories,
            )

        cursor.execute("SELECT COUNT(*) AS count FROM products")
        if cursor.fetchone()["count"] == 0:
            cursor.execute("SELECT category_id, category_name FROM categories")
            category_ids = {row["category_name"]: row["category_id"] for row in cursor.fetchall()}
            products = [
                (category_ids.get("Classic"), "Classic Milk Tea", 89, 89, 109, "Default house blend", "", 1),
                (category_ids.get("Fruit Tea"), "Wintermelon Tea", 79, 79, 99, "Light and refreshing", "", 1),
                (category_ids.get("Coffee"), "Iced Coffee", 95, 95, 115, "Cold brewed coffee", "", 1),
                (category_ids.get("Milkshake"), "Taro Milkshake", 99, 99, 119, "Creamy taro shake", "", 1),
            ]
            cursor.executemany(
                """
                INSERT INTO products (
                    category_id, product_name, price, price_small, price_large,
                    description, image_path, is_active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                products,
            )

        cursor.execute("SELECT COUNT(*) AS count FROM inventory")
        if cursor.fetchone()["count"] == 0:
            inventory_items = [
                ("Black Tea Leaves", "Tea Base", "kg", 15, 10),
                ("Fresh Milk", "Dairy", "liters", 8, 5),
                ("Tapioca Pearls", "Add-on", "kg", 6, 3),
                ("Taro Powder", "Flavoring", "kg", 4, 2),
                ("Coffee Beans", "Coffee", "kg", 5, 2),
            ]
            cursor.executemany(
                """
                INSERT INTO inventory (
                    inventory_name, category, unit_name, quantity_on_hand, reorder_level, last_restocked
                )
                VALUES (?, ?, ?, ?, ?, date('now', 'localtime'))
                """,
                inventory_items,
            )

        cursor.execute("SELECT COUNT(*) AS count FROM addons")
        if cursor.fetchone()["count"] == 0:
            addons = [
                ("Pearls", 15, 15, 1),
                ("Pudding", 15, 15, 1),
                ("Jelly", 15, 15, 1),
                ("Cream Cheese", 15, 15, 1),
            ]
            cursor.executemany(
                "INSERT OR IGNORE INTO addons (addon_name, price, addon_price, is_active) VALUES (?, ?, ?, ?)",
                addons,
            )

        cursor.execute("SELECT COUNT(*) AS count FROM shop_schedule")
        if cursor.fetchone()["count"] == 0:
            current_time = _current_time_text()
            status = "OPEN" if DEFAULT_OPENING_TIME <= current_time < DEFAULT_CLOSING_TIME else "CLOSED"
            cursor.execute(
                """
                INSERT INTO shop_schedule (
                    schedule_id, opening_time, closing_time, shop_status, last_status_change, updated_at
                )
                VALUES (1, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))
                """,
                (DEFAULT_OPENING_TIME, DEFAULT_CLOSING_TIME, status),
            )

        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def ensure_mysql_schema():
    if not mysql_is_available():
        return

    server_conn = mysql_connection(with_database=False)
    server_cursor = server_conn.cursor()
    try:
        server_cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        server_conn.commit()
    finally:
        server_cursor.close()
        server_conn.close()

    mysql_conn = mysql_connection(with_database=True)
    mysql_cursor = mysql_conn.cursor()
    try:
        for statement in [
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INT PRIMARY KEY AUTO_INCREMENT,
                username VARCHAR(100) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(40) NOT NULL DEFAULT 'admin',
                full_name VARCHAR(255) NOT NULL DEFAULT '',
                is_active TINYINT(1) NOT NULL DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS categories (
                category_id INT PRIMARY KEY AUTO_INCREMENT,
                category_name VARCHAR(150) NOT NULL UNIQUE,
                description TEXT,
                price_small DECIMAL(10,2) NULL,
                price_large DECIMAL(10,2) NULL,
                icon_emoji VARCHAR(20) DEFAULT '?',
                is_active TINYINT(1) NOT NULL DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS products (
                product_id INT PRIMARY KEY AUTO_INCREMENT,
                category_id INT NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                price DECIMAL(10,2) NOT NULL DEFAULT 0,
                price_small DECIMAL(10,2) NULL,
                price_large DECIMAL(10,2) NULL,
                icon_emoji VARCHAR(20) DEFAULT '?',
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                description TEXT,
                image_path TEXT,
                CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES categories(category_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS inventory (
                inventory_id INT PRIMARY KEY AUTO_INCREMENT,
                inventory_name VARCHAR(255) NOT NULL,
                category VARCHAR(150) NOT NULL DEFAULT 'General',
                unit_name VARCHAR(80) NOT NULL DEFAULT 'pieces',
                quantity_on_hand INT NOT NULL DEFAULT 0,
                reorder_level INT NOT NULL DEFAULT 0,
                last_restocked DATETIME NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS addons (
                addon_id INT PRIMARY KEY AUTO_INCREMENT,
                addon_name VARCHAR(150) NOT NULL UNIQUE,
                price DECIMAL(10,2) NULL,
                addon_price DECIMAL(10,2) NULL,
                is_active TINYINT(1) NOT NULL DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id INT PRIMARY KEY AUTO_INCREMENT,
                user_id INT NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'Pending',
                total_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
                cash_tendered DECIMAL(10,2) NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS order_items (
                order_item_id INT PRIMARY KEY AUTO_INCREMENT,
                order_id INT NOT NULL,
                product_id INT NOT NULL,
                size_label VARCHAR(20) NOT NULL DEFAULT 'Small',
                quantity INT NOT NULL DEFAULT 1,
                unit_price DECIMAL(10,2) NOT NULL DEFAULT 0,
                line_total DECIMAL(10,2) NOT NULL DEFAULT 0,
                CONSTRAINT fk_order_items_order FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
                CONSTRAINT fk_order_items_product FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS order_item_addons (
                order_item_addon_id INT PRIMARY KEY AUTO_INCREMENT,
                order_item_id INT NOT NULL,
                addon_id INT NOT NULL,
                quantity INT NOT NULL DEFAULT 1,
                line_total DECIMAL(10,2) NOT NULL DEFAULT 0,
                CONSTRAINT fk_order_item_addons_item FOREIGN KEY (order_item_id) REFERENCES order_items(order_item_id) ON DELETE CASCADE,
                CONSTRAINT fk_order_item_addons_addon FOREIGN KEY (addon_id) REFERENCES addons(addon_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS daily_reports (
                report_id INT PRIMARY KEY AUTO_INCREMENT,
                report_date DATE NOT NULL UNIQUE,
                total_sales DECIMAL(10,2) NOT NULL DEFAULT 0,
                total_orders INT NOT NULL DEFAULT 0,
                generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS product_inventory (
                product_id INT NOT NULL,
                inventory_id INT NOT NULL,
                quantity_required DECIMAL(10,3) NOT NULL DEFAULT 0,
                PRIMARY KEY (product_id, inventory_id),
                CONSTRAINT fk_product_inventory_product FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,
                CONSTRAINT fk_product_inventory_inventory FOREIGN KEY (inventory_id) REFERENCES inventory(inventory_id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS shop_schedule (
                schedule_id INT PRIMARY KEY,
                opening_time TIME NOT NULL DEFAULT '08:00:00',
                closing_time TIME NOT NULL DEFAULT '23:00:00',
                shop_status VARCHAR(30) NOT NULL DEFAULT 'CLOSED',
                last_status_change DATETIME NULL,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
        ]:
            mysql_cursor.execute(statement)
        mysql_cursor.execute("SHOW COLUMNS FROM users LIKE 'role'")
        role_column = mysql_cursor.fetchone()
        role_type = str(role_column[1] if role_column and len(role_column) > 1 else "").lower()
        if "enum(" in role_type and "cashier" not in role_type:
            mysql_cursor.execute(
                "ALTER TABLE users MODIFY COLUMN role ENUM('admin','cashier','customer') NOT NULL DEFAULT 'admin'"
            )
        mysql_cursor.execute("SHOW COLUMNS FROM addons")
        addon_columns = {row[0] for row in mysql_cursor.fetchall()}
        if "price" not in addon_columns:
            mysql_cursor.execute("ALTER TABLE addons ADD COLUMN price DECIMAL(10,2) NULL")
        if "addon_price" not in addon_columns:
            mysql_cursor.execute("ALTER TABLE addons ADD COLUMN addon_price DECIMAL(10,2) NULL")
        mysql_conn.commit()
    finally:
        mysql_cursor.close()
        mysql_conn.close()


def sync_mysql_to_sqlite():
    if not mysql_is_available():
        return

    ensure_mysql_schema()
    mysql_resequence_inventory_ids()
    mysql_conn = mysql_connection(with_database=True)
    mysql_cursor = mysql_conn.cursor(dictionary=True)
    sqlite_conn = get_connection()
    sqlite_cursor = sqlite_conn.cursor()

    try:
        backup_inventory_and_addons("before_mysql_pull")
        sqlite_cursor.execute("PRAGMA foreign_keys = OFF")
        mysql_cursor.execute("SELECT COUNT(*) AS count FROM users")
        if int(mysql_cursor.fetchone()["count"] or 0) <= 0:
            sqlite_cursor.execute("PRAGMA foreign_keys = ON")
            return

        table_sync_plan = [
            (
                "users",
                "SELECT user_id, username, password_hash, role, full_name, is_active FROM users ORDER BY user_id",
                "INSERT INTO users (user_id, username, password_hash, role, full_name, is_active) VALUES (?, ?, ?, ?, ?, ?)",
            ),
            (
                "categories",
                "SELECT category_id, category_name, description, price_small, price_large, icon_emoji, is_active FROM categories ORDER BY category_id",
                "INSERT INTO categories (category_id, category_name, description, price_small, price_large, icon_emoji, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ),
            (
                "products",
                "SELECT product_id, category_id, product_name, price, price_small, price_large, icon_emoji, is_active, description, image_path FROM products ORDER BY product_id",
                "INSERT INTO products (product_id, category_id, product_name, price, price_small, price_large, icon_emoji, is_active, description, image_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ),
            (
                "inventory",
                "SELECT inventory_id, inventory_name, category, unit_name, quantity_on_hand, reorder_level, last_restocked FROM inventory ORDER BY inventory_id",
                "INSERT INTO inventory (inventory_id, inventory_name, category, unit_name, quantity_on_hand, reorder_level, last_restocked) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ),
            (
                "orders",
                "SELECT order_id, user_id, status, total_amount, cash_tendered, created_at FROM orders ORDER BY order_id",
                "INSERT INTO orders (order_id, user_id, status, total_amount, cash_tendered, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ),
            (
                "order_items",
                "SELECT order_item_id, order_id, product_id, size_label, quantity, unit_price, line_total FROM order_items ORDER BY order_item_id",
                "INSERT INTO order_items (order_item_id, order_id, product_id, size_label, quantity, unit_price, line_total) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ),
            (
                "order_item_addons",
                "SELECT order_item_addon_id, order_item_id, addon_id, quantity, line_total FROM order_item_addons ORDER BY order_item_addon_id",
                "INSERT INTO order_item_addons (order_item_addon_id, order_item_id, addon_id, quantity, line_total) VALUES (?, ?, ?, ?, ?)",
            ),
            (
                "daily_reports",
                "SELECT report_id, report_date, total_sales, total_orders, generated_at FROM daily_reports ORDER BY report_id",
                "INSERT INTO daily_reports (report_id, report_date, total_sales, total_orders, generated_at) VALUES (?, ?, ?, ?, ?)",
            ),
            (
                "product_inventory",
                "SELECT product_id, inventory_id, quantity_required FROM product_inventory ORDER BY product_id, inventory_id",
                "INSERT INTO product_inventory (product_id, inventory_id, quantity_required) VALUES (?, ?, ?)",
            ),
            (
                "shop_schedule",
                "SELECT schedule_id, opening_time, closing_time, shop_status, last_status_change, updated_at FROM shop_schedule ORDER BY schedule_id",
                "INSERT INTO shop_schedule (schedule_id, opening_time, closing_time, shop_status, last_status_change, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ),
        ]

        for table_name, query, insert_sql in table_sync_plan:
            mysql_cursor.execute(f"SELECT COUNT(*) AS count FROM {table_name}")
            table_count = int((mysql_cursor.fetchone() or {}).get("count", 0) or 0)
            if table_count <= 0:
                continue
            sqlite_cursor.execute(f"DELETE FROM {table_name}")
            mysql_cursor.execute(query)
            for row in mysql_cursor.fetchall():
                sqlite_cursor.execute(
                    insert_sql,
                    tuple(normalize_sqlite_value(value) for value in row.values()),
                )

        mysql_cursor.execute("SELECT COUNT(*) AS count FROM addons")
        addon_count = int((mysql_cursor.fetchone() or {}).get("count", 0) or 0)
        if addon_count > 0:
            sqlite_cursor.execute("DELETE FROM addons")
            addon_queries = [
                "SELECT addon_id, addon_name, price, addon_price, is_active FROM addons ORDER BY addon_id",
                "SELECT addon_id, addon_name, price, price AS addon_price, is_active FROM addons ORDER BY addon_id",
                "SELECT addon_id, addon_name, addon_price AS price, addon_price, is_active FROM addons ORDER BY addon_id",
            ]
            for addon_query in addon_queries:
                try:
                    mysql_cursor.execute(addon_query)
                    for row in mysql_cursor.fetchall():
                        sqlite_cursor.execute(
                            "INSERT INTO addons (addon_id, addon_name, price, addon_price, is_active) VALUES (?, ?, ?, ?, ?)",
                            tuple(normalize_sqlite_value(value) for value in row.values()),
                        )
                    break
                except Exception:
                    continue

        sqlite_conn.commit()
        sqlite_cursor.execute("PRAGMA foreign_keys = ON")
    finally:
        mysql_cursor.close()
        mysql_conn.close()
        sqlite_cursor.close()
        sqlite_conn.close()


def sync_sqlite_to_mysql():
    if not mysql_is_available():
        return

    ensure_mysql_schema()
    sqlite_resequence_inventory_ids()
    mysql_conn = mysql_connection(with_database=True)
    mysql_cursor = mysql_conn.cursor()
    sqlite_conn = get_connection()
    sqlite_cursor = sqlite_conn.cursor()

    try:
        backup_inventory_and_addons("before_mysql_push")
        mysql_cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        for table_name in ["order_item_addons", "order_items", "orders", "product_inventory", "daily_reports", "users", "products", "categories", "inventory", "addons", "shop_schedule"]:
            mysql_cursor.execute(f"DELETE FROM {table_name}")
        mysql_cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

        copy_plan = [
            ("SELECT user_id, username, password_hash, role, full_name, is_active FROM users ORDER BY user_id", "INSERT INTO users (user_id, username, password_hash, role, full_name, is_active) VALUES (%s, %s, %s, %s, %s, %s)"),
            ("SELECT category_id, category_name, description, price_small, price_large, icon_emoji, is_active FROM categories ORDER BY category_id", "INSERT INTO categories (category_id, category_name, description, price_small, price_large, icon_emoji, is_active) VALUES (%s, %s, %s, %s, %s, %s, %s)"),
            ("SELECT product_id, category_id, product_name, price, price_small, price_large, icon_emoji, is_active, description, image_path FROM products ORDER BY product_id", "INSERT INTO products (product_id, category_id, product_name, price, price_small, price_large, icon_emoji, is_active, description, image_path) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"),
            ("SELECT inventory_id, inventory_name, category, unit_name, quantity_on_hand, reorder_level, last_restocked FROM inventory ORDER BY inventory_id", "INSERT INTO inventory (inventory_id, inventory_name, category, unit_name, quantity_on_hand, reorder_level, last_restocked) VALUES (%s, %s, %s, %s, %s, %s, %s)"),
            ("SELECT addon_id, addon_name, price, addon_price, is_active FROM addons ORDER BY addon_id", "INSERT INTO addons (addon_id, addon_name, price, addon_price, is_active) VALUES (%s, %s, %s, %s, %s)"),
            ("SELECT order_id, user_id, status, total_amount, cash_tendered, created_at FROM orders ORDER BY order_id", "INSERT INTO orders (order_id, user_id, status, total_amount, cash_tendered, created_at) VALUES (%s, %s, %s, %s, %s, %s)"),
            ("SELECT order_item_id, order_id, product_id, size_label, quantity, unit_price, line_total FROM order_items ORDER BY order_item_id", "INSERT INTO order_items (order_item_id, order_id, product_id, size_label, quantity, unit_price, line_total) VALUES (%s, %s, %s, %s, %s, %s, %s)"),
            ("SELECT order_item_addon_id, order_item_id, addon_id, quantity, line_total FROM order_item_addons ORDER BY order_item_addon_id", "INSERT INTO order_item_addons (order_item_addon_id, order_item_id, addon_id, quantity, line_total) VALUES (%s, %s, %s, %s, %s)"),
            ("SELECT report_id, report_date, total_sales, total_orders, generated_at FROM daily_reports ORDER BY report_id", "INSERT INTO daily_reports (report_id, report_date, total_sales, total_orders, generated_at) VALUES (%s, %s, %s, %s, %s)"),
            ("SELECT product_id, inventory_id, quantity_required FROM product_inventory ORDER BY product_id, inventory_id", "INSERT INTO product_inventory (product_id, inventory_id, quantity_required) VALUES (%s, %s, %s)"),
            ("SELECT schedule_id, opening_time, closing_time, shop_status, last_status_change, updated_at FROM shop_schedule ORDER BY schedule_id", "INSERT INTO shop_schedule (schedule_id, opening_time, closing_time, shop_status, last_status_change, updated_at) VALUES (%s, %s, %s, %s, %s, %s)"),
        ]

        for select_sql, insert_sql in copy_plan:
            sqlite_cursor.execute(select_sql)
            for row in sqlite_cursor.fetchall():
                mysql_cursor.execute(insert_sql, tuple(row))

        mysql_conn.commit()
    finally:
        mysql_cursor.close()
        mysql_conn.close()
        sqlite_cursor.close()
        sqlite_conn.close()


def sync_from_mysql_if_due(force=False, min_interval_seconds=3.0):
    global LAST_MYSQL_PULL_TS
    if not mysql_is_available():
        return False

    now = time.monotonic()
    if not force and (now - LAST_MYSQL_PULL_TS) < float(min_interval_seconds):
        return False

    sync_mysql_to_sqlite()
    LAST_MYSQL_PULL_TS = now
    return True


def initialize_database():
    ensure_base_schema()
    seed_default_data()
    if mysql_is_available():
        ensure_mysql_schema()
        ensure_mysql_reporting_objects()
        if mysql_table_count("users") <= 0:
            sync_sqlite_to_mysql()
        else:
            sync_mysql_to_sqlite()
        ensure_default_users_mysql()
        sync_mysql_to_sqlite()

    conn = get_connection()
    cursor = conn.cursor()
    try:
        ensure_default_users_sqlite(cursor)
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def authenticate_admin(username, password):
    initialize_database()
    sync_from_mysql_if_due()
    rows = execute_query(
        """
        SELECT user_id, username, password_hash, role, full_name, is_active
        FROM users
        WHERE username = ? AND role = 'admin'
        LIMIT 1
        """,
        (username,),
        fetch=True,
    )

    if not rows:
        return None

    user = rows[0]
    if int(user["is_active"]) != 1:
        return None
    if verify_password(password, user["password_hash"]):
        return user
    return None


def authenticate(username, password):
    initialize_database()
    sync_from_mysql_if_due()
    rows = execute_query(
        """
        SELECT user_id, username, password_hash, role, full_name, is_active
        FROM users
        WHERE username = ?
        LIMIT 1
        """,
        (username,),
        fetch=True,
    )

    if not rows:
        return None

    user = rows[0]
    if int(user["is_active"]) != 1:
        return None
    if verify_password(password, user["password_hash"]):
        return user
    return None


def get_user_by_username(username):
    initialize_database()
    sync_from_mysql_if_due()
    rows = execute_query(
        """
        SELECT user_id, username, password_hash, role, full_name, is_active
        FROM users
        WHERE username = ?
        LIMIT 1
        """,
        (str(username or "").strip(),),
        fetch=True,
    )
    return rows[0] if rows else None


def reset_user_password(username, new_password):
    initialize_database()
    clean_username = str(username or "").strip()
    clean_password = str(new_password or "").strip()
    if not clean_username:
        raise ValueError("Username is required.")
    if not clean_password:
        raise ValueError("New password is required.")

    rows = execute_query(
        """
        SELECT user_id, username
        FROM users
        WHERE username = ?
        LIMIT 1
        """,
        (clean_username,),
        fetch=True,
    )
    if not rows:
        raise ValueError("Username not found.")

    execute_query(
        """
        UPDATE users
        SET password_hash = ?
        WHERE username = ?
        """,
        (hash_password(clean_password), clean_username),
    )
    sync_sqlite_to_mysql()
    return get_user_by_username(clean_username)


def get_users():
    initialize_database()
    sync_from_mysql_if_due()
    return execute_query(
        """
        SELECT user_id, username, role, full_name, is_active
        FROM users
        ORDER BY user_id
        """,
        fetch=True,
    )


def update_user_profile(user_id, full_name=None, role=None, is_active=None):
    initialize_database()
    existing_rows = execute_query(
        """
        SELECT user_id, username, role, full_name, is_active
        FROM users
        WHERE user_id = ?
        LIMIT 1
        """,
        (int(user_id),),
        fetch=True,
    )
    if not existing_rows:
        raise ValueError("User not found.")

    existing = existing_rows[0]
    next_full_name = str(full_name if full_name is not None else existing.get("full_name", "")).strip()
    next_role = str(role if role is not None else existing.get("role", "admin")).strip().lower() or "admin"
    next_is_active = 1 if bool(existing.get("is_active", 1) if is_active is None else is_active) else 0

    if next_role not in {"admin", "cashier", "customer"}:
        raise ValueError("Invalid role selected.")
    if not next_full_name:
        raise ValueError("Full name is required.")

    execute_query(
        """
        UPDATE users
        SET full_name = ?,
            role = ?,
            is_active = ?
        WHERE user_id = ?
        """,
        (next_full_name, next_role, next_is_active, int(user_id)),
    )
    sync_sqlite_to_mysql()
    return get_user_by_username(existing.get("username"))


def ensure_product_storage_schema():
    initialize_database()


def ensure_shop_schedule_schema():
    initialize_database()
    rows = execute_query(
        """
        SELECT opening_time, closing_time, shop_status
        FROM shop_schedule
        WHERE schedule_id = 1
        LIMIT 1
        """,
        fetch=True,
    )
    if not rows:
        execute_query(
            """
            INSERT INTO shop_schedule (
                schedule_id, opening_time, closing_time, shop_status, last_status_change, updated_at
            )
            VALUES (1, ?, ?, 'CLOSED', datetime('now', 'localtime'), datetime('now', 'localtime'))
            """,
            (DEFAULT_OPENING_TIME, DEFAULT_CLOSING_TIME),
        )
        rows = execute_query(
            """
            SELECT opening_time, closing_time, shop_status
            FROM shop_schedule
            WHERE schedule_id = 1
            LIMIT 1
            """,
            fetch=True,
        )
    schedule = rows[0] if rows else {}
    current_time = _current_time_text()
    opening_time = schedule.get("opening_time", DEFAULT_OPENING_TIME)
    closing_time = schedule.get("closing_time", DEFAULT_CLOSING_TIME)
    status = _shop_status_for_time(current_time, opening_time, closing_time)
    execute_query(
        """
        UPDATE shop_schedule
        SET shop_status = ?,
            last_status_change = CASE
                WHEN COALESCE(shop_status, '') <> ? THEN datetime('now', 'localtime')
                ELSE last_status_change
            END,
            updated_at = datetime('now', 'localtime')
        WHERE schedule_id = 1
        """,
        (status, status),
    )
    sync_sqlite_to_mysql()


def get_shop_schedule():
    ensure_shop_schedule_schema()
    sync_from_mysql_if_due()
    rows = execute_query(
        """
        SELECT
            schedule_id,
            opening_time,
            closing_time,
            shop_status,
            last_status_change,
            updated_at
        FROM shop_schedule
        WHERE schedule_id = 1
        LIMIT 1
        """,
        fetch=True,
    )
    return rows[0] if rows else {}


def get_or_create_category(category_name):
    ensure_product_storage_schema()
    category_name = (category_name or "Classic").strip() or "Classic"

    rows = execute_query(
        "SELECT category_id FROM categories WHERE category_name = ? LIMIT 1",
        (category_name,),
        fetch=True,
    )
    if rows:
        return rows[0]["category_id"]

    return execute_query(
        """
        INSERT INTO categories (category_name, description, is_active)
        VALUES (?, ?, 1)
        """,
        (category_name, f"{category_name} products"),
    )


def create_product(product_data):
    ensure_product_storage_schema()
    validate_product_data(product_data)
    category_id = get_or_create_category(product_data.get("category"))
    base_price, small_price, large_price = _parse_price_text(product_data.get("price_text"))

    result = execute_query(
        """
        INSERT INTO products (
            category_id, product_name, price, price_small, price_large,
            icon_emoji, is_active, description, image_path
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            category_id,
            str(product_data.get("name") or "").strip(),
            float(base_price),
            float(small_price),
            float(large_price),
            product_data.get("icon_emoji") or "?",
            1 if product_data.get("available", True) else 0,
            product_data.get("desc") or "No description",
            product_data.get("image") or "",
        ),
    )
    sync_sqlite_to_mysql()
    return result


def update_product(product_id, product_data):
    ensure_product_storage_schema()
    category_id = get_or_create_category(product_data.get("category"))
    base_price, small_price, large_price = _parse_price_text(product_data.get("price_text"))

    execute_query(
        """
        UPDATE products
        SET category_id = ?,
            product_name = ?,
            price = ?,
            price_small = ?,
            price_large = ?,
            is_active = ?,
            description = ?,
            image_path = ?
        WHERE product_id = ?
        """,
        (
            category_id,
            str(product_data.get("name") or "").strip(),
            float(base_price),
            float(small_price),
            float(large_price),
            1 if product_data.get("available", True) else 0,
            product_data.get("desc") or "No description",
            product_data.get("image") or "",
            int(product_id),
        ),
    )
    sync_sqlite_to_mysql()


def delete_product(product_id):
    initialize_database()
    execute_query("DELETE FROM products WHERE product_id = ?", (int(product_id),))
    sync_sqlite_to_mysql()


def get_products():
    ensure_product_storage_schema()
    sync_from_mysql_if_due()
    rows = execute_query(
        """
        SELECT
            p.product_id,
            p.product_name,
            c.category_name,
            COALESCE(p.description, '') AS description,
            COALESCE(p.image_path, '') AS image_path,
            p.is_active,
            p.price,
            p.price_small,
            p.price_large
        FROM products p
        JOIN categories c ON c.category_id = p.category_id
        WHERE p.is_active IN (0, 1)
        ORDER BY c.category_name, p.product_name
        """,
        fetch=True,
    )
    products = []
    for index, row in enumerate(rows):
        small_price = row.get("price_small")
        large_price = row.get("price_large")
        base_price = row.get("price")

        if small_price is not None and large_price is not None and Decimal(str(small_price)) != Decimal(str(large_price)):
            price_text = f"{int(Decimal(str(small_price)))}/{int(Decimal(str(large_price)))}"
        else:
            chosen_price = small_price if small_price is not None else base_price
            price_text = str(int(Decimal(str(chosen_price or 0))))

        products.append(
            _normalize_product_record(
                {
                    "id": row.get("product_id"),
                    "name": row.get("product_name", ""),
                    "category": row.get("category_name", ""),
                    "price_text": price_text,
                    "desc": row.get("description", "") or "No description",
                    "image": row.get("image_path", "") or "",
                    "available": int(row.get("is_active", 1)) == 1,
                },
                index,
            )
        )

    return products


def get_inventory_items():
    initialize_database()
    sync_from_mysql_if_due()
    return execute_query(
        """
        SELECT
            inventory_id,
            inventory_name AS item_name,
            category,
            unit_name AS unit,
            quantity_on_hand AS current_stock,
            reorder_level,
            last_restocked,
            CASE
                WHEN quantity_on_hand <= 0 THEN 'Out'
                WHEN quantity_on_hand <= reorder_level THEN 'Low'
                ELSE 'Good'
            END AS status
        FROM inventory
        ORDER BY LOWER(inventory_name), LOWER(category)
        """,
        fetch=True,
    )


def get_addons():
    initialize_database()
    sync_from_mysql_if_due()
    return execute_query(
        """
        SELECT
            addon_id AS id,
            addon_name AS name,
            COALESCE(price, addon_price, 0) AS price
        FROM addons
        WHERE is_active IN (1) OR is_active IS NULL
        ORDER BY addon_name
        """,
        fetch=True,
    )


def restock_item(inventory_id, quantity):
    initialize_database()
    backup_inventory_and_addons("before_restock")
    execute_query(
        """
        UPDATE inventory
        SET quantity_on_hand = quantity_on_hand + ?,
            last_restocked = date('now', 'localtime')
        WHERE inventory_id = ?
        """,
        (int(quantity), int(inventory_id)),
    )
    sync_sqlite_to_mysql()


def restock_inventory_item(inventory_id, quantity):
    restock_item(inventory_id, quantity)


def consume_inventory_item(inventory_id, quantity):
    initialize_database()
    backup_inventory_and_addons("before_consume")
    execute_query(
        """
        UPDATE inventory
        SET quantity_on_hand = MAX(quantity_on_hand - ?, 0)
        WHERE inventory_id = ?
        """,
        (int(quantity), int(inventory_id)),
    )
    sync_sqlite_to_mysql()


def create_inventory_item(item_data):
    initialize_database()
    backup_inventory_and_addons("before_add_inventory")
    result = execute_query(
        """
        INSERT INTO inventory (
            inventory_name, category, unit_name, quantity_on_hand, reorder_level, last_restocked
        )
        VALUES (?, ?, ?, ?, ?, date('now', 'localtime'))
        """,
        (
            (item_data.get("name") or "New Inventory Item").strip(),
            (item_data.get("category") or "General").strip(),
            (item_data.get("unit") or "pieces").strip(),
            int(item_data.get("quantity_on_hand", 0) or 0),
            int(item_data.get("reorder_level", 0) or 0),
        ),
    )
    sync_sqlite_to_mysql()
    return result


def get_dashboard_counts():
    initialize_database()
    sync_from_mysql_if_due()
    rows = execute_query(
        """
        SELECT
            (SELECT COUNT(*) FROM products) AS total_products,
            0 AS today_orders,
            0 AS total_revenue,
            (SELECT COUNT(*) FROM inventory WHERE quantity_on_hand <= reorder_level) AS low_stock_items
        """,
        fetch=True,
    )
    return rows[0] if rows else {}


def refresh_daily_reports():
    initialize_database()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM daily_reports")
        cursor.execute(
            """
            INSERT INTO daily_reports (report_date, total_sales, total_orders, generated_at)
            SELECT
                date(created_at) AS report_date,
                COALESCE(SUM(total_amount), 0) AS total_sales,
                COUNT(*) AS total_orders,
                datetime('now', 'localtime') AS generated_at
            FROM orders
            WHERE lower(COALESCE(status, '')) = 'completed'
            GROUP BY date(created_at)
            """
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def ensure_mysql_reporting_objects():
    if not mysql_is_available():
        return

    conn = mysql_connection(with_database=True)
    cursor = conn.cursor()
    try:
        statements = [
            "DROP VIEW IF EXISTS view_daily_sales",
            "DROP VIEW IF EXISTS view_order_details",
            "DROP PROCEDURE IF EXISTS sp_complete_order",
            "DROP PROCEDURE IF EXISTS sp_refresh_daily_report",
            "DROP FUNCTION IF EXISTS fn_format_order_code",
            """
            CREATE FUNCTION fn_format_order_code(p_order_id INT)
            RETURNS VARCHAR(20)
            DETERMINISTIC
            BEGIN
                RETURN CONCAT('BB-', LPAD(p_order_id, 6, '0'));
            END
            """,
            """
            CREATE PROCEDURE sp_complete_order(IN p_order_id INT)
            BEGIN
                DECLARE v_report_date DATE;

                UPDATE orders
                SET status = 'Completed'
                WHERE order_id = p_order_id
                  AND status <> 'Cancelled';

                SELECT DATE(created_at)
                  INTO v_report_date
                FROM orders
                WHERE order_id = p_order_id
                LIMIT 1;

                IF v_report_date IS NOT NULL THEN
                    INSERT INTO daily_reports (report_date, total_sales, total_orders)
                    SELECT
                        v_report_date,
                        COALESCE(SUM(total_amount), 0),
                        COUNT(*)
                    FROM orders
                    WHERE DATE(created_at) = v_report_date
                      AND status = 'Completed'
                    ON DUPLICATE KEY UPDATE
                        total_sales = VALUES(total_sales),
                        total_orders = VALUES(total_orders),
                        generated_at = CURRENT_TIMESTAMP;
                END IF;

                SELECT
                    o.order_id,
                    fn_format_order_code(o.order_id) AS order_code,
                    COALESCE(u.full_name, u.username, 'Walk-in Customer') AS full_name,
                    COALESCE(c.category_name, 'Uncategorized') AS category_name,
                    COALESCE(p.product_name, 'No Product') AS product_name,
                    oi.size_label,
                    COALESCE(oi.quantity, 0) AS quantity,
                    COALESCE(oi.unit_price, 0.00) AS unit_price,
                    COALESCE(oi.line_total, 0.00) AS line_total,
                    o.status,
                    o.created_at
                FROM orders o
                LEFT JOIN users u ON u.user_id = o.user_id
                LEFT JOIN order_items oi ON oi.order_id = o.order_id
                LEFT JOIN products p ON p.product_id = oi.product_id
                LEFT JOIN categories c ON c.category_id = p.category_id
                WHERE o.order_id = p_order_id;
            END
            """,
            """
            CREATE PROCEDURE sp_refresh_daily_report()
            BEGIN
                INSERT INTO daily_reports (report_date, total_sales, total_orders)
                SELECT
                    src.sales_date,
                    ROUND(SUM(src.total_sales), 2) AS total_sales,
                    SUM(src.total_orders) AS total_orders
                FROM (
                    SELECT DATE(created_at) AS sales_date, total_amount AS total_sales, 1 AS total_orders
                    FROM orders
                    WHERE status = 'Completed'
                    UNION ALL
                    SELECT CURDATE() AS sales_date, 0.00 AS total_sales, 0 AS total_orders
                ) AS src
                GROUP BY src.sales_date
                ON DUPLICATE KEY UPDATE
                    total_sales = VALUES(total_sales),
                    total_orders = VALUES(total_orders),
                    generated_at = CURRENT_TIMESTAMP;

                SELECT
                    report_date AS sales_date,
                    total_orders,
                    total_sales,
                    CASE
                        WHEN total_orders = 0 THEN 0.00
                        ELSE ROUND(total_sales / total_orders, 2)
                    END AS avg_order_value
                FROM daily_reports
                ORDER BY report_date DESC;
            END
            """,
            """
            CREATE VIEW view_daily_sales AS
            SELECT
                daily_reports.report_date AS sales_date,
                daily_reports.total_orders AS total_orders,
                daily_reports.total_sales AS total_sales,
                CASE
                    WHEN daily_reports.total_orders = 0 THEN 0.00
                    ELSE ROUND(daily_reports.total_sales / daily_reports.total_orders, 2)
                END AS avg_order_value
            FROM daily_reports
            """,
            """
            CREATE VIEW view_order_details AS
            SELECT
                o.order_id AS order_id,
                fn_format_order_code(o.order_id) AS order_code,
                COALESCE(u.full_name, u.username, 'Walk-in Customer') AS full_name,
                COALESCE(c.category_name, 'Uncategorized') AS category_name,
                COALESCE(p.product_name, 'No Product') AS product_name,
                oi.size_label AS size_label,
                COALESCE(oi.quantity, 0) AS quantity,
                COALESCE(oi.unit_price, 0.00) AS unit_price,
                COALESCE(oi.line_total, 0.00) AS line_total,
                o.status AS status,
                o.created_at AS created_at
            FROM orders o
            LEFT JOIN users u ON u.user_id = o.user_id
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            LEFT JOIN products p ON p.product_id = oi.product_id
            LEFT JOIN categories c ON c.category_id = p.category_id
            """,
        ]
        for statement in statements:
            cursor.execute(statement)
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    sync_sqlite_to_mysql()

    if mysql_is_available():
        mysql_conn = mysql_connection(with_database=True)
        mysql_cursor = mysql_conn.cursor()
        try:
            mysql_cursor.execute("CALL sp_refresh_daily_report()")
            while mysql_cursor.nextset():
                pass
            mysql_conn.commit()
        except Exception:
            mysql_conn.rollback()
        finally:
            mysql_cursor.close()
            mysql_conn.close()


def create_order_record(user_id, product_id, quantity, size_label, unit_price, total_amount, cash_tendered=0, addon_items=None, status="Pending", created_at=None):
    initialize_database()
    clean_user_id = int(user_id)
    clean_product_id = int(product_id)
    clean_quantity = max(1, int(quantity or 1))
    normalized_size = "Large" if str(size_label or "").strip().lower() == "large" else "Small"
    normalized_status = str(status or "Pending").strip().title() or "Pending"
    created_value = str(created_at or "").strip() or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    base_unit_price = float(unit_price or 0)
    base_line_total = round(base_unit_price * clean_quantity, 2)
    order_total = round(float(total_amount or 0), 2)
    tendered_total = round(float(cash_tendered or 0), 2)
    addon_items = list(addon_items or [])

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO orders (user_id, status, total_amount, cash_tendered, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (clean_user_id, normalized_status, order_total, tendered_total, created_value),
        )
        order_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO order_items (order_id, product_id, size_label, quantity, unit_price, line_total)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (order_id, clean_product_id, normalized_size, clean_quantity, base_unit_price, base_line_total),
        )
        order_item_id = cursor.lastrowid

        for addon in addon_items:
            addon_id = addon.get("addon_id")
            if addon_id is None:
                continue
            addon_quantity = max(1, int(addon.get("quantity", clean_quantity) or clean_quantity))
            addon_line_total = round(float(addon.get("line_total", 0) or 0), 2)
            cursor.execute(
                """
                INSERT INTO order_item_addons (order_item_id, addon_id, quantity, line_total)
                VALUES (?, ?, ?, ?)
                """,
                (order_item_id, int(addon_id), addon_quantity, addon_line_total),
            )

        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

    sync_sqlite_to_mysql()
    if normalized_status == "Completed":
        refresh_daily_reports()

    return {
        "order_id": order_id,
        "order_item_id": order_item_id,
        "order_code": f"BB-{int(order_id):06d}",
    }


def update_order_record_status(order_id, status):
    initialize_database()
    normalized_status = str(status or "Pending").strip().title() or "Pending"
    execute_query(
        """
        UPDATE orders
        SET status = ?
        WHERE order_id = ?
        """,
        (normalized_status, int(order_id)),
    )
    sync_sqlite_to_mysql()

    if mysql_is_available() and normalized_status == "Completed":
        mysql_conn = mysql_connection(with_database=True)
        mysql_cursor = mysql_conn.cursor()
        try:
            mysql_cursor.execute("CALL sp_complete_order(%s)", (int(order_id),))
            while mysql_cursor.nextset():
                pass
            mysql_conn.commit()
        except Exception:
            mysql_conn.rollback()
        finally:
            mysql_cursor.close()
            mysql_conn.close()

    refresh_daily_reports()


def delete_order_record(order_id):
    initialize_database()
    execute_query("DELETE FROM orders WHERE order_id = ?", (int(order_id),))
    sync_sqlite_to_mysql()
    refresh_daily_reports()


initialize_database()
