# TeaFlow folder guide

Run all `teaflow.cmd` commands from the project root. Website URLs, device keys, database names and order workflows are unchanged by the folder organization.

```text
TeaFlow/
  START_HERE.md
  teaflow.cmd                 # serve, iot, mouse, test, setup
  cashier-mouse.cmd           # direct mouse launcher
  platformio.ini              # PlatformIO entry point for VS Code
  web/
    frontend/
      public/                 # browser JavaScript and CSS
      views/                  # EJS pages and partials
    backend/
      src/                    # Express routes, business rules, MySQL schema
      scripts/                # database setup
      test/                   # web/database/integration tests
      .env                    # private server and device settings
      package.json
      package-lock.json
      node_modules/           # installed dependencies
  iot/
    api/                      # Flask relay, requirements and tests
    firmware/
      cashier/                # 5-inch cashier application
      kitchen/                # 3.5-inch kitchen application and audio
      libraries/              # shared client and board drivers
      platformio/             # firmware entry point
      display-test/
      kitchen-display-test/
    tools/                    # laptop mouse bridge and protocol tests
  shared/
    catalog/                  # menu seed JSON
    assets/menu/              # product images
  docs/
    PROJECT_PLAN.md
    SETUP_AND_WORKFLOW.md
    reports/                  # dated Word reports, preserved
  archive/
    BESTBREW/                 # original project; original inner structure preserved
  .tools/                     # local runtimes, private helpers, logs, QA and backups
  .pio/                       # generated PlatformIO build/dependency files
  .vscode/                    # VS Code settings
```

The frontend is rendered by Express, so it does not need a separate frontend server or a second npm installation. Run npm commands from `web/backend/`, or use the root launcher.

## Old paths and new paths

| Previous location | Current location |
| --- | --- |
| `web/public`, `web/views` | `web/frontend/public`, `web/frontend/views` |
| `web/src`, `web/scripts`, `web/test` | Same folders inside `web/backend/` |
| Web `.env`, package files and `node_modules` | `web/backend/` |
| `iot-api/` | `iot/api/` |
| `firmware/` | `iot/firmware/` |
| `tools/` | `iot/tools/` |
| `catalog/`, `assets/` | `shared/catalog/`, `shared/assets/` |
| `PROJECT_PLAN.md`, `reports/` | `docs/PROJECT_PLAN.md`, `docs/reports/` |
| `BESTBREW/` | `archive/BESTBREW/` |

Historical Word reports retain their original contents and may mention paths from before this reorganization. Use this table to locate those files.

## Preserved data and cleanup

The MySQL database, orders, passwords, device keys, firmware private configuration, menu images, historical desktop database/exports and progress reports are preserved. Device flash and saved device settings were not changed.

A pre-change source/configuration backup and checksums are in `.tools/backups/organization-2026-10-23/`. This backup contains private configuration and must stay private. The archive folder is reference material; it is not served by the website.

Cleanup removes redundant downloaded LibreOffice installers, the completed installer extraction log, and Python bytecode caches. The extracted report-rendering tool, local runtimes, npm/PlatformIO dependencies, vendor reference resources, reports and QA evidence are retained.


## Verification on 23 October 2026

- 27 web/database/integration tests, eight Flask tests and eleven mouse protocol tests passed (46 total).
- Cashier and kitchen PlatformIO builds succeeded from the root configuration. No device upload was performed for this folder-only change.
- The relocated mouse launcher passed its command-line startup check.
- Seven live web/page/asset checks, all 43 menu images and the authenticated IoT relay passed read-only checks.
- Both devices resumed successful API polling after the server restart. Device-driven order creation, preparation, readiness and handover continued during verification.
- All 261 backed-up files were accounted for after the moves. The 178 protected configuration, frontend, menu, report and original-business files checked against their original hashes were unchanged.
- Both baseline orders remain in history with unchanged order contents, totals and payment timestamps; their statuses advanced through normal device activity.
- Removed 421,484,831 bytes (about 402 MiB) of regenerable installers/logs/caches. Build and runtime caches can be generated again normally.

The backup folder also records the path mapping, cleanup list and verification snapshots. The web and Flask servers were left running from their new locations.
