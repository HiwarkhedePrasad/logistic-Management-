import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

req = Request(
    'http://127.0.0.1:8000/api/chat',
    data=json.dumps({'message': 'generate a report of all schedule risks'}).encode(),
    headers={'Content-Type': 'application/json'}
)
try:
    r = urlopen(req, timeout=120)
    resp = r.read().decode()
    with open('test_report_output.txt', 'w', encoding='utf-8') as f:
        f.write("SUCCESS:\n" + resp)
    print("SUCCESS")
    data = json.loads(resp)
    print(f"Response: {data.get('response', '')[:500]}")
except HTTPError as e:
    body = e.read().decode()
    with open('test_report_output.txt', 'w', encoding='utf-8') as f:
        f.write(f"HTTP {e.code}\n" + body)
    print(f"HTTP ERROR {e.code}: {body[:500]}")
except Exception as ex:
    import traceback
    with open('test_report_output.txt', 'w', encoding='utf-8') as f:
        f.write(f"Exception: {ex}\n")
        traceback.print_exc(file=f)
    print(f"Exception: {ex}")
