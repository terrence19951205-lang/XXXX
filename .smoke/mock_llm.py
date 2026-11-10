"""最小 OpenAI 兼容 SSE 服务：只用于头盔 POC 冒烟（真实 HTTP + 流式）。
不参与产品，跑在 127.0.0.1:8877。

两个档：
1) 普通对话（请求里没有 tools）→ 回文本，验证流式渲染。
2) 智能体（请求里带 tools，且上下文里还没有 tool 结果）→ 回一个 create_todo 的
   tool_calls，让后端走「写操作 → 审批 → 执行」整条链；拿到 tool 结果后回文本收尾。
   ——这样审批卡片是真的由后端 permissionMode 触发，不是在界面上假造的。
"""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def _sse(self, obj):
        self.wfile.write(('data: ' + json.dumps(obj, ensure_ascii=False) + '\n\n').encode())
        self.wfile.flush()

    def _chunk(self, delta, finish=None, usage=None):
        obj = {
            'id': 'mock-1', 'object': 'chat.completion.chunk',
            'created': int(time.time()), 'model': 'mock-1',
            'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}],
        }
        if usage:
            obj['usage'] = usage
        self._sse(obj)

    def _text(self, parts):
        for c in parts:
            self._chunk({'content': c})
            time.sleep(0.1)
        self._chunk({}, 'stop', {'prompt_tokens': 9, 'completion_tokens': 5, 'total_tokens': 14})
        self.wfile.write(b'data: [DONE]\n\n')
        self.wfile.flush()

    def _tool_call(self):
        args = json.dumps({'title': '【自测】AI 建的待办', 'priority': 1}, ensure_ascii=False)
        self._chunk({
            'tool_calls': [{
                'index': 0, 'id': 'call_mock_1', 'type': 'function',
                'function': {'name': 'create_todo', 'arguments': ''},
            }],
        })
        for piece in (args[:20], args[20:]):
            self._chunk({
                'tool_calls': [{'index': 0, 'function': {'arguments': piece}}],
            })
            time.sleep(0.05)
        self._chunk({}, 'tool_calls', {'prompt_tokens': 20, 'completion_tokens': 8, 'total_tokens': 28})
        self.wfile.write(b'data: [DONE]\n\n')
        self.wfile.flush()

    def do_POST(self):
        n = int(self.headers.get('content-length') or 0)
        raw = self.rfile.read(n)
        try:
            req = json.loads(raw or b'{}')
        except Exception:
            req = {}
        msgs = req.get('messages') or []
        has_tool_result = any(m.get('role') == 'tool' for m in msgs)
        wants_tools = bool(req.get('tools'))
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'close')
        self.end_headers()
        if wants_tools and not has_tool_result:
            self._tool_call()
        else:
            self._text(['MOCK-REPLY ', '小岛', '流式', '链路 ', 'OK'])

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