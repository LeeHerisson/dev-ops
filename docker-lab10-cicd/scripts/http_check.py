"""HTTP smoke test реального контейнера, без Flask test client."""
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

base = sys.argv[1].rstrip("/")


def request(path, data=None):
    body = None if data is None else json.dumps(data).encode()
    req = Request(base + path, data=body, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=3) as response:
            return response.status, json.load(response)
    except HTTPError as response:
        return response.code, json.load(response)


for attempt in range(60):
    try:
        if request("/health") == (200, {"status": "ok"}):
            break
    except (URLError, TimeoutError, ConnectionError):
        pass
    time.sleep(0.5)
else:
    raise SystemExit("API did not become ready")

assert request("/todos") == (200, [])
status, todo = request("/todos", {"title": "Docker smoke test"})
assert status == 201 and todo == {"id": 1, "title": "Docker smoke test", "done": False}
assert request("/todos") == (200, [todo])
assert request("/todos", {})[0] == 400
assert request("/todos", ["invalid"])[0] == 400
print(json.dumps({"status": "passed", "health": "ok", "created_id": todo["id"],
                  "invalid_requests": [400, 400]}, indent=2))
