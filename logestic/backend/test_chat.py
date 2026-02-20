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
        f.write("SUCCESS:\n" + r.read().decode())
except HTTPError as e:
    with open('test_output.txt', 'w', encoding='utf-8') as f:
        f.write(f"HTTP {e.code}\n" + e.read().decode())
except Exception as ex:
    import traceback
    with open('test_output.txt', 'w', encoding='utf-8') as f:
        f.write(f"Exception: {ex}\n")
        traceback.print_exc(file=f)
print("Done - check test_output.txt")
