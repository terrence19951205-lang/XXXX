"""v8 透明度对照取证：开侧栏 + 笔记三栏，截一张（改前/改后同名脚本）。

用法: python .smoke/v8_shot.py v8_before_opacity.png
只连 9222 上的 Helmet 页，不启停进程。
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cdp  # noqa: E402

PORT = 9222


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else 'v8_shot.png'
    t = cdp.pick(PORT, 'Helmet')
    ws = t['webSocketDebuggerUrl']

    def js(expr):
        r = cdp.evaluate(ws, expr)
        res = r.get('result', {})
        if res.get('exceptionDetails'):
            raise RuntimeError(json.dumps(res['exceptionDetails'], ensure_ascii=False)[:300])
        return res.get('result', {}).get('value')

    # 展开躯干 + 打开笔记列表与编辑栏
    js("""(() => {
      const nav = document.querySelector('[data-nav="notes"]');
      if (nav && !document.querySelector('.is-notes-list')) nav.click();
      return !!nav;
    })()""")
    time.sleep(1.0)
    js("""(() => { const r = document.querySelector('.note-row'); if (r) r.click(); return !!r; })()""")
    time.sleep(1.0)

    probe = js("""(() => {
      const g = el => el ? getComputedStyle(el) : null;
      const rail = document.querySelector('.rail');
      const list = document.querySelector('.is-notes-list');
      const ed = document.querySelector('.is-notes-editor');
      const island = document.querySelector('.island');
      const pick = (el, k) => el ? g(el)[k] : null;
      const r = el => el ? el.getBoundingClientRect() : null;
      const rect = el => { const b = r(el); return b ? [Math.round(b.width), Math.round(b.height)] : null; };
      return JSON.stringify({
        railBg: pick(rail, 'backgroundImage'), railBorder: pick(rail, 'borderTopWidth'),
        railColor: pick(rail, 'borderTopColor'), railRadius: pick(rail, 'borderTopLeftRadius'),
        railBlur: pick(rail, 'backdropFilter'),
        listBg: pick(list, 'backgroundImage'), listRadius: pick(list, 'borderTopLeftRadius'),
        listRect: rect(list), edRect: rect(ed),
        islandBg: pick(island, 'backgroundImage'),
        rows: document.querySelectorAll('.note-row').length,
        threeCols: !!list && !!ed && (rect(list) || [0])[0] > 200 && (rect(ed) || [0])[0] > 300,
      });
    })()""")

    import base64
    path = os.path.join(HERE, name)
    r = cdp.evaluate(ws, "1")  # warm
    # 截图走独立 CDP 命令
    from websockets.sync.client import connect
    with connect(ws, max_size=64 * 1024 * 1024, open_timeout=15, close_timeout=5) as w:
        w.send(json.dumps({'id': 1, 'method': 'Page.enable'}))
        w.send(json.dumps({'id': 2, 'method': 'Page.captureScreenshot',
                           'params': {'format': 'png', 'captureBeyondViewport': False}}))
        end = time.time() + 30
        data = None
        while time.time() < end:
            m = json.loads(w.recv())
            if m.get('id') == 2:
                data = m.get('result', {}).get('data')
                break
    if data:
        with open(path, 'wb') as f:
            f.write(base64.b64decode(data))
    print('SHOT', path if data else 'FAILED')
    print('PROBE', probe)


if __name__ == '__main__':
    main()