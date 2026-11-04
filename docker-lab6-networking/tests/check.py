"""Real HTTP/network checks. Only the dedicated lab cart key is reset."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = 'http://127.0.0.1:' + os.getenv('FRONTEND_PORT', '8080')
BACKEND = 'http://127.0.0.1:' + os.getenv('BACKEND_PORT', '5000')
results = []


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def http(url, method='GET'):
    request = urllib.request.Request(url, method=method)
    try:
        response = urllib.request.urlopen(request, timeout=8)
    except urllib.error.HTTPError as error:
        response = error
    body = response.read().decode()
    return response.status, json.loads(body)


def check(name, condition, evidence):
    results.append({'name': name, 'passed': bool(condition), 'evidence': evidence})
    if not condition:
        raise AssertionError(name + ': ' + repr(evidence))


def main():
    code, products = http(FRONTEND + '/api/products')
    check('Nginx same-origin proxy returns 3 products', code == 200 and len(products) == 3, products)
    check('Source prices are 25, 15, 40', [p['price'] for p in products] == [25, 15, 40], products)
    direct_code, direct_products = http(BACKEND + '/products')
    check('Backend published on its own port', direct_code == 200 and direct_products == products,
          {'status': direct_code, 'products': direct_products})
    code, health = http(FRONTEND + '/api/health')
    check('Flask reaches Redis by DNS alias', code == 200 and health['redis'] is True, health)
    http(FRONTEND + '/api/cart', 'DELETE')
    code, empty = http(FRONTEND + '/api/cart')
    check('Reset empties dedicated demonstration cart', code == 200 and empty['count'] == 0 and empty['total'] == 0, empty)
    for product_id in (1, 2):
        code, added = http(FRONTEND + '/api/cart/add/' + str(product_id), 'POST')
        check('POST adds product ' + str(product_id), code == 201 and added['success'], added)
    code, cart = http(BACKEND + '/cart')
    check('Backend and Nginx share cart, two products total 40', code == 200 and cart['count'] == 2 and cart['total'] == 40, cart)
    code, missing = http(FRONTEND + '/api/cart/add/999', 'POST')
    check('Unknown product returns 404', code == 404, missing)
    code, unchanged = http(BACKEND + '/cart')
    check('Invalid product leaves cart unchanged', unchanged == cart, unchanged)
    http(FRONTEND + '/api/cart/add/3', 'POST')
    code, full = http(FRONTEND + '/api/cart')
    check('Three products total 80', code == 200 and full['count'] == 3 and full['total'] == 80, full)
    code, missing_route = http(BACKEND + '/not-a-route')
    check('Unknown API route returns JSON 404', code == 404, missing_route)
    dns = json.loads(command('docker', 'exec', 'devops-lab6-backend', 'python', '-c',
                     "import json,socket;print(json.dumps({n:socket.gethostbyname(n) for n in ['redis','backend','frontend']}))"))
    check('All aliases resolve in user-defined bridge', len(dns) == 3 and len(set(dns.values())) == 3, dns)
    network = json.loads(command('docker', 'network', 'inspect', 'devops-lab6-network'))[0]
    names = sorted(c['Name'] for c in network['Containers'].values())
    check('Exactly the required three containers are in bridge',
          network['Driver'] == 'bridge' and names == ['devops-lab6-backend', 'devops-lab6-frontend', 'devops-lab6-redis'], names)
    page = urllib.request.urlopen(FRONTEND + '/', timeout=5).read().decode()
    script = urllib.request.urlopen(FRONTEND + '/app.js', timeout=5).read().decode()
    check('UI and script are served; API URL is relative',
          'Docker Shop' in page and "const api = '/api'" in script, {'title': 'Docker Shop', 'api': '/api'})
    return {'dns': dns, 'network': {'name': network['Name'], 'driver': network['Driver'], 'containers': names}}


if __name__ == '__main__':
    report = {'lab': 6, 'source_lab': 'Docker Advanced ЛР2, Week4 PDF pages15–19',
              'measured_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'frontend': FRONTEND, 'backend': BACKEND, 'checks': results}
    try:
        report.update(main())
        report['passed'] = True
    except Exception as error:
        report['passed'] = False
        report['error'] = str(error)
        raise
    finally:
        target = ROOT / 'evidence' / 'checks.json'
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'passed': report['passed'], 'checks': len(results), 'report': str(target)}, ensure_ascii=False))
