# Flask IoT API

This implements the supporting Flask API named in the IoT proposal. It forwards device requests to the central Node.js/Express backend and MySQL database. It does not duplicate order, payment, or inventory state in Python memory.

Launch from the TeaFlow root with `teaflow.cmd iot`. Configuration and role-specific device keys are loaded from the ignored `web/backend/.env` file.

| Flask request | Central Express request |
| --- | --- |
| `POST /auth/login` | `POST /api/iot/auth/login` |
| `POST /auth/logout` | `POST /api/iot/auth/logout` |
| `GET /iot/menu` | `GET /api/iot/menu` |
| `GET /iot/state` | `GET /api/iot/state` |
| `GET /iot/summary` | `GET /api/iot/summary` (cashier only) |
| `POST /orders` | `POST /api/iot/orders` |
| `POST /orders/{id}/pay` | `POST /api/iot/orders/{id}/pay` |
| `POST /orders/{id}/status` | `POST /api/iot/orders/{id}/status` |

Every request requires `X-Device-Key`. POST bodies must be JSON objects. The cashier touchscreen now operates directly with its cashier device key and does not require account login or `X-Operator-Token`. Device-only payment records have `paid_by=NULL`; the order and stock audit records remain intact. Browser account login and role restrictions are unchanged.

For older clients, the optional `/auth/login` and `/auth/logout` endpoints remain compatible. If `X-Operator-Token` is explicitly supplied, the server checks its expiry, binding to the device key, and the current admin/cashier role; invalid/expired tokens return 401 and revoked roles return 403. Valid optional tokens attribute payment to that user. Omitting a token uses the device's role. Logout itself requires an explicit valid token.

Authenticated cashier requests can create orders, confirm payment, and complete ready orders. The kitchen key can read paid orders and set Preparing/Ready without an operator token. Express validates each action again. The local HTTP relay is for the trusted demonstration LAN.

Creation body example (replace IDs with real values from `/iot/menu`):

```json
{
  "request_key": "ba6b14bd-efac-4ad8-b63e-cc2c995e85aa",
  "customer_name": "Walk-in Customer",
  "lines": [{"variant_id": 1, "quantity": 1, "sugar": 50, "ice": "light", "addon_ids": []}]
}
```

Payment body: `{}`. Status body: `{"status":"preparing"}` or `{"status":"ready"}`; a cashier completes a ready order with `{"status":"completed"}`.

State responses include `server_time` (ISO UTC) and `server_unix` (whole Unix seconds from the same server clock). Device orders include `paid_at_unix` (whole UTC Unix seconds, or null while unpaid). These additive fields let the kitchen calculate waiting minutes from the original payment after a restart, without requiring a separate ESP32 wall clock. The relay forwards them unchanged. Ready orders remain in both active queues until cashier completion; the cashier derives its persistent ready notice from those records.

Reuse the same `request_key` and payload when retrying creation. Reuse the saved order ID for payment/status retries. A request timeout is not proof that the database action failed; refresh state and retry the same identity as needed. Upstream failures return their rejection status, and connection failures return HTTP 503 without claiming success.

Summary responses contain `day` (YYYY-MM-DD), `timezone` (`Asia/Manila`), `paid_orders`, `drinks_sold`, `total_cents` and `generated_at` (ISO UTC). They aggregate all orders paid within that Manila day, including completed orders and both channels, independently of the active-queue limit. Unpaid orders are excluded. The kitchen key returns 403. Responses disable caching; the cashier labels any retained older snapshot if refresh fails.

`requirements.lock.txt` records the verified local package versions. Eight Flask unit tests and 27 web/database tests passed, including a real relay/Express/MySQL integration test, summary permissions and Manila payment-day boundaries.
