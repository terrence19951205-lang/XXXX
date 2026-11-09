"""P0-8 杀进程可恢复：关掉头盔进程 → 重新起 → 数据原样回来（真 SQLite + 真窗口）。"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cdp  # noqa: E402

EXE = os.path.join(ROOT, 'src-tauri', 'target', 'debug', 'x-hub.exe')
APPDATA_DB = os.path.join(os.environ['APPDATA'], 'x-hub', 'app.db')
PORT = 9222
OUT = []


def step(name, ok, **kw):
    OUT.append({'step': name, 'ok': bool(ok), **kw})
    print(json.dumps(OUT[-1], ensure_ascii=False))


def kill():
    subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                    '-File', os.path.join(HERE, 'kill_smoke.ps1')], capture_output=True)
    time.sleep(3)


def launch():
    env = dict(os.environ)
    # 与 .smoke/tauri.smoke.json 的 additionalBrowserArgs 保持完全一致（同一串）
    cfg = json.load(open(os.path.join(HERE, 'tauri.smoke.json'), encoding='utf-8'))
    env['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = \
        cfg['app']['windows'][0]['additionalBrowserArgs']
    p = subprocess.Popen([EXE], cwd=os.path.dirname(EXE), env=env,
                         stdout=open(os.path.join(HERE, 'run-persist.log'), 'w'),
                         stderr=subprocess.STDOUT)
    for _ in range(60):
        time.sleep(1)
        try:
            ts = cdp.list_targets(PORT)
            if any('Helmet' in (t.get('title') or '') for t in ts):
                time.sleep(3)
                return p.pid, True
        except Exception:  # noqa: BLE001
            pass
    return p.pid, False


def js(expr):
    t = cdp.pick(PORT, 'Helmet')
    r = cdp.evaluate(t['webSocketDebuggerUrl'], expr)
    return r['result']['result'].get('value')


def shot(name):
    import base64
    t = cdp.pick(PORT, 'Helmet')
    from websockets.sync.client import connect  # 与 verify_v08 同一客户端库
    with connect(t['webSocketDebuggerUrl'], max_size=64 * 1024 * 1024) as ws:
        ws.send(json.dumps({'id': 1, 'method': 'Page.captureScreenshot',
                            'params': {'format': 'png', 'captureBeyondViewport': False}}))
        while True:
            m = json.loads(ws.recv())
            if m.get('id') == 1:
                data = base64.b64decode(m['result']['data'])
                p = os.path.join(HERE, f'v08_{name}.png')
                open(p, 'wb').write(data)
                return p


def main():
    before = os.path.getmtime(APPDATA_DB) if os.path.exists(APPDATA_DB) else None
    print('== 关闭头盔进程 ==')
    kill()
    print('== 重新启动（同一 exe，portable data/）==')
    pid, up = launch()
    step('P8-0-重启存活', up, pid=pid)
    if not up:
        json.dump(OUT, open(os.path.join(HERE, 'v08_result_persist.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        return

    print('== 点唤起 → 待办面板 ==')
    js("(()=>{const e=document.querySelector('.evoke'); if(e) e.click();})()")
    time.sleep(1.5)
    js("""(()=>{const b=[...document.querySelectorAll('.nav-btn')].find(x=>x.textContent.includes('01'));
      if(b) b.click();})()""")
    time.sleep(1.2)
    rows = json.loads(js("JSON.stringify([...document.querySelectorAll('.todo-row')].map(r=>r.textContent.trim()))") or '[]')
    # 已完成的待办默认不在「未完成」页签显示，DOM 行数为 0 不代表丢数据；
    # 以 DB（list_todos）为准，DOM 行与页签计数作为旁证。
    db_todos = json.loads(js("window.__TAURI_INTERNALS__.invoke('list_todos')"
                             ".then(v=>JSON.stringify(v||[]))") or '[]')
    counts = js("(()=>{const t=document.querySelector('.panel-col');"
                "return t?t.innerText.replace(/\\s+/g,' ').slice(0,80):''})()")
    step('P8-1-待办存活', any('头盔' in (t.get('title') or '') for t in db_todos),
         rows=rows[:4], counts=counts,
         db=[{'id': t['id'], 'title': t['title'], 'done': t['done']} for t in db_todos][:4])

    js("""(()=>{const b=[...document.querySelectorAll('.nav-btn')].find(x=>x.textContent.includes('02'));
      if(b) b.click();})()""")
    time.sleep(1.5)
    body = js("(document.querySelector('.note-ed textarea')||{}).value||''")
    title = js("(document.querySelector('.note-ed input.title')||{}).value||''")
    step('P8-2-笔记可续写', '头盔' in str(title) and len(str(body)) > 0, title=title, body=str(body)[:40])

    js("""(()=>{const b=[...document.querySelectorAll('.nav-btn')].find(x=>x.textContent.includes('03'));
      if(b) b.click();})()""")
    time.sleep(1.5)
    js("""(()=>{const b=[...document.querySelectorAll('.work-hd .btn')].find(x=>x.textContent.includes('刷新'));
      if(b) b.click();})()""")
    time.sleep(1.2)
    clips = json.loads(js("JSON.stringify([...document.querySelectorAll('.clip-item .t')].map(e=>e.textContent.trim()))") or '[]')
    step('P8-3-剪贴板存活', any('HELMET-CLIP' in c for c in clips), clips=clips[:3])

    js("""(()=>{const b=[...document.querySelectorAll('.nav-btn')].find(x=>x.textContent.includes('04'));
      if(b) b.click();})()""")
    time.sleep(1.5)
    items = json.loads(js("JSON.stringify([...document.querySelectorAll('.launch-item')].map(e=>e.textContent.trim()))") or '[]')
    step('P8-4-速达存活', any('计算器' in i for i in items), items=items[:4])

    print('== 岛上剩余工时（localStorage 配置是否留存）==')
    pct = js("(document.querySelector('.island-pct')||{}).textContent||''")
    step('P8-5-日衰配置存活', '%' in str(pct), pct=pct, shot=shot('persist'))

    after = os.path.getmtime(APPDATA_DB) if os.path.exists(APPDATA_DB) else None
    step('P8-6-正式库未动', before == after, appdata_mtime_before=before, appdata_mtime_after=after)

    json.dump(OUT, open(os.path.join(HERE, 'v08_result_persist.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    fails = [r['step'] for r in OUT if not r['ok']]
    print('\n== 汇总 ==', len(OUT) - len(fails), 'pass /', len(fails), 'fail', fails)


if __name__ == '__main__':
    main()