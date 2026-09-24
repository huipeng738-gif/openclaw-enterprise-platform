"""Smoke-test the running Compose stack against the user's actual Gateway."""
import getpass
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = 'http://127.0.0.1'

def call(path, data=None, bearer=None):
    body = json.dumps(data).encode() if data is not None else None
    headers = {'Content-Type': 'application/json'}
    if bearer:
        headers['Authorization'] = 'Bearer ' + bearer
    with urlopen(Request(BASE + path, data=body, headers=headers), timeout=10) as response:
        return response.read().decode()

def main():
    print('Checking Nginx, FastAPI, JWT, Redis and a real Gateway Agent run...')
    for attempt in range(30):
        try:
            assert 'OpenClaw 企业 AI 平台' in call('/'), 'Vue page not served'
            assert json.loads(call('/health'))['status'] == 'ok', 'FastAPI/Redis not healthy'
            break
        except (AssertionError, HTTPError, URLError):
            if attempt == 29:
                raise
            time.sleep(1)
    username = input('Login: ')
    password = getpass.getpass('Password: ')
    token = json.loads(call('/api/auth/login', {'username': username, 'password': password}))['access_token']
    created = json.loads(call('/api/tasks', {'prompt': '请只回复：联调成功', 'timeout_seconds': 120}, token))
    task_id = created['id']
    print('Task created:', task_id)
    until = time.monotonic() + 150
    while time.monotonic() < until:
        task = json.loads(call(f'/api/tasks/{task_id}', bearer=token))
        if task['status'] in ('completed', 'failed', 'cancelled', 'timed_out'):
            events = json.loads(call(f'/api/tasks/{task_id}/events', bearer=token))
            print('Status:', task['status'], 'Event count:', len(events))
            if task['status'] != 'completed' or not task.get('result'):
                raise RuntimeError(task.get('error') or 'Task completed without assistant text')
            print('Gateway response:', task['result'][:300])
            return
        time.sleep(2)
    raise RuntimeError('Smoke test timed out; inspect docker compose logs worker')

if __name__ == '__main__':
    try:
        main()
    except (AssertionError, HTTPError, URLError, RuntimeError) as exc:
        print('Verification failed:', exc, file=sys.stderr)
        raise SystemExit(1)
