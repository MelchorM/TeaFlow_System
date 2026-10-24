# Cashier mouse control

Use this when the 5-inch JC8048W550 picture is readable but its touch glass is damaged. The laptop is the USB host. A hub alone cannot attach a mouse directly to the cashier's CH340 programming port.

1. Connect the hub to the laptop, then connect the wired mouse and cashier USB data cable to the laptop or hub.
2. Upload the current **cashier** firmware to the cashier's actual port. The port may change after reconnecting; it is currently COM8. The kitchen firmware is separate.
3. Close PlatformIO Serial Monitor and any serial capture tools.
4. Run `teaflow.cmd mouse` from the TeaFlow folder, or double-click `cashier-mouse.cmd`.
5. Wait for **Connected on COM...**. Move inside the laptop window's mouse area while watching the cursor on the ESP32, then left-click its buttons.

The control area maps to the full 800 x 480 cashier screen. It is a mouse pad, not a live copy of the LCD. Moving outside the area, switching away from the app, dragging more than eight screen pixels, pressing Escape, or using **Cancel click** cancels a held/queued click. Cancel does not undo an order action already submitted to the server. A click held for more than 1.5 seconds is canceled. The cashier now stays at full brightness. The input protocol retains its wake-only first-click handling if dimming is re-enabled in future firmware. The existing on-screen keyboard remains usable by mouse.

The laptop window and USB cable must remain connected. Wi-Fi/API polling, saved submissions, kitchen alerts and the existing payment/handover confirmations continue normally. Physical touch is ignored in mouse mode, so cracked-glass ghost touches cannot activate buttons. Mouse-only mode is saved independently of pending requests and Wi-Fi settings. Closing the app cancels input; it does not re-enable the cracked touchscreen. To restore touch after repair, close the app and send `mouse touch` in Serial Monitor, followed by a newline.

The bridge automatically selects a single CH340 device, then requires a cashier-specific version/model handshake before sending input. It never selects Bluetooth COM ports or the kitchen's native USB automatically. If several CH340 boards are attached, run `cashier-mouse.cmd --port COM8` with the correct port. **Reconnect** clears queued input. Unplug/replug also reconnects automatically when one cashier CH340 is available. The bridge does not capture global mouse/keyboard input or open a network listener.

Input frames are acknowledged individually, and motion is coalesced rather than filling the UART with stale movement. Queued clicks expire after one second. Missed acknowledgements and an eight-second device watchdog cancel incomplete input; they never synthesize a release. A full screen repaint also invalidates a held click. A stalled request may therefore require clicking again after the connection recovers. Only user mouse input activates normal UI actions; the bridge does not create orders, pay, or advance statuses on its own.

The launcher uses the project's Python when it includes Tk; otherwise it uses the available Codex Python runtime with Tk. The pure-Python pyserial module can come from the project's existing tool packages. On another PC, use Python with Tk support, install `iot/tools/requirements-mouse.txt`, and run `python iot/tools/cashier_mouse.py`. No Windows service or startup task is installed.

For software checks, run `python -m unittest discover -s iot/tools -p test_mouse_protocol.py -v`. Tests cover stale clicks, drag cancellation, queue bounds, reconnect clearing and matching acknowledgements, without accessing a board or shop orders.
