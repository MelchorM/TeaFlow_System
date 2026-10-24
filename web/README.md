# TeaFlow web system

- `frontend/views/`: EJS pages and partials rendered by Express.
- `frontend/public/`: browser JavaScript and CSS, served at `/assets`.
- `backend/src/`: server routes, security, business rules, database access and schema.
- `backend/scripts/`: database initialization.
- `backend/test/`: isolated web, database and relay integration tests.
- `backend/.env`: private configuration; keep it out of shared copies.

From the TeaFlow root, run `teaflow.cmd serve` or `teaflow.cmd test`. For npm commands, work in `web/backend/`. Express serves the frontend; no separate frontend build is required.
