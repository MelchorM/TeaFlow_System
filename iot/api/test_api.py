import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from io import BytesIO

os.environ['CASHIER_DEVICE_KEY'] = 'test-cashier'
os.environ['KITCHEN_DEVICE_KEY'] = 'test-kitchen'
spec = importlib.util.spec_from_file_location('teaflow_iot', Path(__file__).with_name('app.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeResponse:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return json.dumps({'orders': [], 'event_id': '42'}).encode()


class ApiTests(unittest.TestCase):
    def setUp(self): self.client = module.app.test_client()
    def test_unknown_device_rejected(self):
        self.assertEqual(self.client.get('/iot/state').status_code, 401)
        self.assertEqual(self.client.get('/iot/state', headers={'X-Device-Key': 'wrong'}).status_code, 401)
    @patch.object(module, 'urlopen', return_value=FakeResponse())
    def test_state_is_forwarded_without_temporary_flask_order_storage(self, upstream):
        result = self.client.get('/iot/state', headers={'X-Device-Key': 'test-kitchen'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['event_id'], '42')
        forwarded = upstream.call_args.args[0]
        self.assertTrue(forwarded.full_url.endswith('/api/iot/state'))
        self.assertEqual(forwarded.get_header('X-device-key'), 'test-kitchen')
    @patch.object(module, 'urlopen', return_value=FakeResponse())
    def test_daily_summary_route_preserves_device_identity_and_disables_cache(self, upstream):
        result = self.client.get('/iot/summary', headers={'X-Device-Key': 'test-cashier'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers['Cache-Control'], 'no-store')
        forwarded = upstream.call_args.args[0]
        self.assertTrue(forwarded.full_url.endswith('/api/iot/summary'))
        self.assertEqual(forwarded.get_header('X-device-key'), 'test-cashier')
        self.assertEqual(self.client.get('/iot/summary').status_code, 401)
    @patch.object(module, 'urlopen', return_value=FakeResponse())
    def test_payment_retry_keeps_same_order_identity(self, upstream):
        result = self.client.post('/orders/101/pay', json={}, headers={'X-Device-Key': 'test-cashier'})
        self.assertEqual(result.status_code, 200)
        forwarded = upstream.call_args.args[0]
        self.assertTrue(forwarded.full_url.endswith('/api/iot/orders/101/pay'))
        self.assertEqual(forwarded.get_method(), 'POST')
    @patch.object(module, 'urlopen', return_value=FakeResponse())
    def test_operator_token_and_login_are_relayed(self, upstream):
        result = self.client.post('/auth/login', json={'email': 'admin@test.local', 'password': 'private'}, headers={'X-Device-Key': 'test-cashier'})
        self.assertEqual(result.status_code, 200)
        self.assertTrue(upstream.call_args.args[0].full_url.endswith('/api/iot/auth/login'))
        self.client.get('/iot/state', headers={'X-Device-Key': 'test-cashier', 'X-Operator-Token': 'operator-token'})
        self.assertEqual(upstream.call_args.args[0].get_header('X-operator-token'), 'operator-token')
        self.client.post('/auth/logout', json={}, headers={'X-Device-Key': 'test-cashier', 'X-Operator-Token': 'operator-token'})
        self.assertTrue(upstream.call_args.args[0].full_url.endswith('/api/iot/auth/logout'))
    def test_non_json_object_rejected(self):
        for payload in [[], None, 'invalid']:
            self.assertEqual(self.client.post('/orders/101/status', json=payload, headers={'X-Device-Key': 'test-kitchen'}).status_code, 400)
    @patch.object(module, 'urlopen', side_effect=URLError('server unavailable'))
    def test_outage_is_reported_without_claiming_success(self, upstream):
        result = self.client.post('/orders/101/pay', json={}, headers={'X-Device-Key': 'test-cashier'})
        self.assertEqual(result.status_code, 503)
        self.assertIn('not confirmed', result.json['message'])
    @patch.object(module, 'urlopen', side_effect=HTTPError('url', 409, 'stock', {}, BytesIO(b'{"message":"Insufficient stock"}')))
    def test_upstream_stock_rejection_preserves_status(self, upstream):
        result = self.client.post('/orders/101/pay', json={}, headers={'X-Device-Key': 'test-cashier'})
        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.json['message'], 'Insufficient stock')


if __name__ == '__main__': unittest.main()
