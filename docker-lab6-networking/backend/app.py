"""The shop API uses Redis by its network alias, never by a hard-coded IP."""
import json
import os
from flask import Flask, jsonify
import redis

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
store = redis.Redis(host=os.getenv('REDIS_HOST', 'redis'),
                    port=int(os.getenv('REDIS_PORT', '6379')),
                    decode_responses=True, socket_connect_timeout=2,
                    socket_timeout=2)
CART_KEY = 'devops:lab6:cart'
PRODUCTS = [
    {'id': 1, 'name': 'Docker T-Shirt', 'price': 25},
    {'id': 2, 'name': 'Kubernetes Mug', 'price': 15},
    {'id': 3, 'name': 'DevOps Book', 'price': 40},
]


@app.errorhandler(redis.RedisError)
def redis_unavailable(error):
    app.logger.warning('Redis is unavailable')
    return jsonify(error='cart storage unavailable'), 503


@app.get('/health')
def health():
    return jsonify(status='ok', redis=bool(store.ping()))


@app.get('/products')
def products():
    return jsonify(PRODUCTS)


@app.post('/cart/add/<int:product_id>')
def add_to_cart(product_id):
    product = next((item for item in PRODUCTS if item['id'] == product_id), None)
    if product is None:
        return jsonify(error='product not found'), 404
    store.rpush(CART_KEY, json.dumps(product))
    return jsonify(success=True, product=product), 201


@app.get('/cart')
def get_cart():
    items = [json.loads(value) for value in store.lrange(CART_KEY, 0, -1)]
    return jsonify(count=len(items), total=sum(item['price'] for item in items),
                   items=items)


@app.delete('/cart')
def clear_cart():
    store.delete(CART_KEY)
    return jsonify(success=True, count=0, total=0)


@app.errorhandler(404)
def not_found(error):
    return jsonify(error='route not found'), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
