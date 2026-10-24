# Run TeaFlow for BESTBREW

This version follows the Web Systems and IoT proposals: Node.js/Express, HTML/CSS/Bootstrap/JavaScript, MySQL, Flask, and ESP32 C++. Laravel has been removed.

## Start the application

1. Ensure MySQL is running in XAMPP. The current connection uses `127.0.0.1:3306` and a separate database named `teaflow`.
2. Open PowerShell in `C:/Users/63905/Documents/TeaFlow`.
3. Start the web system:

```powershell
.\teaflow.cmd serve
```

Open **http://127.0.0.1:3000**.

4. In a second PowerShell window, start the Flask IoT API:

```powershell
.\teaflow.cmd iot
```

The Flask endpoint is **http://127.0.0.1:5000/iot/state**. It requires a valid device key; opening it without a key returns Unauthorized.

Press Ctrl+C in each terminal to stop its server. No permanent PATH or PowerShell execution-policy change is required.

## Accounts and workflow

Customer accounts are created through **Create an account** on the website.

Local owner, cashier, and kitchen accounts are configured for this installation. Their access details are in `.tools/staff-access.txt`, which is ignored by Git. Sign in at `/login`.

- Owner/admin: products and recipes, inventory, cashier orders, kitchen, and order records.
- Cashier: online/walk-in orders, payment verification, inventory, and completed handover records.
- Barista/kitchen: confirmed queue and Preparing/Ready actions.
- Customer: customized orders, private tracking, and personal order history.

Try one complete flow:
1. Register a customer, choose a drink, size, sugar, ice, toppings, and quantity, then place the order.
2. Sign in as cashier in another browser profile and confirm payment after checking it.
3. Sign in as kitchen and mark Preparing, then Ready.
4. Cashier completes handover. The order leaves the active queue and stays in history.

## Database and setup

Configuration is in the ignored `web/backend/.env`; `web/backend/.env.example` contains the available settings. The database already contains the saved BESTBREW catalog, temporary topping prices, and clearly labeled sample recipes/stock. Old BESTBREW users and transactions were not imported.

For another computer or a changed MySQL connection, edit `web/backend/.env`, then run:

```powershell
.\teaflow.cmd setup
```

Setup creates only the selected TeaFlow database/tables. It refuses to initialize a database belonging to another application. Re-running setup does not reset stock, change saved menu prices, or replace existing staff passwords.

The application has independent centavo prices per topping and size. Initial topping prices are PHP 9 each, authorized as temporary values. Set actual prices in **Products & recipes**. Enter actual ingredients and opening stock in **Inventory**, then configure recipes for each drink size. The initial recipes are demonstration portions, not measured BESTBREW recipes.

## Local-network IoT demonstration

For customer browsers and ESP32 devices on the same Wi-Fi, set these values in `web/backend/.env` and restart the servers:

```dotenv
HOST=0.0.0.0
FLASK_HOST=0.0.0.0
```

Use the laptop's local IPv4 address for customer browsers (`http://LAPTOP_IP:3000`) and firmware (`http://LAPTOP_IP:5000`). Flask calls Express locally; `EXPRESS_BASE_URL` can remain `http://127.0.0.1:3000`.

The device keys are in `web/backend/.env`. Use the cashier key only for the cashier firmware and the kitchen key only for the kitchen firmware. Put initial Wi-Fi/key settings in ignored `config.h` files, following `iot/firmware/README.md`. The cashier now opens straight to ordering without account login. Change its network in **Status > Wi-Fi setup**. Change the kitchen network in **Info > Wi-Fi**. Both provide network scanning, a password keyboard, and a saved laptop API address. Changing cashier connection settings clears the draft cart while preserving unresolved saved submissions. Website account sign-in remains available normally.

## Checks

```powershell
.\teaflow.cmd test
.\.tools\python\python.exe -m unittest discover -s iot/api -p test_api.py -v
```

Twenty-seven web/database tests and eight Flask tests passed, including a real Flask/Express/MySQL integration check. Tests cover device-key cashier ordering without login, web role permissions, creation/payment retries, stock rules, optional older-client token validation, original UTC payment timing, and ready orders remaining visible until handover. Tests use temporary isolated databases and remove them afterward. They leave the existing BESTBREW database unchanged.

The cashier was most recently detected on COM8; USB ports can change after reconnecting. Verify each board identity before upload. Both synchronize through the laptop's 2.4 GHz mobile hotspot (`http://192.168.137.1:5000`). The user confirmed kitchen colors/touch, cashier startup without login, and kitchen **Info > Wi-Fi > Scan**. Tap a paid order, use **Start preparing**, then **Mark ready > Confirm ready** after all drinks are done. The improved alert uses a three-note cafe chime and a **NEW - view queued orders** banner, with up to two reminders 15 seconds apart until acknowledged. Its volume is saved at 100%, and the user confirmed the updated chime is loud enough. Open **Info** for sound test, mute, volume, and Wi-Fi setup. Keep Mobile hotspot and both servers running. The user confirmed the cashier's periodic screen flashing is fixed. New-order/reminder timing, saved settings after restart, and reconnect acceptance checks remain; see `iot/firmware/README.md`.

Kitchen Queued/Preparing cards now show minutes since payment, turning yellow at 5 minutes and red at 10; Ready stays green. At the cashier, a large green **READY** banner and **View ready** list identify drinks awaiting handover without interrupting cart entry. The user confirmed both the kitchen timer and cashier READY notice work. Confirm **Complete handover** after giving the order to the customer. Waiting time recovers from server records after reconnect/restart; stale timers pause and the live cashier notice hides until refreshed.

Both screens now use matching green/cream styling, white cards, clearer status badges, and centered buttons. The cashier menu has six larger product cards per page with starting prices; the kitchen has larger wait badges, a recipe reading panel, and an Info volume bar. Both updates were uploaded, actual screen captures were checked, and the user confirmed both layouts are easy to read and tap.

With no orders, both terminals show the **TeaFlow name and cup logo**. On the cashier, tap **Start an order** (or the background) to use the menu; the logo returns after one minute without touch when there is no cart or saved submission. **Settings** remains available on the idle screen. The kitchen resumes its queue when a paid order arrives; **Info** remains available while idle. The canceled cashier buzzer feature has been removed.

The kitchen logo screen dims to **25% after 30 seconds** while its empty queue is current. The cashier stays at **100% brightness** because its 25% setting was reported as black and its touch glass is damaged. The first tap wakes the light; tap again to operate a button. New orders or connection trouble restore full brightness. The kitchen queue has **All / Queued / Preparing / Ready** filters with counts and two cards per page. Tapping its new-order banner opens Queued. Both headers show Wi-Fi bars and the last successful sync age. On the cashier, open **Settings/Status > Daily summary** for today's paid orders, drinks sold and total sales, including completed orders and all channels. The summary uses **Manila midnight**, refreshes every 30 seconds while open, and labels cached values when refresh fails.

For a readable cashier LCD with damaged touch glass, use the laptop mouse bridge: connect the wired mouse and cashier USB data cable to the laptop or hub, then run `teaflow.cmd mouse`. Move inside the control window while watching the cursor on the ESP32. The window must remain open. Physical touch is disabled in mouse mode, including after restart; existing payment/handover confirmations remain. See [Mouse control](../iot/tools/MOUSE_CONTROL.md) for reconnect, port selection and restoring touch after repair.

## Project folders

- `web/frontend/`: HTML/EJS templates and browser CSS/JavaScript.
- `web/backend/`: Express source, setup, tests, dependency files and private `.env`.
- `iot/api/`: Flask relay, tests and Python requirements.
- `iot/firmware/`: cashier/kitchen sketches and shared display/client libraries.
- `iot/tools/`: laptop mouse bridge and its tests.
- `shared/catalog/` and `shared/assets/menu/`: menu data and images.
- `docs/`: project plan, setup notes and dated progress reports.
- `archive/BESTBREW/`: original business reference and historical data, preserved.
- `.tools/`: local runtimes, private credentials, hardware helpers and QA evidence.

All command examples above run from the TeaFlow root. See [folder guide](FOLDER_GUIDE.md) for the complete layout.
