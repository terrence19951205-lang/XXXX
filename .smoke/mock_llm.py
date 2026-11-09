"""最小 OpenAI 兼容 SSE 服务：只用于头盔对话链路冒烟（真实 HTTP + 流式）。
不参与产品，跑在 127.0.0.1:8877。
"""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def _sse(self, obj):
        self.wfile.write(('data: ' + json.dumps(obj, ensure_ascii=False) + '\n\n').encode())
        self.wfile.flush()

    def do_POST(self):
        n = int(self.headers.get('content-length') or 0)
        raw = self.rfile.read(n)
        try:
            req = json.loads(raw or b'{}')
        except Exception:
            req = {}
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'close')
        self.end_headers()
        for c in ['MOCK-REPLY ', '小岛', '流式', '链路 ', 'OK']:
            self._sse({
                'id': 'mock-1', 'object': 'chat.completion.chunk',
                'created': int(time.time()), 'model': 'mock-1',
                'choices': [{'index': 0, 'delta': {'content': c}, 'finish_reason': None}],
            })
            time.sleep(0.12)
        self._sse({
            'id': 'mock-1', 'object': 'chat.completion.chunk',
            'created': int(time.time()), 'model': 'mock-1',
            'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 9, 'completion_tokens': 5, 'total_tokens': 14},
        })
        self.wfile.write(b'data: [DONE]\n\n')
        self.wfile.flush()

    def do_GET(self):
        body = b'{"ok":true}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    print('mock llm on 127.0.0.1:8877', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8877), H).serve_forever()