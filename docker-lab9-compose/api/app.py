"""PostgreSQL is the source of truth; Redis stores disposable user copies."""
import json
from contextlib import closing
import psycopg2
import redis
from flask import Flask, jsonify, request
from config import read_config

config = read_config()
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
cache = redis.Redis(host=config['redis_host'], port=config['redis_port'],
                    decode_responses=True, socket_connect_timeout=1,
                    socket_timeout=1)


def connect_db():
    return psycopg2.connect(**config['db'])


def user_from_row(row):
    return {'id': row[0], 'name': row[1], 'email': row[2]}


@app.errorhandler(psycopg2.Error)
def database_unavailable(error):
    app.logger.error('Database operation failed')
    return jsonify(error='database unavailable'), 503


@app.errorhandler(404)
def not_found(error):
    return jsonify(error='route not found'), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify(error='method not allowed'), 405


@app.errorhandler(413)
def body_too_large(error):
    return jsonify(error='request too large'), 413


@app.get('/')
def home():
    return jsonify(app='DevOps Lab 9 API', source_lab='Docker Compose ЛР5',
                   status='running', cache_ttl_seconds=config['cache_ttl_seconds'])


@app.get('/health')
def health():
    # Liveness intentionally does not imply readiness of external services.
    return jsonify(status='healthy', scope='http-process')


@app.get('/db-test')
def db_test():
    with closing(connect_db()) as conn:
        with conn.cursor() as cursor:
            cursor.execute('SELECT version();')
            version = cursor.fetchone()[0]
    return jsonify(status='success', database=version)


@app.get('/cache-test')
def cache_test():
    try:
        cache.set('devops:lab9:connectivity', 'test_value', ex=60)
        value = cache.get('devops:lab9:connectivity')
        if value != 'test_value':
            return jsonify(error='unexpected cache value'), 503
        return jsonify(status='success', redis='connected', test_value=value)
    except redis.RedisError:
        return jsonify(error='cache unavailable'), 503


@app.post('/users')
def create_user():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='JSON object required'), 400
    name, email = data.get('name'), data.get('email')
    if not isinstance(name, str) or not isinstance(email, str):
        return jsonify(error='name and email must be strings'), 400
    name, email = name.strip(), email.strip().lower()
    if not name or not email or len(name) > 100 or len(email) > 200 or '@' not in email:
        return jsonify(error='invalid name or email'), 400
    try:
        with closing(connect_db()) as conn:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        'INSERT INTO users(name,email) VALUES(%s,%s) '
                        'RETURNING id,name,email', (name, email))
                    user = user_from_row(cursor.fetchone())
        return jsonify(user), 201
    except psycopg2.errors.UniqueViolation:
        return jsonify(error='email already exists'), 409


@app.get('/users')
def list_users():
    with closing(connect_db()) as conn:
        with conn.cursor() as cursor:
            cursor.execute('SELECT id,name,email FROM users ORDER BY id')
            users = [user_from_row(row) for row in cursor.fetchall()]
    return jsonify(users)


@app.get('/users/<int:user_id>')
def get_user(user_id):
    key = f'devops:lab9:user:{user_id}'
    try:
        value = cache.get(key)
        if value is not None:
            return jsonify(user=json.loads(value), source='cache')
    except (redis.RedisError, json.JSONDecodeError):
        pass
    with closing(connect_db()) as conn:
        with conn.cursor() as cursor:
            cursor.execute('SELECT id,name,email FROM users WHERE id=%s', (user_id,))
            row = cursor.fetchone()
    if row is None:
        return jsonify(error='user not found'), 404
    user = user_from_row(row)
    try:
        cache.set(key, json.dumps(user), ex=config['cache_ttl_seconds'])
    except redis.RedisError:
        app.logger.warning('Cache write unavailable; response served from database')
    return jsonify(user=user, source='database')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
