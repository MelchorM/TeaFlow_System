# TeaFlow implementation plan

TeaFlow is the combined Web Systems and IoT project for the BESTBREW milk tea shop. The implementation follows the supplied proposals. Laravel and its Composer tooling have been removed at the user's request.

## Requirements sources

- IoT: `C:/Users/63905/Downloads/TeaFlow_IoT_Project_Proposal.docx` and its `Nganiiii` copy. Both describe the same IoT scope.
- Web Systems: `C:/Users/63905/Downloads/IT-314-Project-Proposal (2).docx`.
- Business reference: `BESTBREW/BESTBREW`, confirmed by the user as the same shop.

Documents are requirements references. Embedded example setup instructions and legacy SQL were not executed. The original proposals and BESTBREW project remain unchanged.

## Technology and architecture

| Layer | Implementation |
| --- | --- |
| Customer and staff website | HTML, CSS, Bootstrap, JavaScript; Express renders HTML with EJS templates |
| Business backend | Node.js and Express.js |
| Persistent records | MySQL/MariaDB through the existing XAMPP service |
| IoT supporting API | Python/Flask, forwarding requests to the central Express backend |
| Embedded terminals | ESP32 C++ with ArduinoJson 7 and HTTP/JSON |

Customer browsers communicate with Express. Cashier/kitchen ESP32 terminals communicate with Flask on port 5000. Flask forwards authenticated requests to Express. Express alone applies order, payment, recipe, and stock rules and writes the central database. Flask keeps no second order store or inventory database.

The integration keeps both proposal technologies without duplicating business rules. The IoT proposal's temporary in-memory API has been replaced by a persistent supporting API for the integrated project.

## Proposal feature mapping

| Proposed feature | Current implementation |
| --- | --- |
| Authentication and appropriate access | Website registration/sign-in with separate admin, cashier, kitchen, and customer permissions; screens use role-specific device keys and cashier starts without account login |
| Customer online ordering | BESTBREW menu, size, sugar level, ice level, toppings, quantity, cart, and checkout |
| Cashier online and walk-in orders | Staff order queue, browser walk-in entry, and authenticated cashier device endpoints |
| Payment verification | Cashier manually checks payment and confirms it; only this action deducts ingredients and queues the order |
| Kitchen display and order updates | Browser queue and ES3C35P touchscreen queue; recipe pages, Start preparing, and separate Ready confirmation; hardware queue synchronization verified, full order-flow acceptance pending |
| Kitchen waiting time | Queued/Preparing timer since payment, yellow at 5 minutes and red at 10; Ready stays green; UTC server time survives reconnect/restart |
| Cashier ready notification | Persistent green ready-order code/count, oldest-first View ready list, and fresh-state handover confirmation without interrupting cart entry |
| Empty-queue branding | TeaFlow name and enlarged cup logo on both terminals; touch-to-start cashier with one-minute idle return, automatic kitchen queue recovery, and accessible settings |
| Idle display brightness | Fresh empty logo screens dim to 25% after 30 seconds; touch, incoming orders or stale data restore full brightness without stopping synchronization/audio |
| Kitchen status filters | All, Queued, Preparing and Ready counts, oldest-first filtered pages, and new-order banner opens Queued |
| Terminal connection status | Wi-Fi signal bars and last successful queue-sync age on both devices; RSSI in Status/Info |
| Cashier daily summary | Paid-order count, drink quantities and total sales for the Manila payment day, including completed orders and all sales channels |
| Cashier mouse input | Laptop USB mouse bridge for the readable LCD with cracked touch glass; cursor, click cancellation, acknowledged UART input and saved mouse-only mode |
| Automated inventory | Per-size recipe requirements and topping quantities saved with each order; deductions committed with payment |
| Low-stock notification | Inclusive thresholds displayed to cashier, kitchen, inventory staff, and device clients |
| Product management | Owner can add, edit, enable/disable, and delete products from the menu; historic order snapshots remain intact |
| Inventory management | New ingredients, restocks, stock counts, low-stock thresholds, and an adjustment history |
| Order records | Customer history, cashier completed records, saved amounts and customization, payment time, and order events |
| Audible kitchen notification | ES8311 three-note cafe chime with a visible acknowledgement banner, up to two 15-second reminders, manual test, mute, and saved volume; initial speaker audibility confirmed |
| Wi-Fi refresh and reconnect | Approximately three-second polling; stale-data indicators; both screens provide network scanning, touchscreen credentials/API entry, saved connection settings, and reconnect behavior |

## Operating rules

1. New website or walk-in orders are Unpaid; stock remains unchanged.
2. The cashier checks payment before confirming it.
3. The server locks the order and required ingredient rows. If any ingredient is insufficient, payment and all deductions are rejected together.
4. A successful confirmation deducts ingredients once, records payment, creates a paid-order event, and sets Queued.
5. The kitchen only receives payment-confirmed orders.
6. Barista/kitchen staff move Queued to Preparing, then Ready.
7. Cashier staff mark Completed after handover; completed orders leave the active queue.
8. Payment, creation, and status retries safely reuse the original identifiers. Duplicate payment requests do not cause another deduction or paid-order event.
9. Prices are calculated by the server. Recipe and price snapshots preserve already-submitted orders when the menu changes.
10. A failed synchronization is never displayed as a successful action. Browser staff buttons are disabled while the displayed state is stale.

Stock uses integer thousandths of the ingredient's stated unit; prices use integer centavos. Recipes may have fixed quantities or scale with the selected sugar/ice option. For the initial configurable rule, light ice uses half the regular-ice amount; this assumption must be checked with BESTBREW before service.

## BESTBREW data and temporary values

The extracted catalog contains 43 products in the saved milk tea, fruit tea, iced coffee, and milkshake categories. Product images and saved Small/Large prices are reused. Test categories, old users, credentials, orders, and inventory balances were not imported.

The user authorized temporary topping prices. Pearl, Crushed Oreo, Crushed Graham, and Crystal initially cost PHP 9 each; the owner can set a different price for each.

The legacy recipe dump has mismatched ingredient references, so its quantities were not imported as valid recipes. Initial recipes use one sample drink-base portion and one correctly sized cup per drink; toppings use sample portions. Staff screens label these values as samples. Enter the shop's verified recipes and opening stock before operating with real transactions.

The legacy SQL stock-deduction trigger is not used. All new deductions occur during payment confirmation.

## Purchased hardware

| Terminal | Purchased screen | Known listing information |
| --- | --- | --- |
| Cashier | GUITION JC8048W550, 5-inch with touch | 800 x 480, ESP32-S3, 16 MB flash, 8 MB PSRAM; PlatformIO cashier uploaded on COM5. Wi-Fi/queue synchronization verified through the laptop hotspot; user confirms periodic display flashing is fixed. Full order flow and touch alignment still require checking |
| Kitchen | DIYMORE / LCDWIKI ES3C35P-compatible 3.5-inch capacitive touch | ST77922 QSPI with integrated touch at 0x55, 320 x 480 native / 480 x 320 landscape, 16 MB flash, 8 MB PSRAM. Uploaded on COM6; user confirmed colors, touch, and hearing the ES8311 speaker test. Paid queue synchronization verified on the laptop hotspot |

The IoT proposal specifies a 7-inch cashier display. The purchased 5-inch unit is an explicit hardware difference to document. Original DOCX files have not been edited.

Product links:
- https://s.shopee.ph/4B0gPuqxv7?share_channel_code=5
- https://s.shopee.ph/70Krn8fhri?share_channel_code=5

Listing screenshots were supplied because the links could not be accessed. The user later supplied the cashier PCB photo, identifying JC8048W550, and confirmed PlatformIO IDE is installed in VS Code. Cashier pin assignments were cross-checked against Arduino_GFX and ESP32_Display_Panel board definitions. The kitchen PCB photo matches the LCDWIKI ES3C35P design; its display/touch wiring and protocol were checked against the supplier's ST77922 and ST77922_TOUCH examples.

## Validation and remaining work

Twenty-five Express/MySQL tests and seven Flask tests passed. Checks cover web checkout and authentication, role boundaries, server pricing, retries, simultaneous payment confirmation, stock rollback, private order access, stock auditing, CRUD, option-based recipe quantities, device-key cashier ordering without account login, and live Flask-to-Express requests/outage reporting. The latest test verifies original UTC payment timing and ready-order visibility through repeated polls until handover. Explicit optional operator tokens used by older clients still receive expiry, role, and revocation checks. Test runs create and remove isolated databases; they do not alter the shop's existing database.

Dependency installation reports zero Node security advisories after removing an unnecessary outdated dependency. No browser was connected, so rendered pages have HTTP/template checks but no visual browser inspection.

Still required:
- Verify cashier display colors, corner touch mapping, and the cashier workflow on hardware using the PlatformIO builds in `iot/firmware/README.md`.
- Complete a paid order through the kitchen touchscreen's Preparing and Ready controls, then confirm cashier handover and reconnect behavior.
- Verify a newly paid order triggers one notification, unchanged polling stays quiet, and saved speaker settings survive a restart.
- Confirm final menu/topping prices, actual recipes, units, stock, and the light-ice quantity rule with BESTBREW.
- Run the combined local-network demonstration with both terminals.

Both cashier PlatformIO environments compiled successfully, and all six Flask relay tests passed on 16 October 2026. On 17 October the configured cashier was uploaded on COM5 and physically confirmed synchronized with the active order API over the laptop's 2.4 GHz hotspot (`http://192.168.137.1:5000`). The user confirmed the three-second flashing stopped after unchanged poll responses were excluded from screen repainting. Full hardware order flow, touch alignment, and kitchen integration remain. See `START_HERE.md` and `iot/firmware/README.md`.

The 17 October follow-up adds touchscreen Wi-Fi scanning, a masked on-screen keyboard, saved network/API settings, and server-verified admin/cashier sign-in with account switching. This cashier firmware compiled and uploaded successfully on COM5. The running hotspot API accepted both existing local admin and cashier accounts, returned 43 menu products and zero active orders, rejected unauthenticated cashier access, and rejected both tokens after logout. No shop orders were created or changed by these live checks. Touchscreen sign-in, switching to another Wi-Fi network, persistence after restart, and the complete hardware order workflow still need physical acceptance checks.

Kitchen follow-up on 17 October: added separate kitchen and kitchen-display-test environments and the ST77922 driver. Corrected no-data SPI commands and native USB flags during board bring-up. The user confirmed correct corner colors and finger tracking. The kitchen app compiled (828,469 bytes program flash, 46,012 bytes static RAM) and uploaded successfully on COM6. UART confirmed IP `192.168.137.71`, touch `0x55`, and a current queue containing one paid order. The supporting Flask service was restarted after it was found stopped. The agent's live checks did not create/pay/change orders. Full hardware Preparing/Ready/handover acceptance and speaker alerts remain.

Speaker follow-up: the supplier's ES8311/I2S and active-low amplifier wiring were checked against its music example. Added generated two-tone PCM playback in a separate task, triggered by a changed paid-event ID with an active paid queue. Info provides test, mute, and volume controls; settings persist across restarts. The speaker firmware built and uploaded on COM6 (851,641 bytes program flash, 46,084 bytes static RAM). Hardware logged successful audio transfers without losing queue synchronization, and the user confirmed hearing the test alert. The automatic new-order alert and saved settings after restart remain acceptance checks. Live logs additionally show user-driven payment, two kitchen status updates, and cashier completion for orders 15 and 16.

Latest 17 October changes: removed the cashier account-login and account-switch screens at the user's request; it now opens directly to ordering using its device key. Website login remains unchanged, and optional tokens from older clients are validated when explicitly provided. Added kitchen Info > Wi-Fi with scanning, password/API keyboard entry, saved settings, cancel, and reconnect. Upgraded the alert to a harmonic three-note cafe chime with a visible acknowledgement button and at most two reminders 15 seconds apart while queued orders remain and the connection is fresh. Opening an order, acknowledging the banner, or muting stops the sound/reminders.

Both final builds compiled and uploaded: cashier on COM5 (859,177 bytes flash, 48,360 bytes static RAM) and kitchen on COM6 after the volume follow-up (864,649 bytes flash, 48,164 bytes static RAM). All 24 web/database and seven Flask tests passed. Live API checks verified menu/queue access with the cashier key and no account login. The user confirmed direct cashier startup and kitchen Info > Wi-Fi > Scan work. The chime now has a longer decay and near-full-scale PCM with unity codec gain; volume was saved at 100%, hardware completed playback with the queue current, and the user confirmed it is loud enough. Typing/saving a different network, restart persistence, and reminder acknowledgement/timing remain physical acceptance checks.

Waiting-time/ready-notice follow-up: kitchen cards and order details show whole minutes since the original payment, with yellow at 5 minutes and red at 10; Ready stays green. Timing uses UTC server/payment fields and pauses the cached display when stale. The cashier shows a persistent green ready code/count and an oldest-first View ready list, preserving cart entry and existing action messages. Completion still requires explicit, fresh-state handover confirmation. Both environments built and uploaded on COM5/COM6: cashier 862,453 bytes flash / 48,360 bytes static RAM; kitchen 867,165 bytes flash / 48,164 bytes static RAM. All 25 web/database and seven Flask tests passed. Live read-only checks verified timing fields and both boards' current queues. A user-driven paid event arrived during verification and the kitchen logged chime playback. The user confirmed the kitchen timer and green cashier READY notice both work after marking the order ready. Five-/ten-minute colors and reconnect acceptance remain pending.

UI follow-up: applied a matching forest-green/cream palette, centered controls, primary action styling, status pills, and white reading cards. Cashier now shows six larger product cards per page with wrapped names and larger starting prices, structured order rows, and clearer confirmation cards. Kitchen separates order/status/wait badges, colors recipe toppings, and groups connection/sound controls with a volume bar. Both builds were uploaded and their actual framebuffer captures inspected: cashier menu/paid-order details and kitchen empty queue/ready-order details. Final sizes: cashier 864,657 bytes flash / 48,360 bytes static RAM; kitchen 868,905 bytes flash / 48,164 bytes static RAM. The user confirmed both UIs look good and names/prices/buttons are easy to read and tap. The backend was unchanged; the prior 32 tests were not rerun for styling. Long/multiple-order layouts, remaining pages, and recovery behavior still require broader physical acceptance.

The user withdrew the cashier buzzer addition and requested removal. Its driver/task, sound settings screen, serial test commands, configuration example, and wiring guide were removed. The cashier retains the redesigned UI and visual Ready notice; kitchen speaker alerts remain in place. No physical cashier buzzer installation was completed.

Idle-branding follow-up: added the enlarged code-drawn TeaFlow cup mark and system name to both empty-queue screens. Cashier initially idles after a fresh empty queue; Start an order/background touch opens ordering, and the idle screen returns after one minute without touch on Menu/Orders/Ready when there is no draft or saved submission. Settings and active editing views are excluded. Kitchen restores its queue when paid orders arrive and returns to the logo when the last displayed order leaves. Both builds compiled and uploaded: cashier 865,917 bytes flash / 48,368 bytes static RAM, kitchen 869,189 bytes flash / 48,164 bytes static RAM. Actual idle framebuffers from both devices were visually inspected; cashier Status was also observed with no buzzer controls. Read-only diagnostics reported current empty queues. New-order wake, draft protection, and reconnect edge cases still need physical acceptance; the unchanged backend's earlier 32 tests were not rerun for this UI change.

Next device improvements: both apps now include 30-second idle dimming, kitchen status filters/counts, Wi-Fi strength and queue-sync age, and a cashier daily summary using the Manila payment day. Summary totals include all paid channels and completed orders, independently of the active-queue limit. All 35 backend/relay tests passed. Both final apps compiled and uploaded, and actual summary/Info/idle screenshots were inspected. The cashier uses small-region indicator updates to avoid periodic full-page clears; corrected PWM initialization restores full startup brightness, confirmed visible by the user. The user subsequently confirmed the cashier is steady without flashing. Filter pagination with live orders and physical dim/wake/new-order wake remain acceptance checks. No shop orders or stock were changed by agent verification.

Cashier input follow-up on 23 October: the LCD remains readable after its touch glass cracked. Added a laptop USB mouse bridge, so the existing wired mouse and cashier connect to the laptop or hub. The hub alone cannot provide USB-host functionality to the cashier programming port. The bridge provides cursor movement and existing UI clicks, saves mouse-only mode to suppress broken touch input, and cancels stale/dragged/disconnected presses. Eleven input protocol tests passed. Firmware compiled and uploaded to the verified cashier on COM8, and hardware acknowledged pointer movement and Status navigation. The captured display showed the cursor and connected input; the laptop control window completed its handshake. No shop order actions were requested by these checks. The user confirmed physical cursor movement and screen button clicks work. Cable-loss/restart recovery and the complete mouse-driven order flow remain acceptance checks.


Folder organization on 23 October: separated the web frontend and backend under `web/`; grouped the Flask API, firmware and mouse tools under `iot/`; moved menu data/images into `shared/`, reports/notes into `docs/`, and the original BESTBREW reference into `archive/`. Launchers, configuration paths, static assets, integration tests, local helpers and PlatformIO settings were updated. Private settings, reports and historical business files were preserved and checked against source-backup hashes. Removed redundant report-tool installers, the extraction log and bytecode caches (421,484,831 bytes). All 27 web/database, eight Flask and eleven mouse protocol tests passed. Read-only checks verified website assets, all 43 menu images and the IoT relay. Both devices resumed API polling; normal device-driven order activity continued during verification. Baseline orders remained in history with unchanged contents, totals and payment timestamps.

Both relocated cashier and kitchen firmware builds subsequently passed. No upload or device settings change was needed for the folder organization. See [folder guide](FOLDER_GUIDE.md) for the final layout and validation.


Cashier visibility follow-up on 23 October: the user reported a black cashier screen. USB diagnostics showed the device online, queue current and backlight at 25% on its idle view; its captured framebuffer was normal. The read-only menu command restored 100% brightness, and the user confirmed the physical menu was visible. Disabled automatic dimming on the cashier while retaining its idle branding, direct RGB driver and existing PWM startup sequence. The kitchen dimming behavior is unchanged. The cashier build passed (898,233 bytes program / 49,224 static RAM) and was uploaded successfully to the verified COM8 cashier (MAC ac:27:6e:a4:a3:14) without erasing NVS. The mouse control window was temporarily closed to release the upload port. No order mutations were issued by the diagnostic/fix commands.

Post-upload diagnostics reported 100% brightness at startup and again after 33 seconds, with Wi-Fi connected and the queue current (two active orders). The laptop mouse window was reopened and completed its COM8 handshake. The user confirmed after the upload that the cashier screen is visible and the mouse works.
