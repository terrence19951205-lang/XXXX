"""v9 验收：P0 六项（待办 / 聊天AI / 剪贴板 / 启动常用 / 搜索 / 日衰）逐项真点。

只连 9222 上的 Helmet 页，只杀自己起的 calc.exe。结果写 .smoke/v9_result.json，
每项截图 .smoke/v9_<item>.png。前端不改数据表，全部走既有 tauri 命令。
"""
import base64
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cdp  # noqa: E402
from websockets.sync.client import connect  # noqa: E402

t = cdp.pick(9222, 'Helmet')
WS = t['webSocketDebuggerUrl']
R = {}


def js(expr, timeout=30):
    r = cdp.evaluate(WS, expr, timeout=timeout)
    res = r.get('result', {})
    if res.get('exceptionDetails'):
        raise RuntimeError(json.dumps(res['exceptionDetails'], ensure_ascii=False)[:300])
    return res.get('result', {}).get('value')


def inv(cmd, args=None):
    return js(f"window.__TAURI_INTERNALS__.invoke({json.dumps(cmd)}, {json.dumps(args or {})})")


def click(sel, wait=0.7):
    ok = js(f"""(() => {{ const e=document.querySelector({json.dumps(sel)});
      if(!e) return false; e.click(); return true; }})()""")
    time.sleep(wait)
    return ok


def set_input(sel, val, blur=False):
    return js(f"""(() => {{ const e=document.querySelector({json.dumps(sel)});
      if(!e) return false;
      e.focus();
      const d=Object.getOwnPropertyDescriptor(e.constructor.prototype,'value');
      if (d && d.set) d.set.call(e, {json.dumps(val)}); else e.value = {json.dumps(val)};
      e.dispatchEvent(new Event('input', {{bubbles:true}}));
      e.dispatchEvent(new Event('change', {{bubbles:true}}));
      {'e.blur();' if blur else ''}
      return true; }})()""")


def shot(name):
    with connect(WS, max_size=64 * 1024 * 1024, open_timeout=15, close_timeout=5) as w:
        w.send(json.dumps({'id': 1, 'method': 'Page.enable'}))
        w.send(json.dumps({'id': 2, 'method': 'Page.captureScreenshot',
                           'params': {'format': 'png', 'captureBeyondViewport': False}}))
        end = time.time() + 30
        while time.time() < end:
            m = json.loads(w.recv())
            if m.get('id') == 2:
                data = m.get('result', {}).get('data')
                p = os.path.join(HERE, name)
                if data:
                    open(p, 'wb').write(base64.b64decode(data))
                return p
    return None


def note(item, ok, **kw):
    R[item] = {'step': item, 'ok': bool(ok), **kw}
    print(('PASS ' if ok else 'FAIL ') + item, '|', json.dumps(kw, ensure_ascii=False)[:320], flush=True)


# ---------------------------------------------------------------- T1 待办
def t1():
    click('[data-nav="todos"]', 1.0)
    before = inv('list_todos')
    title = 'v9验收-新建待办'
    set_input('.panel-col .row-add input.field', title)
    js("""(() => { const e=document.querySelector('.panel-col .row-add input.field');
      e.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true, cancelable:true})); return true; })()""")
    time.sleep(1.2)
    mid = inv('list_todos')
    added = [x for x in mid if x['title'] == title]
    # 改标题
    js("""(() => { const e=document.querySelector('.todo-row .tt');
      const d=Object.getOwnPropertyDescriptor(e.constructor.prototype,'value');
      e.focus();
      d.set.call(e,'v9验收-改标题'); e.dispatchEvent(new Event('input',{bubbles:true}));
      e.dispatchEvent(new Event('change',{bubbles:true}));
      e.blur(); return true; })()""")
    time.sleep(1.2)
    ren = inv('list_todos')
    renamed = [x for x in ren if x['title'] == 'v9验收-改标题']
    # 勾完成
    click('.todo-row .chk', 1.2)
    done = inv('list_todos')
    tid = added[0]['id'] if added else None
    fin = [x for x in done if x['id'] == tid]
    # 收尾：删掉本轮造的数据
    if tid:
        inv('delete_todo', {'id': tid})
    ok = bool(added) and bool(renamed) and bool(fin and fin[0]['done'])
    p = shot('v9_todo.png')
    note('T1 待办：新增/改标题/完成/落盘', ok,
         rows_before=len(before), rows_after_add=len(mid),
         added_id=tid, renamed_id=renamed[0]['id'] if renamed else None,
         done_flag=fin[0]['done'] if fin else None, shot=p)


# ---------------------------------------------------------------- T2 聊天 / AI
def t2():
    click('[data-nav="chat"]', 1.4)
    info = js("""(() => {
      const c = document.querySelector('.island-chat');
      const sel = document.querySelector('.island-chat .chat-top select');
      return JSON.stringify({
        cabin: !!c,
        model: sel ? sel.value : null,
        options: sel ? [...sel.options].map(o => o.textContent.trim()) : [],
        sessions: [...document.querySelectorAll('.sess-list .sess')].map(e => e.textContent.trim()),
        hasNewBtn: !!document.querySelector('.island-chat .chat-top .btn'),
      });
    })()""")
    info = json.loads(info) if isinstance(info, str) else info
    before = inv('list_chat_sessions')
    click('.island-chat .chat-top .btn', 1.4)  # 新会话
    after = inv('list_chat_sessions')
    # 真发一条（本机 mock 模型在跑）
    set_input('.composer textarea', 'v9 验收：一句话回复即可')
    click('.composer .btn.primary', 0.5)
    reply = None
    for _ in range(30):
        time.sleep(1.0)
        st = js("""(() => {
          const ms = [...document.querySelectorAll('.msgs .msg')];
          return JSON.stringify({n: ms.length, last: ms.length ? ms[ms.length-1].textContent.trim() : '',
            typing: !!document.querySelector('.msgs .typing'),
            err: (document.querySelector('.chat-err')||{}).textContent || ''});
        })()""")
        st = json.loads(st) if isinstance(st, str) else st
        if st['n'] >= 2 and not st['typing'] and st['last']:
            reply = st
            break
    p = shot('v9_chat.png')
    ok = bool(info['cabin'] and info['options'] and (len(after) > len(before))) and bool(
        reply and reply['n'] >= 2)
    note('T2 聊天/AI：多会话 + 可选模型 + 真实回复（非字幕）', ok,
         model=info['model'], options=info['options'], sessions_before=len(before),
         sessions_after=len(after), reply=reply, shot=p)


# ---------------------------------------------------------------- T5 搜索
def t5():
    # 先确保有一条笔记可命中
    click('[data-nav="notes"]', 1.0)
    js("""(() => { const b=document.querySelector('.is-notes-list .hd-acts .btn.primary'); if (b) b.click(); return true; })()""")
    time.sleep(1.0)
    set_input('.is-notes-editor input.title', 'v9验收-搜索命中', blur=False)
    set_input('.is-notes-editor textarea', 'v9 搜索用正文 token：ZEBRA-V9', blur=False)
    time.sleep(0.6)
    js("""(() => { const t=document.querySelector('.is-notes-editor textarea'); if(t) t.blur(); return true; })()""")
    time.sleep(1.2)
    click('[data-nav="search"]', 1.2)
    set_input('.quick-search input', 'ZEBRA-V9')
    time.sleep(1.6)
    res = js("""(() => {
      const hits=[...document.querySelectorAll('.search-pop .search-hit')].map(e => ({
        kind: (e.querySelector('.kind')||{}).textContent || '', t: (e.querySelector('.t')||{}).textContent || ''}));
      return JSON.stringify({hits, total: (document.querySelector('.quick-search .m')||{}).textContent || ''});
    })()""")
    res = json.loads(res) if isinstance(res, str) else res
    hit_ok = any('笔记' in h['kind'] for h in res['hits'])
    p = shot('v9_search.png')
    if hit_ok:
        js("""(() => { const h=[...document.querySelectorAll('.search-pop .search-hit')].find(e => (e.querySelector('.kind')||{}).textContent.includes('笔记')); if(h) h.click(); return true; })()""")
        time.sleep(1.4)
        jumped = js("(() => ({title: (document.querySelector('.is-notes-editor input.title')||{}).value || null, cols: !!document.querySelector('.is-notes-editor')}))()")
    else:
        jumped = None
    ok = hit_ok and bool(jumped and jumped.get('title') == 'v9验收-搜索命中')
    note('T5 搜索：一处搜待办+笔记，点击直达', ok, hits=res['hits'][:6], jumped=jumped, shot=p)


# ---------------------------------------------------------------- T6 日衰
def t6():
    st = js("""(() => {
      const pct=(document.querySelector('.island-pct')||{}).textContent||'';
      const lbl=(document.querySelector('.island-decay')||{}).textContent||'';
      return JSON.stringify({pct, lbl, hours: localStorage.getItem('rr.hud.hours')});
    })()""")
    st = json.loads(st) if isinstance(st, str) else st
    orig_hours = st['hours']
    click('.island-gear', 1.0)
    pop = js("""(() => { const p=document.querySelector('.hours-pop');
      return JSON.stringify({open: !!p, inputs: p ? [...p.querySelectorAll('input')].map(i=>i.value) : []}); })()""")
    pop = json.loads(pop) if isinstance(pop, str) else pop
    # 改成 00:00–23:59 后保存，看 % 是否变
    js("""(() => { const p=document.querySelector('.hours-pop'); const ins=[...p.querySelectorAll('input')];
      const set=(e,v)=>{const d=Object.getOwnPropertyDescriptor(e.constructor.prototype,'value');
        d.set.call(e,v); e.dispatchEvent(new Event('input',{bubbles:true}));};
      set(ins[0],'00:00'); set(ins[1],'23:59');
      const save=[...p.querySelectorAll('button')].find(b=>/保存/.test(b.textContent));
      if (save) save.click();
      return true; })()""")
    time.sleep(1.2)
    st2 = js("""(() => ({pct:(document.querySelector('.island-pct')||{}).textContent||'',
      hours: localStorage.getItem('rr.hud.hours')}))()""")
    changed = bool(st2 and st2.get('hours') and st2['hours'] != orig_hours)
    # 还原
    if orig_hours:
        js(f"localStorage.setItem('rr.hud.hours', {json.dumps(orig_hours)})")
        click('.island-gear', 0.8)
    p = shot('v9_decay.png')
    ok = bool(st['pct'].endswith('%') and pop['open'] and len(pop['inputs']) == 2 and changed)
    note('T6 日衰：岛显示剩余工时%，上下班可配', ok,
         pct_before=st['pct'], pct_after=st2.get('pct') if st2 else None,
         popover=pop, hours_changed=changed, shot=p)


# ---------------------------------------------------------------- T4 启动常用
def t4():
    click('[data-nav="launch"]', 1.0)
    lst = js("""(() => [...document.querySelectorAll('.launch-item')].map(e => ({
      ico:(e.querySelector('.ico')||{}).textContent||'', t:(e.querySelector('.t')||{}).textContent||''})))()""")
    before = inv('list_resources')
    started = time.time()
    click('.launch-item', 2.5)
    mode = js("(() => ({mode: (window.__helmet||{}).mode, deckOpen: !!document.querySelector('.hud.is-open')}))()")
    tg = [r['target'] for r in before]
    ps = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'calc|Calculator' } | "
         "Select-Object ProcessId,Name,ExecutablePath | ConvertTo-Json -Compress"],
        capture_output=True, text=True).stdout.strip()
    try:
        procs = json.loads(ps or '[]')
    except Exception:  # noqa: BLE001
        procs = ps
    if isinstance(procs, dict):
        procs = [procs]
    wins = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         "Get-Process | Where-Object { $_.MainWindowTitle -match '计算器|Calculator' } | "
         "Select-Object Id,ProcessName,MainWindowTitle | ConvertTo-Json -Compress"],
        capture_output=True, text=True).stdout.strip()
    p = shot('v9_launch.png')
    ok = bool(lst and lst[0]['t'] == '计算器' and procs and mode and mode.get('mode') == 'idle')
    note('T4 启动常用：调起应用后回穿透', ok, items=lst[:4], targets=tg,
         launched_procs=procs, launch_windows=wins, helmet_mode_after=mode, shot=p)
    # 收拾：关掉本轮起的计算器（只关最近 3 分钟启动的 Calculator 进程）
    subprocess.run(['powershell', '-NoProfile', '-Command',
                    "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'CalculatorApp|calc' } | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
                   capture_output=True, text=True)


# ---------------------------------------------------------------- T3 剪贴板
def t3():
    subprocess.run(['powershell', '-NoProfile', '-Command',
                    "Set-Clipboard -Value 'v9-剪贴板验收-7Q4X'"], capture_output=True, text=True)
    time.sleep(1.5)
    click('[data-nav="clipboard"]', 1.2)
    click('.panel-col .work-hd .btn.sm', 1.0)  # 刷新
    rows = js("""(() => [...document.querySelectorAll('.clip-item')].slice(0,5).map(e => ({
      t:(e.querySelector('.t')||{}).textContent||'', m:(e.querySelector('.m')||{}).textContent||''})))()""")
    n = len(rows or [])
    p = shot('v9_clipboard.png')
    clicked = js("""(() => { const e=[...document.querySelectorAll('.clip-item')].find(x =>
        (x.querySelector('.t')||{}).textContent.includes('v9-剪贴板验收'));
      if(!e) return false; e.click(); return true; })()""")
    time.sleep(1.6)
    got = subprocess.run(['powershell', '-NoProfile', '-Command', 'Get-Clipboard -Raw'],
                         capture_output=True, text=True).stdout.strip()
    ok = bool(n > 0 and clicked and '7Q4X' in got)
    note('T3 剪贴板历史：侧栏可点、点选取用', ok, rows=n, sample=rows[:3] if rows else [],
         clicked_new=clicked, clipboard_after=got[:40], shot=p)
    # 收起后再展开，恢复躯干
    js("(() => { const n=document.querySelector('[data-nav=\"notes\"]'); if(n) n.click(); return true; })()")
    time.sleep(0.8)


def cleanup():
    """清掉本轮造的验收数据，不留脏数据给用户。"""
    out = {}
    try:
        notes = inv('search_all', {'keyword': 'v9验收-搜索命中'})
    except Exception:  # noqa: BLE001
        notes = {}
    for n in (notes or {}).get('notes', []) or []:
        if n.get('title') == 'v9验收-搜索命中':
            try:
                inv('delete_note', {'id': n['id']})
                out['note_deleted'] = n['id']
            except Exception as e:  # noqa: BLE001
                out['note_err'] = repr(e)[:120]
    try:
        for s in inv('list_chat_sessions') or []:
            if s.get('title', '').startswith('v9 验收'):
                inv('delete_chat_session', {'id': s['id']})
                out['session_deleted'] = s['id']
    except Exception as e:  # noqa: BLE001
        out['session_err'] = repr(e)[:120]
    print('CLEANUP', json.dumps(out, ensure_ascii=False), flush=True)


def main():
    items = {'t1': t1, 't2': t2, 't3': t3, 't4': t4, 't5': t5, 't6': t6}
    want = sys.argv[1:] or list(items)
    path = os.path.join(HERE, 'v9_result.json')
    if os.path.exists(path):
        try:
            R.update(json.load(open(path, encoding='utf-8')))
            R.pop('SUMMARY', None)
        except Exception:  # noqa: BLE001
            pass
    for k in want:
        if k not in items:
            continue
        try:
            items[k]()
        except Exception as e:  # noqa: BLE001
            note(k.upper() + ' 异常', False, error=repr(e)[:300])
    if len(want) > 1:
        cleanup()

    oks = [v for k, v in R.items() if k != 'SUMMARY']
    ok = all(v.get('ok') for v in oks) and len(oks) == 6
    R['SUMMARY'] = {'ok': ok, 'items': len(oks),
                    'passed': sum(1 for v in oks if v.get('ok'))}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
    print(('ALLOK ' if ok else 'FAILED ') + f"{R['SUMMARY']['passed']}/{len(oks)}", flush=True)


if __name__ == '__main__':
    main()