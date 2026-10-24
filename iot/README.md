# TeaFlow IoT

- [Firmware](firmware/README.md): separate cashier and kitchen applications and board drivers.
- [Flask API](api/README.md): forwards device requests to the Express backend.
- [Mouse bridge](tools/MOUSE_CONTROL.md): controls the readable cashier LCD when its physical touch is damaged.

Run `teaflow.cmd iot` or `teaflow.cmd mouse` from the TeaFlow root. Open the root folder in VS Code to use the existing PlatformIO environments. Build configuration remains in the root `platformio.ini`.
