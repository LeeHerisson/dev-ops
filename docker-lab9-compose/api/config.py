"""Read and validate runtime configuration without logging secret values."""
import os


def port(name, default=None):
    value = os.getenv(name, default)
    try:
        parsed = int(value)
    except (ValueError, TypeError) as error:
        raise RuntimeError(name + ' must be an integer') from error
    if not 1 <= parsed <= 65535:
        raise RuntimeError(name + ' is out of range')
    return parsed


def read_config():
    required = ('DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'REDIS_HOST')
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError('Missing configuration: ' + ', '.join(missing))
    ttl = int(os.getenv('CACHE_TTL_SECONDS', '60'))
    if not 1 <= ttl <= 3600:
        raise RuntimeError('CACHE_TTL_SECONDS must be in range 1..3600')
    return {
        'db': {'host': os.environ['DB_HOST'], 'port': port('DB_PORT', '5432'),
               'dbname': os.environ['DB_NAME'], 'user': os.environ['DB_USER'],
               'password': os.environ['DB_PASSWORD'], 'connect_timeout': 3},
        'redis_host': os.environ['REDIS_HOST'],
        'redis_port': port('REDIS_PORT', '6379'),
        'cache_ttl_seconds': ttl,
    }
