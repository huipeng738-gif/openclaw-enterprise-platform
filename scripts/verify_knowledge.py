"""Verify authenticated chat, the real Worker, knowledge tool and WebSocket."""
import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
import websockets


def credentials():
    configured = {}
    env_file = Path(__file__).resolve().parents[1] / '.env'
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8-sig').splitlines():
            name, separator, value = line.partition('=')
            if separator and name in {'VERIFY_USERNAME', 'VERIFY_PASSWORD'}:
                configured[name] = value.strip().strip('\"\'')
    username = os.getenv('VERIFY_USERNAME') or configured.get('VERIFY_USERNAME') or input('Login: ')
    password = os.getenv('VERIFY_PASSWORD') or configured.get('VERIFY_PASSWORD') or getpass.getpass('Password: ')
    return username, password


async def verify(base_url, query, username, password, skill=None):
    async with httpx.AsyncClient(base_url=base_url, timeout=15, trust_env=False) as client:
        login = await client.post('/api/auth/login', json={'username': username, 'password': password})
        if login.status_code != 200:
            raise RuntimeError(f'Login failed: HTTP {login.status_code}')
        client.headers['Authorization'] = 'Bearer ' + login.json()['access_token']
        prompt = ('You MUST call knowledge_search with query ' + json.dumps(query)
                  + ' and top_k 3. Answer briefly from retrieved content and cite actual document names.')
        if skill == 'enterprise-knowledge-qa':
            prompt = f'请使用 enterprise-knowledge-qa Skill 回答企业知识问题：{query}。请检索实际资料并列出真实来源。'
        elif skill == 'enterprise-document-draft':
            prompt = f'请使用 enterprise-document-draft Skill，围绕“{query}”起草一份简短制度说明。请先检索资料，并列出来源和待确认事项。'
        created = await client.post('/api/chat', json={
            'prompt': prompt,
            'timeout_seconds': 150,
        })
        if created.status_code != 202:
            raise RuntimeError(f'Chat submission failed: HTTP {created.status_code}')
        task_id = created.json()['id']
        print('Task created:', task_id, flush=True)
        ticket_response = await client.post(f'/api/tasks/{task_id}/ws-ticket')
        if ticket_response.status_code != 200:
            raise RuntimeError(f'WebSocket ticket failed: HTTP {ticket_response.status_code}')
        url = urlsplit(base_url)
        ws_url = urlunsplit(('wss' if url.scheme == 'https' else 'ws', url.netloc,
                           f'/ws/tasks/{task_id}', urlencode({'ticket': ticket_response.json()['ticket']}), ''))
        events = []
        terminal = None
        async with asyncio.timeout(180):
            async with websockets.connect(ws_url, proxy=None) as ws:
                async for raw in ws:
                    message = json.loads(raw)
                    if message.get('type') == 'event':
                        events.append(message['event'])
                    elif message.get('type') == 'snapshot':
                        task = message['task']
                        if task['status'] in {'completed', 'failed', 'cancelled', 'timed_out'}:
                            terminal = task
        if not terminal or terminal['status'] != 'completed':
            raise RuntimeError('Task did not complete successfully')
        if not terminal.get('result') or not terminal.get('sources'):
            raise RuntimeError('Completed task is missing its answer or document sources')
        tools = [event for event in events if event.get('kind') == 'tool'
                 and event.get('name') == 'knowledge_search']
        if not any(event.get('phase') == 'start' for event in tools):
            raise RuntimeError('WebSocket did not deliver knowledge_search start')
        if not any(event.get('phase') == 'result' and event.get('resultCount', 0) > 0 for event in tools):
            raise RuntimeError('WebSocket did not deliver successful retrieval results')
        if not all(source.get('document_id') and source.get('document_name')
                   and source.get('knowledge_base_id') for source in terminal['sources']):
            raise RuntimeError('Document sources are incomplete')
        replay = await client.get(f'/api/tasks/{task_id}/events')
        if replay.status_code != 200 or not any(event.get('name') == 'knowledge_search' for event in replay.json()):
            raise RuntimeError('Persisted task events are missing the knowledge tool')
        print(f'PASS: completed; WebSocket events={len(events)}; sources={len(terminal["sources"])}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1')
    parser.add_argument('--query', default='test knowledge base')
    parser.add_argument('--skill', choices=['enterprise-knowledge-qa', 'enterprise-document-draft'],
                        help='通过原有聊天任务链验收 Skill 场景；需使用有实际命中的问题')
    args = parser.parse_args()
    try:
        user, secret = credentials()
        asyncio.run(verify(args.base_url, args.query, user, secret, args.skill))
    except RuntimeError as exc:
        print('FAIL:', exc)
        raise SystemExit(1)
    except (httpx.HTTPError, websockets.WebSocketException, TimeoutError) as exc:
        # Exception messages may contain a WebSocket URL with its one-use ticket.
        print('FAIL:', type(exc).__name__)
        raise SystemExit(1)
