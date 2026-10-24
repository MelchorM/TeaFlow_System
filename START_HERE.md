# Start TeaFlow

Open PowerShell in `C:/Users/63905/Documents/TeaFlow` and keep MySQL running in XAMPP.

Start the website:

```powershell
.\teaflow.cmd serve
```

Open **http://127.0.0.1:3000**. In a second terminal, start the device API:

```powershell
.\teaflow.cmd iot
```

Keep both servers running for the ESP32 devices. With the current hotspot, the devices use `http://192.168.137.1:5000`. API requests require the saved device keys.

For the cracked cashier touch screen, connect the mouse and cashier USB data cable to the laptop (directly or through the hub), then run:

```powershell
.\teaflow.cmd mouse
```

Keep the mouse control window open and move inside its green area while watching the cashier screen. The current firmware uses the laptop as the USB host. BLE mouse support has not been implemented.

## Where files belong

| Folder | Contents |
| --- | --- |
| `web/frontend/` | EJS pages, CSS and browser JavaScript |
| `web/backend/` | Express server, MySQL schema, setup, tests and dependencies |
| `iot/api/` | Flask relay between ESP32 devices and Express |
| `iot/firmware/` | Cashier/kitchen firmware and shared libraries |
| `iot/tools/` | Cashier mouse bridge and tests |
| `shared/` | Menu JSON and menu images |
| `docs/` | Setup notes, project plan and progress reports |
| `archive/BESTBREW/` | Original desktop project and historical business data |
| `.tools/` | Local runtimes, private access details, backups and diagnostic helpers |

Edit web/database settings in `web/backend/.env`. Staff account details remain in `.tools/staff-access.txt`. Initial firmware settings are in `iot/firmware/cashier/config.h` and `iot/firmware/kitchen/config.h`; saved device settings still take precedence.

Open the **TeaFlow root** in VS Code for PlatformIO; its `platformio.ini` remains here.

## Verify changes

```powershell
.\teaflow.cmd test
.\.tools\python\python.exe -m unittest discover -s iot/api -p test_api.py -v
.\.tools\python\python.exe -m unittest discover -s iot/tools -p test_mouse_protocol.py -v
```

Web tests use temporary isolated databases. The `setup` command initializes a selected database; it is not a command for resetting live data.

More details: [folder guide](docs/FOLDER_GUIDE.md), [workflow and setup](docs/SETUP_AND_WORKFLOW.md), [ESP32 setup](iot/firmware/README.md), [mouse control](iot/tools/MOUSE_CONTROL.md), [project plan](docs/PROJECT_PLAN.md).
