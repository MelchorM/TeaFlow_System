"""Flask device API from the IoT proposal, backed by the central Express/MySQL system."""
import hmac
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv(Path(__file__).resolve().parents[2] / 'web' / 'backend' / '.env')
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100_000
BASE_URL = os.environ.get('EXPRESS_BASE_URL', 'http://127.0.0.1:3000').rstrip('/')


@app.before_request
def authorize_device():
    supplied = request.headers.get('X-Device-Key', '')
    keys = [os.environ.get('CASHIER_DEVICE_KEY', ''), os.environ.get('KITCHEN_DEVICE_KEY', '')]
    if not supplied or not any(key and hmac.compare_digest(key, supplied) for key in keys):
        return jsonify(message='Unauthorized device.'), 401


def relay(path, method='GET'):
    body = None
    if method == 'POST':
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(message='A JSON object is required.'), 400
        body = json.dumps(data).encode('utf-8')
    headers = {'X-Device-Key': request.headers['X-Device-Key'], 'Content-Type': 'application/json', 'Accept': 'application/json'}
    if request.headers.get('X-Operator-Token'):
        headers['X-Operator-Token'] = request.headers['X-Operator-Token']
    upstream = Request(BASE_URL + '/api/iot' + path, data=body, method=method, headers=headers)
    try:
        with urlopen(upstream, timeout=2) as response:
            return app.response_class(response.read(), status=response.status, mimetype='application/json', headers={'Cache-Control': 'no-store'})
    except HTTPError as error:
        return app.response_class(error.read(), status=error.code, mimetype='application/json', headers={'Cache-Control': 'no-store'})
    except (URLError, TimeoutError, OSError):
        return jsonify(message='TeaFlow server unavailable. Action was not confirmed; refresh state before continuing.'), 503


@app.get('/iot/state')
def state():
    return relay('/state')


@app.post('/auth/login')
def login():
    return relay('/auth/login', 'POST')


@app.post('/auth/logout')
def logout():
    return relay('/auth/logout', 'POST')


@app.get('/iot/menu')
def menu():
    return relay('/menu')


@app.get('/iot/summary')
def summary():
    return relay('/summary')


@app.post('/orders')
def create_order():
    return relay('/orders', 'POST')


@app.post('/orders/<int:order_id>/pay')
def pay(order_id):
    return relay(f'/orders/{order_id}/pay', 'POST')


@app.post('/orders/<int:order_id>/status')
def status(order_id):
    return relay(f'/orders/{order_id}/status', 'POST')


if __name__ == '__main__':
    app.run(host=os.environ.get('FLASK_HOST', '127.0.0.1'), port=int(os.environ.get('FLASK_PORT', '5000')), debug=False)
