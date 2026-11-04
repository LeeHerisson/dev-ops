"""Real behavior checks, controlled dependency outages and down/up persistence.

Only resources of the fixed devops-lab9 Compose project are touched.
One uniquely named synthetic user is retained on each successful run.
"""
import datetime
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ['docker', 'compose', '--project-directory', str(ROOT), '-f', str(ROOT / 'compose.yaml')]
settings = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines()
                if line and not line.startswith('#'))
BASE = 'http://127.0.0.1:' + settings.get('API_PORT', '5059')
checks = []
commands = []
safe_settings = {key: value for key, value in settings.items() if key != 'DB_PASSWORD'}


def run(*args, compose=False):
    command = COMPOSE + list(args) if compose else list(args)
    process = subprocess.run(command, text=True, capture_output=True)
    output = process.stdout.strip()
    commands.append({'command': command, 'exit_code': process.returncode,
                     'stdout': output, 'stderr': process.stderr.strip()})
    if process.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(command))
    return output


def http(path, method='GET', payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(BASE + path, data=data, method=method,
                                     headers={'Content-Type': 'application/json'})
    try:
        response = urllib.request.urlopen(request, timeout=12)
    except urllib.error.HTTPError as error:
        response = error
    return response.status, json.loads(response.read())


def check(name, condition, evidence):
    checks.append({'name': name, 'passed': bool(condition), 'evidence': evidence})
    if not condition:
        raise AssertionError(name + ': ' + repr(evidence))


def redis_cli(*args):
    return run('exec', '-T', 'redis', 'redis-cli', *args, compose=True)


def snapshot():
    raw = json.loads(run('docker', 'inspect', 'devops-lab9-api', 'devops-lab9-db', 'devops-lab9-redis'))
    # Inspect contains secrets in Config.Env. Never serialize raw inspect.
    commands[-1]['stdout'] = '[raw inspect filtered; no environment values stored]'
    return {item['Name'].lstrip('/'): {
        'id': item['Id'], 'image': item['Image'],
        'status': item['State']['Status'],
        'health': item['State'].get('Health', {}).get('Status'),
        'mounts': [{key: mount[key] for key in ('Type', 'Name', 'Destination') if key in mount}
                   for mount in item['Mounts']],
        'networks': list(item['NetworkSettings']['Networks']),
    } for item in raw}


def main():
    for path in ('/', '/health', '/db-test', '/cache-test'):
        code, body = http(path)
        check('GET ' + path, code == 200, {'status': code, 'body': body})
    unique = uuid.uuid4().hex[:12]
    user_payload = {'name': 'Alice persistence ' + unique, 'email': 'alice-' + unique + '@example.com'}
    code, user = http('/users', 'POST', user_payload)
    check('POST /users saves in PostgreSQL', code == 201 and user['name'] == user_payload['name'], {'status': code, 'body': user})
    user_id = user['id']
    key = f'devops:lab9:user:{user_id}'
    code, users = http('/users')
    check('GET /users includes new record', code == 200 and user in users, {'count': len(users), 'created': user})
    code, from_db = http('/users/' + str(user_id))
    check('Cache miss reads PostgreSQL', code == 200 and from_db['source'] == 'database' and from_db['user'] == user, from_db)
    code, from_cache = http('/users/' + str(user_id))
    check('Second GET reads Redis copy', code == 200 and from_cache['source'] == 'cache' and from_cache['user'] == user, from_cache)
    ttl = int(redis_cli('TTL', key))
    check('Cached copy has bounded positive TTL', 0 < ttl <= int(settings['CACHE_TTL_SECONDS']), {'ttl_seconds': ttl})
    code, duplicate = http('/users', 'POST', user_payload)
    check('Duplicate email returns 409', code == 409, duplicate)
    for name, invalid in [('missing fields', {}), ('array', []), ('wrong types', {'name': 1, 'email': 'a@b'}),
                          ('empty name', {'name': ' ', 'email': 'a@b'}), ('invalid email', {'name': 'A', 'email': 'none'})]:
        code, body = http('/users', 'POST', invalid)
        check('Invalid POST ' + name + ' returns 400', code == 400, body)
    code, absent = http('/users/2147483647')
    check('Missing user returns 404', code == 404, absent)
    code, absent_route = http('/unknown')
    check('Unknown route returns JSON 404', code == 404, absent_route)
    code, bad_method = http('/users', 'DELETE')
    check('Unsupported method returns JSON 405', code == 405, bad_method)

    redis_cli('EXPIRE', key, '1')
    time.sleep(1.2)
    code, expired = http('/users/' + str(user_id))
    check('Expired copy is read again from database', code == 200 and expired['source'] == 'database', expired)
    dns = json.loads(run('exec', '-T', 'api', 'python', '-c',
                         "import json,socket;print(json.dumps({n:socket.gethostbyname(n) for n in ['db','redis']}))", compose=True))
    check('API resolves DB and Redis by service names', len(dns) == 2 and dns['db'] != dns['redis'], dns)

    run('stop', 'redis', compose=True)
    try:
        code, offline_cache = http('/cache-test')
        check('Cache health is 503 during Redis outage', code == 503, offline_cache)
        code, fallback = http('/users/' + str(user_id))
        check('User read falls back to DB while Redis is stopped', code == 200 and fallback['source'] == 'database' and fallback['user'] == user, fallback)
    finally:
        run('up', '-d', '--wait', '--wait-timeout', '60', 'redis', compose=True)

    run('stop', 'db', compose=True)
    try:
        code, offline_db = http('/db-test')
        check('DB check is 503 during PostgreSQL outage', code == 503, offline_db)
        code, liveness = http('/health')
        check('Liveness remains HTTP-process liveness', code == 200 and liveness['scope'] == 'http-process', liveness)
    finally:
        run('up', '-d', '--wait', '--wait-timeout', '60', 'db', compose=True)

    marker_key = 'devops:lab9:persistence:' + unique
    redis_cli('SET', marker_key, unique)
    before = snapshot()
    check('All three containers healthy before recreation', all(item['health'] == 'healthy' for item in before.values()), before)
    run('down', compose=True)  # Intentionally no -v: this is the persistence experiment.
    run('up', '-d', '--wait', '--wait-timeout', '120', compose=True)
    after = snapshot()
    check('Containers really replaced, not merely restarted', all(before[name]['id'] != after[name]['id'] for name in before),
          {'before': {name: item['id'] for name, item in before.items()}, 'after': {name: item['id'] for name, item in after.items()}})
    check('Named volumes unchanged across down/up', all(before[name]['mounts'] == after[name]['mounts'] for name in before),
          {name: item['mounts'] for name, item in after.items()})
    code, restored_users = http('/users')
    check('PostgreSQL record survives new containers', code == 200 and user in restored_users, {'created_record': user, 'count_after': len(restored_users)})
    marker_value = redis_cli('GET', marker_key)
    check('Redis AOF marker survives new Redis container', marker_value == unique, {'key': marker_key, 'value': marker_value})
    aof = redis_cli('CONFIG', 'GET', 'appendonly')
    check('Redis AOF enabled', aof.splitlines()[-1] == 'yes', aof)
    # Restore a useful cached record and ensure normal API behavior after recovery.
    code, recovered = http('/users/' + str(user_id))
    check('API works after full recreation', code == 200 and recovered['user'] == user, recovered)
    return {'user': user, 'before_recreation': before, 'after_recreation': after, 'dns': dns}


if __name__ == '__main__':
    report = {'lab': 9, 'source_lab': 'Docker Compose PDF ЛР5 pages22–29',
              'measured_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'base_url': BASE, 'configuration_without_password': safe_settings,
              'checks': checks, 'commands': commands}
    try:
        report.update(main())
        report['passed'] = True
    except Exception as error:
        report['passed'] = False
        report['error'] = str(error)
        raise
    finally:
        destination = ROOT / 'evidence' / 'checks.json'
        # Defensive redaction also covers unexpected engine/Compose error output.
        serialized = json.dumps(report, ensure_ascii=False, indent=2)
        serialized = serialized.replace(settings['DB_PASSWORD'], '[REDACTED]')
        destination.write_text(serialized + '\n')
        print(json.dumps({'passed': report['passed'], 'checks': len(checks), 'report': str(destination)}, ensure_ascii=False))
