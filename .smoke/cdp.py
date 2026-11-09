"""Minimal CDP client for WebView2 (--remote-debugging-port). Sync websockets."""
import json, sys, time, urllib.request
from websockets.sync.client import connect


def targets(port=9222):
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=10) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def list_targets(port=9222):
    out = []
    for t in targets(port):
        out.append({'id': t.get('id'), 'type': t.get('type'), 'title': t.get('title'), 'url': t.get('url')})
    return out


def pick(port, needle, idx=None):
    cand = [t for t in targets(port) if t.get('type') == 'page']
    if needle:
        cand = [t for t in cand if needle.lower() in (t.get('title', '') + ' ' + t.get('url', '')).lower()]
    if idx is not None:
        return cand[idx]
    if not cand:
        raise SystemExit('no target matched %r in %s' % (needle, [t.get('url') for t in targets(port)]))
    return cand[0]


def evaluate(ws_url, expr, await_promise=True, timeout=30):
    with connect(ws_url, max_size=32 * 1024 * 1024, open_timeout=15, close_timeout=5) as ws:
        mid = 1
        ws.send(json.dumps({'id': mid, 'method': 'Runtime.enable'}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get('id') == mid:
                break
        ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {
            'expression': expr, 'awaitPromise': await_promise, 'returnByValue': True,
            'allowUnsafeEvalBlockedByCSP': True, 'userGesture': True}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                ws.settimeout(2)
            except Exception:
                pass
            msg = json.loads(ws.recv())
            if msg.get('id') == 2:
                return msg


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'targets':
        print(json.dumps(list_targets(int(sys.argv[2]) if len(sys.argv) > 2 else 9222), ensure_ascii=False, indent=1))
    elif cmd == 'eval':
        port = int(sys.argv[2]); needle = sys.argv[3]; expr = sys.argv[4]
        t = pick(port, needle)
        res = evaluate(t['webSocketDebuggerUrl'], expr)
        r = res.get('result', {})
        print(json.dumps({'target': t.get('title'), 'url': t.get('url'),
                          'value': r.get('result', {}).get('value'),
                          'description': r.get('result', {}).get('description'),
                          'exception': r.get('exceptionDetails', {}).get('text') if r.get('exceptionDetails') else None},
                         ensure_ascii=False))