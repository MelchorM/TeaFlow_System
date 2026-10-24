from models import AddonModel, AuthModel, InventoryModel, OrderModel, ProductModel, ShopScheduleModel


class DashboardController:
    def __init__(self, product_model=None, inventory_model=None, addon_model=None, auth_model=None, order_model=None, shop_schedule_model=None):
        self.product_model = product_model or ProductModel()
        self.inventory_model = inventory_model or InventoryModel()
        self.addon_model = addon_model or AddonModel()
        self.auth_model = auth_model or AuthModel()
        self.order_model = order_model or OrderModel()
        self.shop_schedule_model = shop_schedule_model or ShopScheduleModel()

    def get_users(self):
        return self.auth_model.get_all_users()

    def update_user_profile(self, user_id, user_data):
        return self.auth_model.update_user_profile(user_id, user_data)

    def get_products(self):
        return self.product_model.get_all()

    def create_product(self, product_data):
        return self.product_model.create(product_data)

    def update_product(self, product_id, product_data):
        return self.product_model.update(product_id, product_data)

    def delete_product(self, product_id):
        return self.product_model.delete(product_id)

    def get_inventory_items(self):
        return self.inventory_model.get_all()

    def map_inventory_items(self, rows):
        return self.inventory_model.map_inventory_rows(rows)

    def create_inventory_item(self, item_data):
        return self.inventory_model.create(item_data)

    def restock_inventory_item(self, inventory_id, quantity):
        return self.inventory_model.restock(inventory_id, quantity)

    def consume_inventory_item(self, inventory_id, quantity):
        return self.inventory_model.consume(inventory_id, quantity)

    def get_addons(self):
        return self.addon_model.get_all()

    def get_shop_schedule(self):
        return self.shop_schedule_model.get_current()

    def normalize_order_status(self, status):
        return self.order_model.normalize_status(status)

    def current_order_status_counts(self, order_entries):
        return self.order_model.count_statuses(order_entries)

    def build_order_entry(self, product, order_config, slot_label, order_total, order_entries=None):
        return self.order_model.build_order_entry(product, order_config, slot_label, order_total, order_entries)

    def renumber_order_entries(self, order_entries):
        return self.order_model.renumber_order_entries(order_entries)

    def normalize_inventory_name(self, name):
        return self.order_model.normalize_inventory_name(name)

    def inventory_consumption_plan(self, product, order_config, inventory_items):
        return self.order_model.build_inventory_consumption_plan(product, order_config, inventory_items)
