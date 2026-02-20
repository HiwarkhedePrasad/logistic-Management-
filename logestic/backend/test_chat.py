"""Quick test script to capture the full error from /api/chat and write to file."""
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

req = Request(
    'http://127.0.0.1:8000/api/chat',
    data=json.dumps({'message': 'hello'}).encode(),
    headers={'Content-Type': 'application/json'}
)

try:
    r = urlopen(req, timeout=60)
    with open('test_output.txt', 'w', encoding='utf-8') as f:
        f.write("SUCCESS:\n")
        f.write(r.read().decode())
except HTTPError as e:
    body = e.read().decode()
    with open('test_output.txt', 'w', encoding='utf-8') as f:
        f.write(f"HTTP {e.code}\n")
        f.write(body)
except Exception as ex:
    with open('test_output.txt', 'w', encoding='utf-8') as f:
        f.write(f"Exception: {ex}\n")
        import traceback
        traceback.print_exc(file=f)

print("Done - check test_output.txt")
