from PyQt5.QtCore import QDateTime


class OrderModel:
    def next_daily_order_number(self, order_entries):
        numbers = []
        for entry in order_entries or []:
            try:
                numbers.append(int(str(entry.get("id", "")).strip()))
            except (TypeError, ValueError):
                continue
        return max(numbers, default=0) + 1

    def renumber_order_entries(self, order_entries):
        normalized_entries = []
        for index, entry in enumerate(order_entries or [], start=1):
            updated_entry = dict(entry or {})
            updated_entry["id"] = str(index)
            normalized_entries.append(updated_entry)
        return normalized_entries

    def normalize_status(self, status):
        normalized = str(status or "").strip().lower()
        if normalized == "processing":
            return "Processing"
        if normalized == "completed":
            return "Completed"
        return "Pending"

    def count_statuses(self, order_entries):
        counts = {"Pending": 0, "Processing": 0, "Completed": 0}
        for entry in order_entries or []:
            counts[self.normalize_status(entry.get("status"))] += 1
        return counts

    def build_order_entry(self, product, order_config, slot_label, order_total, order_entries=None):
        product_name = str(product.get("name", "Product")).strip() or "Product"
        size = str(order_config.get("size", "Solo")).strip() or "Solo"
        quantity = max(1, int(order_config.get("quantity", 1) or 1))
        addons = [str(addon).strip() for addon in (order_config.get("addons", []) or []) if str(addon).strip()]
        created_at = QDateTime.currentDateTime()
        tendered = int(order_config.get("amount_tendered", order_total) or order_total)
        change_amount = int(order_config.get("change_amount", max(0, tendered - int(order_total))) or 0)
        return {
            "id": str(self.next_daily_order_number(order_entries)),
            "slot": slot_label,
            "product_name": product_name,
            "category": str(product.get("category", "")).strip() or "Product",
            "size": size,
            "quantity": quantity,
            "addons": addons,
            "total_price": int(order_total),
            "customer_name": str(order_config.get("customer_name", "")).strip() or "Walk-in Customer",
            "order_type": str(order_config.get("order_type", "")).strip() or "Dine-in",
            "payment_method": str(order_config.get("payment_method", "")).strip() or "Cash",
            "amount_tendered": tendered,
            "change_amount": change_amount,
            "cashier_name": str(order_config.get("cashier_name", "")).strip(),
            "status": "Pending",
            "created_at": created_at.toString("yyyy-MM-dd HH:mm:ss"),
            "display_time": created_at.toString("h:mm AP"),
        }

    def normalize_inventory_name(self, name):
        cleaned = "".join(ch.lower() for ch in str(name or "") if ch.isalnum())
        alias_map = {
            "pearl": "tapiocapearls",
            "pearls": "tapiocapearls",
            "tapiocapearl": "tapiocapearls",
            "crystal": "crystal",
            "freshmilk": "freshmilk",
            "milk": "freshmilk",
            "blacktea": "blacktealeaves",
            "blacktealeaves": "blacktealeaves",
            "tea": "tea",
            "coffeepowder": "coffeepowder",
            "creamer": "creamer",
            "fructose": "fructose",
            "whipcream": "whipcream",
            "cupssmall": "cupssmall",
            "cupsmall": "cupssmall",
            "cuplarge": "cupslarge",
            "cupslarge": "cupslarge",
            "straw": "straws",
            "straws": "straws",
            "sealingfilm": "sealingfilm",
            "flatlid": "flatlids",
            "flatlids": "flatlids",
            "domelid": "domelids",
            "domelids": "domelids",
        }
        return alias_map.get(cleaned, cleaned)

    def build_inventory_consumption_plan(self, product, order_config, inventory_items):
        quantity = max(1, int(order_config.get("quantity", 1) or 1))
        product_name = str(product.get("name", "")).strip()
        category_name = str(product.get("category", "")).strip().lower()
        addons = [str(addon).strip() for addon in (order_config.get("addons", []) or []) if str(addon).strip()]

        plan = {}
        inventory_by_name = {
            self.normalize_inventory_name(item.get("name", "")): item
            for item in inventory_items or []
            if item.get("id") is not None
        }

        def add_match(name, amount):
            normalized = self.normalize_inventory_name(name)
            item = inventory_by_name.get(normalized)
            if not item:
                return False
            inventory_id = item.get("id")
            if inventory_id is None:
                return False
            plan[inventory_id] = plan.get(inventory_id, 0) + amount
            return True

        def add_first_match(candidates, amount):
            for candidate in candidates:
                if candidate and add_match(candidate, amount):
                    return True
            return False

        def product_inventory_candidates():
            base_name = product_name
            trimmed = base_name
            if trimmed.lower().startswith("kape "):
                trimmed = trimmed[5:].strip()

            candidates = [
                base_name,
                f"{base_name} Powder",
                f"{base_name} Syrup",
                trimmed,
                f"{trimmed} Powder",
                f"{trimmed} Syrup",
            ]

            alias_candidates = {
                "mango": ["Mango Syrup"],
                "blueberry": ["Blueberry Syrup"],
                "green apple": ["Green Apple Syrup"],
                "honey peach": ["Honey Peach Syrup"],
                "kiwi": ["Kiwi Syrup"],
                "lemon": ["Lemon Syrup"],
                "lychee": ["Lychee Syrup"],
                "strawberrry": ["Strawberry Powder"],
                "strawberry": ["Strawberry Powder"],
                "kape cappuccino": ["Cappuccino Powder", "Coffee Powder"],
                "kape caramel": ["Caramel Macchiato Powder", "Coffee Powder"],
                "kape macchiato": ["Caramel Macchiato Powder", "Coffee Powder"],
                "kape matcha": ["Matcha Powder", "Coffee Powder"],
                "kape mocha": ["Chocolate Powder", "Coffee Powder"],
                "kape vanilla": ["Vanilla Powder", "Coffee Powder"],
            }
            candidates.extend(alias_candidates.get(base_name.lower(), []))
            return candidates

        add_first_match(product_inventory_candidates(), quantity)

        selected_size = str(order_config.get("size", "")).strip().lower()
        is_large = selected_size == "large"
        is_fruit_tea = "fruit" in category_name
        is_iced_coffee = "iced coffee" in category_name
        is_milkshake = "milkshake" in category_name
        is_milktea = "milktea" in category_name or "milk tea" in category_name

        add_first_match(["Cups Large" if is_large else "Cups Small"], quantity)
        add_first_match(["Straws"], quantity)
        add_first_match(["Flatlids" if is_fruit_tea else "Domelids"], quantity)

        if is_fruit_tea:
            add_first_match(["Tea"], quantity)
            add_first_match(["Fructose"], quantity)
        elif is_iced_coffee:
            add_first_match(["Coffee Powder"], quantity)
            add_first_match(["Creamer"], quantity)
            add_first_match(["Fructose"], quantity)
        elif is_milkshake:
            add_first_match(["Creamer"], quantity)
            add_first_match(["Whip Cream"], quantity)
            add_first_match(["Fructose"], quantity)
            if "coffee" in category_name:
                add_first_match(["Coffee Powder"], quantity)
        elif is_milktea or "tea" in category_name:
            add_first_match(["Tea"], quantity)
            add_first_match(["Creamer"], quantity)
            add_first_match(["Fructose"], quantity)

        for addon in addons:
            add_match(addon, quantity)

        return plan
