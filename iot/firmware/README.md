# TeaFlow ESP32 terminals

The cashier board is the **GUITION JC8048W550**, identified from the user's PCB photo. Its TeaFlow display and Wi-Fi/queue connection have been tested on the board; full touch and order-flow acceptance checks remain.

## PlatformIO in VS Code

For a readable cashier screen with broken touch glass, the current cashier firmware supports a laptop USB mouse bridge. Run `teaflow.cmd mouse` after uploading, with the mouse and cashier connected to the laptop or hub. The laptop remains the USB host; the hub cannot connect the mouse directly to the screen's CH340 port. See [Mouse control](../tools/MOUSE_CONTROL.md). The kitchen is unaffected. The cashier port changed to COM8 on 23 October; always check USB identity before upload.

Open the **TeaFlow root folder**, which contains `platformio.ini`. Use the existing PlatformIO IDE extension; do not create a separate empty project.

The configuration pins Espressif32 6.9.0 (Arduino ESP32 2.0.17), GFX Library for Arduino 1.4.9, and ArduinoJson 7.4.2. PlatformIO installs these automatically. The generic S3 board definition is overridden for **16 MB flash, QIO flash, and OPI PSRAM**. USB CDC is disabled: GPIO19/20 are used for touch, and the board's CH340 provides USB serial.

### 1. Test the display and touch first

In PlatformIO's **Project Tasks**, expand `cashier-display-test`:

1. Choose **Build**.
2. Choose the CH340 USB serial port. It was detected as **COM5** during setup; COM3/COM4 were Bluetooth ports. Recheck after reconnecting.
3. Choose **Upload** when ready to replace the factory demo.
4. The screen should show four colored corner dots, 8 MB PSRAM, and a nonzero GT911 address (normally `0x5D`, alternatively `0x14`).
5. Tap each corner and drag. The displayed coordinates and drawn trail must follow your finger in landscape orientation. Verify red, green, blue, and yellow appear correctly.

The test uses no Wi-Fi, device key, backend, or order actions. If the screen is blank, colors are wrong, or touch does not follow your finger, resolve that before uploading the cashier app. Uploading either build replaces the installed program. These builds retain the NVS partition used for pending TeaFlow requests; do not erase flash while an order submission is unresolved.

If upload cannot connect, close Serial Monitor, hold BOOT, press/release RESET, release BOOT, and retry Upload. Use a USB data cable. The UART Serial Monitor speed is 115200.

Equivalent commands from a PlatformIO terminal:

```powershell
pio run -e cashier-display-test
pio run -e cashier-display-test -t upload --upload-port COM5
pio device monitor --port COM5 --baud 115200
```

### 2. Configure and build the cashier app

The current local cashier configuration is already prepared for the laptop's 2.4 GHz Windows mobile hotspot, with `API_BASE=http://192.168.137.1:5000`. Keep **Mobile hotspot** on while testing; the laptop's web and Flask servers must remain running. Its router's 2.4 GHz signal was too weak at the board's location.

For a new setup, copy `iot/firmware/cashier/config.example.h` to `iot/firmware/cashier/config.h`. Set:

- `WIFI_SSID` and `WIFI_PASSWORD`: a 2.4 GHz network on the same local network as the laptop. ESP32-S3 cannot join a 5 GHz-only network; the laptop can remain on the same router's 5 GHz band if both bands share the LAN.
- `API_BASE`: `http://LAPTOP_IPV4:5000`, with no trailing slash. Do not use `localhost` or `127.0.0.1` on the ESP32.
- `DEVICE_KEY`: the cashier device key from the ignored `web/backend/.env` file.

Keep the device key and initial connection defaults in the ignored `config.h`. Subsequent Wi-Fi/server changes can be saved from the touchscreen without uploading firmware. The device key still requires `config.h`. Configure the servers for LAN access and launch Express and Flask as described in `START_HERE.md`.

In **Project Tasks > cashier**, choose **Build**, then **Upload** after the display test passes. Or:

```powershell
pio run -e cashier
pio run -e cashier -t upload --upload-port COM5
```

For this workspace's optional local command-line installation, `& "$env:USERPROFILE/.platformio/penv/Scripts/python.exe" -m platformio` can replace `pio`. VS Code's PlatformIO terminal normally provides `pio` directly.

### Change Wi-Fi on the touchscreen

1. On the cashier, open **Status > Wi-Fi setup**. On the kitchen, open **Info > Wi-Fi**.
2. Tap **Scan Wi-Fi**, select a nearby 2.4 GHz network, and tap the password field. Hidden networks can be entered manually in the network-name field. An open network needs an empty password.
3. Use the on-screen keyboard: **UPPER/lower**, **123 / #**, **Space**, **Delete**, **Clear**, then **Done**. Passwords are masked and are never printed to Serial.
4. Connect the laptop to the same LAN. Set the laptop API field to `http://LAPTOP_IPV4:5000`; find its IPv4 address with `ipconfig`. Keep `http://192.168.137.1:5000` when using the existing Windows hotspot. The API address must have no path and cannot be localhost.
5. Tap **Save and connect**. This saves the connection as one Preferences/NVS record and reconnects. The cashier clears its unsubmitted draft cart while preserving saved submissions; the kitchen clears its cached queue and reloads it. Neither changes orders on the server. Setup stays accessible while offline. **Cancel** keeps the previous connection.

Saved connection settings override the compiled defaults after a normal upload or restart. Do not erase flash to change Wi-Fi: that would also erase unresolved saved submissions. The setup screen configures this terminal; it does not remotely configure the laptop's Wi-Fi. Keep the laptop hotspot and both TeaFlow servers running for the current setup.

### Direct cashier startup

The cashier now boots straight into ordering, as requested. There is no terminal sign-in or account-switch screen. Its cashier device key still protects API access and limits it to cashier actions. The website retains its admin, cashier, kitchen, and customer logins and permissions. Website account passwords do not need to be entered on either screen.

Device-only payments have no individual `paid_by` account attribution. Their order/stock/event records still exist normally. Older clients that explicitly supply an operator token still have that token validated, but this touchscreen build does not request one. Creation retries keep the same saved UUID and device identity, including submissions saved by the previous firmware.

### Cashier workflow

Both terminals share a forest-green/cream theme with white cards, centered buttons, and distinct status badges. The cashier menu shows six larger product cards per page, wrapped names, and a starting price from the currently available sizes. Selected options and the primary checkout/payment actions use filled green buttons. Order rows separate the large order code, status, amount, customer, and drink count; confirmation screens provide a separate review card.

When the connected cashier has no active orders, no draft cart, and no saved submission, it shows a large TeaFlow name and cup logo. Tap **Start an order** or the background to wake the menu; **Settings** opens Status. After waking, the logo returns after one minute without touch on Menu/Orders/Ready views when those empty-state conditions still hold. Customization, Cart, order details/confirmation, Status, and Wi-Fi entry remain accessible without an idle overlay. New active orders immediately remove the idle overlay on the next poll. A stale/offline queue never claims there are no active orders.

1. **New order**: select a drink, size, sugar, ice, up to four toppings, and quantity (1–20), then add it to the cart. The cashier supports up to 12 cart lines and uses the name `Walk-in Customer`.
2. **Cart**: review/remove items and create an **unpaid** order. Draft totals are estimates; review the server's saved total before accepting payment. Unsubmitted cart edits are held in RAM and do not survive restarting.
3. **Orders**: open online or walk-in orders and review their items/customization and authoritative saved total.
4. **Review payment**: check the customer's payment, then use the separate confirmation screen. The server applies stock rules and notifies the kitchen only after payment succeeds.
5. Follow Queued, Preparing, and Ready. Use **Complete handover** only after handing over the ready order.
6. **Status**: view the board, touch, network/API, and pending-request information; refresh menu and orders or change Wi-Fi.

When a paid order becomes Ready, a large green **READY: order code** notice appears at the bottom of every normal cashier screen. **View ready** opens an oldest-first list with large order codes, customer names, and drink counts; tap one to review it and confirm handover. The Orders tab shows the ready count, and ready rows are green. The notice remains until all ready orders are completed, including after reconnecting/restarting. It does not navigate away from a draft cart or confirm handover automatically. Existing action/error messages remain visible below the ready notice. Stale data removes the live notice and labels a cached ready list **LAST SEEN READY**; payment/handover still requires fresh server confirmation.

The queue refreshes approximately every three seconds plus request time. Unchanged responses do not clear/repaint the display; server timestamps are excluded from the display comparison. Cached queue actions are disabled after a failed refresh, while disconnected, or when more than ten seconds old. Payment/handover requests recheck server state immediately before posting. Network calls may pause touch handling briefly; the screen never treats a timeout as success. Orders lists only active orders; completed handovers remain in web history.

Creation saves the exact request and UUID in Preferences before sending. A timeout/reboot retains it, blocks new creation, and exposes **Retry saved submission** in Cart. Retrying reuses the same request, preventing duplicate orders. An explicit validation rejection allows editing the cart; ambiguous failures and authorization failures retain the saved request. Payment and handover retries use the original order ID. Never use a new order to work around an unresolved submission.

## Board configuration and sources

The driver uses ST7262-compatible RGB565 timings at 16 MHz and polls GT911 over I2C without driving unverified reset/interrupt pins. It preserves the factory touch configuration, probes both GT911 addresses, and accepts one touch point at a time.

| Function | GPIO |
| --- | --- |
| DE / VSYNC / HSYNC / PCLK | 40 / 41 / 39 / 42 |
| R0–R4 | 45 / 48 / 47 / 21 / 14 |
| G0–G5 | 5 / 6 / 7 / 15 / 16 / 4 |
| B0–B4 | 8 / 3 / 46 / 9 / 1 |
| Backlight | 2 |
| Touch SDA / SCL | 19 / 20 |

Sources: [GUITION product specifications](https://www.guition.com/esp32-display-module/custom-tft-display-module), [Arduino_GFX board example](https://github.com/moononournation/Arduino_GFX/blob/master/examples/PDQgraphicstest/Arduino_GFX_dev_device.h), [ESP32_Display_Panel JC8048W550C definition](https://github.com/esp-arduino-libs/ESP32_Display_Panel/blob/master/src/board/supported/jingcai/BOARD_JINGCAI_JC8048W550C.h), and [PlatformIO S3 board overrides](https://docs.platformio.org/en/latest/boards/espressif32/esp32-s3-devkitc-1.html).

## Kitchen terminal

The photographed DIYMORE 3.5-inch board matches the **LCDWIKI ES3C35P** design: ESP32-S3, ST77922 QSPI panel with integrated capacitive touch, 320 x 480 native resolution, 16 MB flash, and 8 MB OPI PSRAM. The kitchen interface uses a 480 x 320 landscape canvas. It has a separate driver and PlatformIO environments; use **COM6** for the kitchen and **COM5** for the cashier during this setup. Recheck port identity after reconnecting.

References: [LCDWIKI product and hardware resources](https://www.lcdwiki.com/3.5inch_ESP32-S3_Display), [LCDWIKI resource directory](https://www.lcdwiki.com/res/ES3C35P/), and [Elecrow's matching board/resources](https://wiki.elecrow.com/3.5_ESP32-S3_Display_with_320x480_Capacitive_IPS_Touch_Panel.html). Panel initialization and touch protocol were checked against the supplier's ST77922/ST77922_TOUCH Arduino libraries. Touch uses address `0x55` and **16-bit registers**; this is not an FT6336 driver.

| Function | GPIO |
| --- | --- |
| QSPI CS / clock | 10 / 12 |
| QSPI D0 / D1 / D2 / D3 | 11 / 13 / 14 / 9 |
| Backlight | 41 |
| Touch SDA / SCL | 38 / 39 |
| Touch reset / interrupt | 48 / 47 |
| Speaker MCLK / BCLK / data / word select | 17 / 18 / 15 / 21 |
| Speaker amplifier enable (active low) | 1 |

First build/upload **kitchen-display-test** to the kitchen's port. Verify the red/green/blue/yellow corner dots, 8 MB PSRAM, touch address `0x55`, and that tapping/dragging follows your finger. The test has no Wi-Fi or order actions. Native USB CDC is enabled for both kitchen environments; the cashier must keep CDC disabled because its touch uses GPIO19/20. Display commands with no data use a null TX buffer as required by the pinned ESP-IDF SPI driver. Framebuffer writes use DMA-compatible internal staging memory and transmit the full portrait buffer; canvas rotation provides landscape layout.

After that test passes, build/upload **kitchen**. The ignored `iot/firmware/kitchen/config.h` supplies initial Wi-Fi/API defaults and the **kitchen** device key. The prepared configuration targets the same laptop hotspot at `http://192.168.137.1:5000`. Never use the cashier key. The kitchen display uses device authentication. Change its network from **Info > Wi-Fi > Scan**, enter the password and laptop API address with the keyboard, then **Save and connect**. Saved settings override the defaults after restart. Kitchen web access remains `kitchen@bestbrew.local` with the password recorded in `.tools/staff-access.txt`.

```powershell
pio run -e kitchen-display-test -t upload --upload-port COM6
pio run -e kitchen -t upload --upload-port COM6
```

The queue shows paid Queued/Preparing/Ready orders, oldest paid first, two per page. **All / Queued / Preparing / Ready** filters show the count for each status; switching filters starts at the first page. Empty filtered results keep the tabs available. Tap an order to read every drink, size, sugar, ice, and topping across recipe pages. **Start preparing** moves Queued to Preparing. **Mark ready > Confirm ready** moves Preparing to Ready after review. Both actions recheck the server's current status and validate the acknowledgement. Disconnected, failed, or older-than-ten-second queue data disables actions. Polling excludes server timestamps from the screen comparison to avoid flashing unchanged content.

Kitchen queue cards separate the order code, status badge, customer/drink count, and a larger waiting-time badge. Recipe pages use a white reading panel with green topping lines; all fields still wrap across pages. Info groups the connection details and shows a volume bar above the existing sound controls. Wi-Fi setup and keyboard controls use the same theme.

An empty kitchen queue shows the TeaFlow name and enlarged cup logo, with **Info** and **Refresh** still available. The next paid order restores the normal queue automatically. When the last order leaves while its details are open, the kitchen returns to this idle queue. Offline state is labeled as waiting for connection rather than waiting for orders. Both logos are code-drawn versions of the existing TeaFlow cup mark, with no downloaded bitmap assets.

Queued/Preparing cards and order details show whole minutes since payment: **Wait <1m**, then **Wait 1m**, etc. The timer badge and card stripe turn yellow at **5 minutes** and red at **10 minutes**. These are initial display thresholds, not a promised preparation time. Ready orders show green **READY** instead of an overdue warning. Timing comes from the backend's original UTC payment timestamp and current server time, so a board restart/reconnect does not restart the wait. Offline/stale timers pause at the last server snapshot and the footer reports this; the next successful refresh restores the current age. Missing timing fields show **Wait --**. Minute changes only redraw queue/detail views, and timer repaints wait until a finger is released.

New paid events with queued drinks produce a prominent **NEW - view queued orders** banner and a three-note cafe bell chime. Its harmonic notes have a smooth attack and fading tail. If nobody acknowledges it, the kitchen plays up to two reminders at 15-second intervals while the queue is current and online. Tap the banner to open the Queued filter and stop playback/reminders, or open an order to acknowledge. Reminders also stop when no queued drinks remain; routine unchanged polling does not produce sounds.

The ES8311 codec shares the touch I2C bus at address `0x18`; I2S outputs generated 16 kHz PCM using the supplier's clock/register settings. Playback runs in a separate task and the amplifier is muted afterward, including on transfer failure. The last observed event, alert mute setting, and volume are saved in Preferences. New paid events received while muted still produce the visual notice. Muting also stops current playback and cancels scheduled reminders.

Open **Info > Test speaker** to play the test sound. **Mute alerts / Enable alerts** changes automatic order sounds; the explicit test works even when alerts are muted. **Vol - / Vol +** adjusts volume in ten-percent steps (10-100%, default 50%). The UART diagnostic command `speaker-test` plays the same test without changing an order. No SD card, microphone input, or online audio service is required. Codec failure leaves the order display and visual notices operational. The codec setup's attribution and Apache 2.0 license are in `iot/firmware/kitchen/ES8311_NOTICE.md` and `LICENSE-ES8311.txt`.

Keep `BUZZER_PIN=-1` for the legacy Serial prototype; this board's speaker uses the audio codec rather than a direct GPIO buzzer. Both terminals now provide saved touchscreen Wi-Fi/API setup; firmware upload is needed only to change their device keys or program.

## Idle dimming, connection indicators and sales

The cashier stays at 100% brightness, including its idle logo, because the user reported its 25% setting as a black screen and its cracked touch glass cannot wake it reliably. The kitchen empty-queue logo still dims to 25% after 30 seconds without touch. Only a fresh, empty kitchen queue can dim; settings, drafts, saved submissions and active orders stay bright. The first dimmed tap restores full brightness without activating its button. Another tap operates normally. New orders, a stale queue or leaving the idle view also restore 100%. Backlights use 5 kHz, 8-bit PWM on channel 7 (cashier GPIO2, kitchen GPIO41); PWM setup failure keeps the light fully on. Polling and kitchen audio continue while dimmed.

Both headers show four Wi-Fi strength bars and the age of the last successful queue synchronization. Signal thresholds use hysteresis to limit redraws. A failed refresh retains the last successful time and shows offline/stale state. Status/Info also shows RSSI in dBm. Sync ages are shown in ten-second, minute or hour buckets after the initial `Sync now` interval.

The cashier retains its original direct RGB display driver. Signal bars, queue-sync age and summary-sync age update only their small rectangles. They are excluded from the full-page comparison, as is the summary's changing generation timestamp. Unchanged totals do not clear/redraw the sales page every refresh; other unchanged pages retain the stable-content hash.

Open cashier **Status > Daily summary** for today's paid-order count, drink quantities and total sales in PHP. Totals include all channels and completed handovers, use the UTC payment timestamp with midnight boundaries in **Asia/Manila**, and refresh every 30 seconds while the page is open. Unpaid orders are excluded. They are fetched separately from the 100-order active queue and are not inferred from that cache. Failed requests retain the previous values with a warning; switching network/API clears the summary cache. **Refresh totals** fetches immediately. This page uses the cashier device key and does not require account login.

## Validation

For read-only visual checks, the `screen-dump` UART diagnostic sends the current RGB565 framebuffer as run-length packets. `.tools/capture-terminal.py cashier` or `kitchen` saves a PNG under `.tools/ui-qa/`, correcting kitchen canvas rotation. Close other serial monitors first. Captures do not change orders, stock, network settings, or the current view; kitchen capture reports busy during an active chime, so retry afterward.

`display-info` reports PWM availability, commanded brightness, idle state, signal bars and queue-sync age. Read-only navigation commands are `show-summary` / `show-menu` on the cashier and `show-info` / `show-queue` on the kitchen; they preserve the cart and never submit/pay/update an order. They do not interrupt an active touch or network keyboard. The capture helper's optional `--view summary|menu|info|queue` uses those commands before capture; without that option it retains the current page.

On 16 October 2026, both PlatformIO environments compiled successfully and all six existing Flask relay tests passed. The cashier uses approximately 47 KB static RAM and 840 KB flash; the display test uses approximately 20 KB static RAM and 321 KB flash. These figures exclude runtime allocations, including the display framebuffer and JSON held in PSRAM.

On 17 October 2026, the configured cashier was uploaded successfully on COM5. Physical UART diagnostics confirmed connection to the laptop hotspot, IP `192.168.137.73`, and a current order queue matching the server (zero active orders at that check). The user confirmed that the brief flash every three seconds stopped after the display update fix.

The subsequent touchscreen connection/login update also compiled and uploaded successfully on COM5 (48,424 bytes static RAM, 864,229 bytes program flash). All 23 web/database tests and seven relay tests passed. Live API checks with the existing admin and cashier accounts verified sign-in, the 43-product menu, the zero-order active queue, sign-out revocation, and rejection of unauthenticated cashier access. These checks did not modify shop orders or stock. Physical keyboard entry, switching accounts on the display, changing networks, and saved settings across a restart still need user acceptance checks.

The kitchen display test and kitchen app also compiled and uploaded on COM6 on 17 October. The user confirmed correct colors and touch tracking after the no-data SPI command fix. Physical USB diagnostics reported approximately 8 MB PSRAM, touch `0x55`, and backlight on. The final kitchen app uses 46,012 bytes static RAM and 828,469 bytes program flash. It connected at `192.168.137.71` and reported a current queue with one paid order. The full touchscreen Preparing/Ready/handover cycle, outage recovery, and speaker alerts remain acceptance tasks. No orders or stock were modified by the agent's live kitchen checks.

The subsequent speaker update compiled and uploaded on COM6 (46,084 bytes static RAM, 851,641 bytes program flash). Hardware reported successful audio transfers for the serial-triggered test while Wi-Fi and the queue stayed current. The user confirmed hearing the alert. A newly paid order triggering the automatic sound and saved mute/volume after restart remain acceptance checks. Existing live service logs also record kitchen status updates followed by cashier handover for orders 15 and 16; these were user-driven transactions, not generated by the agent's checks.

The latest update removes cashier login, adds kitchen touchscreen Wi-Fi setup, and improves the chime with bounded reminders and acknowledgement. It compiled and uploaded on COM5/COM6. Cashier: 48,360 bytes static RAM and 859,177 bytes program flash. Kitchen after the volume follow-up: 48,164 bytes static RAM and 864,649 bytes program flash. All 24 web/database tests and seven relay tests passed. Live checks confirmed direct cashier key access and both boards' current queues. The user confirmed the cashier opens without login and the kitchen Info > Wi-Fi > Scan controls work. The volume follow-up lengthens the chime's decay and uses near-full-scale PCM with unity codec gain. Volume was saved at 100%, playback completed while the queue stayed current, and the user confirmed it is loud enough. Actual network switching/restart persistence and new-order/reminder acknowledgement remain physical acceptance checks.

Waiting-time/ready-notice follow-up on 17 October: both environments built and uploaded successfully, cashier on COM5 (862,453 bytes flash, 48,360 bytes static RAM) and kitchen on COM6 (867,165 bytes flash, 48,164 bytes static RAM). All 25 web/database tests and seven Flask tests passed, including original UTC payment time, repeated ready-state reads, and removal after handover. The running server was restarted to expose the additive timing fields. Read-only checks verified them through the live Flask relay. Both boards reconnected with current queues. A user-driven newly paid event arrived during checks and the kitchen reported chime playback; the agent did not create or pay shop orders. The user confirmed both the kitchen waiting timer and the green cashier READY notice work after kitchen confirmation. Five-/ten-minute color transitions and reconnect acceptance remain pending.

Hardware acceptance still requires the complete updated order flow and a lost-connection/retry check on the actual boards. Kitchen corner colors/touch and the timer/cashier-ready notice were confirmed; cashier corner alignment, waiting-color thresholds, and recovery behavior still need physical acceptance checks.

UI follow-up on 17 October: both redesigned interfaces compiled and uploaded successfully. Final cashier build: 864,657 bytes flash / 48,360 bytes static RAM; kitchen: 868,905 bytes flash / 48,164 bytes static RAM. Actual framebuffers were captured and visually inspected: cashier product menu and paid-order details; kitchen empty queue and ready-order recipe details. The cashier product price text was enlarged after the first visual check. No overlap was found in the inspected views. Hardware diagnostics confirmed current queues and the kitchen touch controller, and the user confirmed names, prices, and buttons are easy to read/tap on both screens. The user-driven paid order visible during checks was not created/paid/updated by the agent. Other pages and long/multiple-order edge cases retain physical acceptance checks; backend logic did not change in this visual update, so its previously passing 25 web/database and seven relay tests were not repeated.

The later cashier buzzer addition was removed at the user's request, including its task, GPIO/PWM setup, controls, test commands, and guide. The idle-branding update then compiled and uploaded successfully on both boards: cashier 865,917 bytes flash / 48,368 bytes static RAM; kitchen 869,189 bytes flash / 48,164 bytes static RAM. Actual idle screenshots from both boards were inspected, with no clipping; cashier Status also showed only the restored refresh/Wi-Fi controls. Current empty queues were confirmed by read-only diagnostics. New-order wake and draft/reconnect edge cases remain physical acceptance tasks. Existing Wi-Fi settings and saved submissions were not erased, and no shop orders were changed by these checks.

Device follow-up on 17 October: added idle dimming, kitchen filters/counts, Wi-Fi/sync indicators and the cashier daily summary. All 27 web/database tests and eight Flask unit tests passed (35 total), including Manila midnight boundaries, multi-line drink quantities without multiplied sales, completed orders, empty days and cashier-only summary access. The running Express and Flask services were restarted. Read-only live checks returned consistent summary fields and denied the kitchen key; no shop transactions were created or changed. Both apps built and uploaded: cashier 879,105 bytes flash / 48,560 bytes static RAM; kitchen 878,841 bytes flash / 48,292 bytes static RAM. The cashier display-test environment also builds with the restored direct RGB driver.

Actual cashier daily-summary, kitchen Info and kitchen idle screenshots were inspected. Both boards reported current empty queues and 25% idle brightness through diagnostics. A reported cashier flash was addressed by updating changing indicators in small regions and excluding summary generation timestamps from full-page redraws. Backlight startup now attaches its PWM channel before setting full brightness; the user confirmed the cashier picture is visible after that correction. The user then confirmed the cashier remains steady without flashing. Final diagnostics reported cashier 100% on the summary page and kitchen 25% on its current empty idle queue. Physical dim/wake behavior, filtered multi-page order handling and wake on a new paid order remain acceptance checks.

On 23 October, the user reported a readable cashier LCD with cracked, unresponsive touch glass and supplied a wired USB mouse. Added a laptop control window (`iot/tools/cashier_mouse.py`) and acknowledged cashier UART input, with an on-screen cursor and existing button hit targets. Mouse-only mode suppresses physical touch and persists separately from pending submissions/network settings. Delayed, dragged, stale and disconnected presses are canceled. The bridge accepts input only in its own control area and does not capture the global mouse.

All 11 mouse protocol tests passed. The cashier built using VS Code's PlatformIO Core 6.2.0 and uploaded with flash verification to the identified CH340 cashier on COM8 (MAC ac:27:6e:a4:a3:14): 898,309 bytes flash / 49,224 bytes static RAM. Hardware acknowledged pointer movement, Status navigation, corner coordinates and a duplicate frame; its captured Status page showed the cursor and connected mouse input. The running laptop window completed the model/version handshake on COM8. These checks requested no order creation, payment or status changes. The backend and kitchen firmware were unchanged; their previous tests were not repeated. The user confirmed that moving the mouse and clicking New order/Status works on the physical screen. Cable-loss recovery, restart persistence and a complete user-driven order flow with mouse input remain acceptance checks.



23 October brightness correction: after the user reported the cashier idle screen as black, diagnostics showed 25% brightness with a normal framebuffer. Returning to 100% restored the visible menu, confirmed by the user. The cashier now stays at full brightness while retaining idle branding. Built and uploaded successfully on the verified COM8 cashier (898,233 bytes program / 49,224 static RAM); no NVS erase or order commands were issued. Post-upload diagnostics stayed at 100%, mouse control reconnected, and the user confirmed both the screen and mouse work. Kitchen dimming is unchanged.
