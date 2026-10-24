from . import db


class AuthModel:
    def authenticate(self, username, password):
        return db.authenticate(username, password)

    def reset_password(self, username, new_password):
        return db.reset_user_password(username, new_password)

    def get_all_users(self):
        return db.get_users()

    def update_user_profile(self, user_id, user_data):
        return db.update_user_profile(
            user_id,
            full_name=user_data.get("full_name"),
            role=user_data.get("role"),
            is_active=user_data.get("is_active"),
        )


class ProductModel:
    def get_all(self):
        return db.get_products()

    def create(self, product_data):
        return db.create_product(product_data)

    def update(self, product_id, product_data):
        return db.update_product(product_id, product_data)

    def delete(self, product_id):
        return db.delete_product(product_id)


class InventoryModel:
    def get_all(self):
        return db.get_inventory_items()

    def create(self, item_data):
        return db.create_inventory_item(item_data)

    def restock(self, inventory_id, quantity):
        return db.restock_inventory_item(inventory_id, quantity)

    def consume(self, inventory_id, quantity):
        return db.consume_inventory_item(inventory_id, quantity)

    def map_inventory_rows(self, rows):
        items = []
        for index, row in enumerate(rows):
            item_name = row.get("item_name", "")
            current_stock = row.get("current_stock", 0) or 0
            reorder_level = row.get("reorder_level", 0) or 0
            unit = row.get("unit", "") or "pcs"

            status_value = str(row.get("status", "")).strip().upper()
            if status_value in {"IN STOCK", "GOOD"}:
                status = "Good"
            elif status_value in {"OUT OF STOCK", "OUT"}:
                status = "Out"
            elif status_value == "LOW":
                status = "Low"
            else:
                status = "Good"

            icon = "".join([word[0] for word in item_name.split()[:2]]).upper() or "IT"
            last_restocked = row.get("last_restocked")

            items.append({
                "id": row.get("inventory_id"),
                "display_id": index + 1,
                "name": item_name,
                "category": row.get("category", ""),
                "stock": f"{int(float(current_stock))} {unit}",
                "reorder": f"{int(float(reorder_level))} {unit}",
                "status": status,
                "date": str(last_restocked) if last_restocked else "-",
                "accent": "#6f4a31",
                "icon": icon,
            })
        items.sort(key=lambda item: str(item.get("name", "")).strip().lower())
        for index, item in enumerate(items):
            item["display_id"] = index + 1
        return items


class AddonModel:
    def get_all(self):
        return db.get_addons()


class ShopScheduleModel:
    def get_current(self):
        return db.get_shop_schedule()
