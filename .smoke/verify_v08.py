"""Helmet v0.8 验收：真窗口 + 真鼠标 + CDP + 后端 IPC 取证。

用法：python .smoke/verify_v08.py [--stage geom|p0|all]
必须 PerMonitorV2，否则 Win32 矩形被 DPI 虚拟化。
"""
import json, os, subprocess, sys, time, ctypes

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cdp  # noqa: E402
from win_inspect import find_windows, info, hit, click, move, fg, u32  # noqa: E402
from websockets.sync.client import connect  # noqa: E402

PORT = 9222
RESULT = []
CX, CY = 1280, 764

JS_STATE = """(()=>{
 const q=s=>document.querySelector(s);
 const r=e=>{if(!e)return null;const b=e.getBoundingClientRect();
   return [Math.round(b.x),Math.round(b.y),Math.round(b.width),Math.round(b.height)]};
 const root=q('.helmet-root');
 return JSON.stringify({
  mode: root?root.dataset.mode:null, panel: root?root.dataset.panel:null,
  iw: innerWidth, ih: innerHeight,
  island:r(q('.island')), evoke:r(q('.evoke')), cabin:r(q('.island-chat')),
  rail:r(q('.rail')), panelcol:r(q('.panel-col')), search:r(q('.eave-bot')),
  islandCls:(q('.island')||{}).className||'', pct:(q('.island-pct')||{}).textContent||'',
  title:(q('.island-brand .cn')||{}).textContent||'',
  rightRail: !!(q('.rail-r')||q('.right-rail')||q('.rightbar')),
  hudVis: q('.hud')?getComputedStyle(q('.hud')).visibility:null,
  clock: (q('.island-pct')||{}).textContent||'',
  sessions: document.querySelectorAll('.sess').length,
  todos: document.querySelectorAll('.todo-row').length,
  msgs: document.querySelectorAll('.msg').length,
  hits: (window.__hits||[]).slice(-8)
 })})()"""


def js(expr, timeout=30):
    t = cdp.pick(PORT, 'Helmet')
    r = cdp.evaluate(t['webSocketDebuggerUrl'], expr, timeout=timeout)
    res = r.get('result', {})
    if res.get('exceptionDetails'):
        return 'EXC:' + json.dumps(res['exceptionDetails'], ensure_ascii=False)[:400]
    return res.get('result', {}).get('value')


def helmet_win():
    for h in find_windows('Helmet'):
        d = info(h)
        if d['class'] == 'Tauri Window':
            return d
    return None


def st():
    v = js(JS_STATE)
    if not (isinstance(v, str) and v.startswith('{')):
        return {'raw': v}
    d = json.loads(v)
    h = helmet_win()
    if h:
        W = h['rect'][2] - h['rect'][0]
        H = h['rect'][3] - h['rect'][1]
        s = (W / d['iw']) if d['iw'] else 1
        d['win'] = h['rect']
        d['win_css'] = [round(W / s), round(H / s)]
        d['scale'] = round(s, 4)
    return d


def screen_pt(rect, s, fx=0.5, fy=0.5):
    L, T = s['win'][0], s['win'][1]
    sc = s['scale']
    return (L + round((rect[0] + rect[2] * fx) * sc), T + round((rect[1] + rect[3] * fy) * sc))


def hit_at(x, y):
    h = hit(x, y)
    hl = helmet_win()
    h['is_helmet'] = bool(hl and h['root'] == hl['hwnd'])
    return h


def raise_helmet():
    hl = helmet_win()
    if not hl:
        return
    h = int(hl['hwnd'], 16)
    SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 0x2, 0x1, 0x10
    u32.SetWindowPos(h, ctypes.c_void_p(-1), 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def step(tag, ok, **kv):
    row = {'step': tag, 'ok': bool(ok)}
    row.update(kv)
    RESULT.append(row)
    print(json.dumps(row, ensure_ascii=False))


def probe_hits():
    js("""(()=>{if(window.__hits)return 'on';window.__hits=[];
      document.addEventListener('pointerdown',e=>{const t=e.target.closest?e.target.closest('.hit'):null;
        window.__hits.push((t?t.className:'none')+'@'+Math.round(e.clientX)+','+Math.round(e.clientY))},true);
      return 'armed'})()""")


def shot(name):
    """CDP 截图（透明窗只有 HUD 层，便于看视觉）"""
    try:
        t = cdp.pick(PORT, 'Helmet')
        with connect(t['webSocketDebuggerUrl'], max_size=64 * 1024 * 1024) as ws:
            ws.send(json.dumps({'id': 1, 'method': 'Page.captureScreenshot',
                                'params': {'format': 'png', 'fromSurface': True}}))
            while True:
                m = json.loads(ws.recv())
                if m.get('id') == 1:
                    import base64
                    data = m['result']['data']
                    p = os.path.join(HERE, f'v08_{name}.png')
                    with open(p, 'wb') as f:
                        f.write(base64.b64decode(data))
                    return p
    except Exception as e:  # noqa: BLE001
        return 'ERR ' + str(e)


def wait_ready(timeout=25):
    end = time.time() + timeout
    while time.time() < end:
        v = js("!!(document.querySelector('.helmet-root')&&document.querySelector('.island'))")
        if v is True:
            return True
        time.sleep(0.4)
    return False


# ---------------------------------------------------------------- geometry
def stage_geom():
    print('== G0 复位：清记忆 + reload ==')
    js("(()=>{localStorage.removeItem('rr.hud.collapsed');location.reload();return 'ok'})()")
    time.sleep(1.2)
    print('ready:', wait_ready())
    js("window.__TAURI_INTERNALS__.invoke('helmet_show').then(()=>'shown')")
    time.sleep(2.5)
    probe_hits()
    s1 = st()
    ok1 = (s1.get('mode') == 'idle' and s1.get('win') is not None
           and 800 < s1['win'][2] - s1['win'][0] < 1900
           and (s1['win'][3] - s1['win'][1]) < 140)
    step('G1-默认收起', ok1, mode=s1.get('mode'), win=s1.get('win'),
         win_css=s1.get('win_css'), island=s1.get('island'), evoke=s1.get('evoke'))

    print('== G2 收起态：中央点穿 ==')
    raise_helmet()
    move(CX, CY)
    time.sleep(0.6)
    h2 = hit_at(CX, CY)
    b = json.loads(js('JSON.stringify(window.__hits||[])') or '[]')
    click(CX, CY)
    time.sleep(0.4)
    a = json.loads(js('JSON.stringify(window.__hits||[])') or '[]')
    step('G2-收起中央点穿', (not h2['is_helmet']) and len(a) == len(b),
         hit=h2, hits_before=b, hits_after=a)

    print('== G3 点小岛 → 对话舱 ==')
    ip = screen_pt(s1['island'], s1)
    click(*ip)
    time.sleep(1.8)
    s3 = st()
    cab = s3.get('cabin') or [0, 0, 0, 0]
    full = s3.get('win_css') or [0, 0]
    step('G3-小岛开对话舱', s3.get('mode') == 'chat' and cab[2] > 380 and full[0] > 1200,
         mode=s3.get('mode'), cabin=cab, win_css=full, sessions=s3.get('sessions'),
         title=s3.get('title'), shot=shot('chat'))

    print('== G4 对话舱外点穿（舱不覆盖处）==')
    raise_helmet()
    move(500, 1150)
    time.sleep(0.7)
    h4 = hit_at(500, 1150)
    step('G4-舱外点穿', not h4['is_helmet'], hit=h4)

    print('== G5 Esc 收起 → 小窗 ==')
    js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
    time.sleep(1.4)
    s5 = st()
    step('G5-Esc 收起', s5.get('mode') == 'idle' and s5['win'][3] - s5['win'][1] < 140,
         mode=s5.get('mode'), win=s5.get('win'), win_css=s5.get('win_css'), shot=shot('idle'))

    print('== G6 点唤起 → 躯干（左轨 + 面板 + 底栏，无右栏）==')
    ep = screen_pt(s5['evoke'], s5)
    click(*ep)
    time.sleep(1.6)
    s6 = st()
    step('G6-展开躯干', s6.get('mode') == 'deck' and s6.get('rail') and s6.get('panelcol')
         and s6.get('search') and s6.get('hudVis') == 'visible' and not s6.get('rightRail'),
         mode=s6.get('mode'), rail=s6.get('rail'), panel=s6.get('panelcol'),
         search=s6.get('search'), hud=s6.get('hudVis'),
         rightRail=s6.get('rightRail'), shot=shot('deck'))

    print('== G7 躯干态中央点穿 ==')
    raise_helmet()
    move(CX, CY)
    time.sleep(0.7)
    h7 = hit_at(CX, CY)
    b7 = json.loads(js('JSON.stringify(window.__hits||[])') or '[]')
    click(CX, CY)
    time.sleep(0.4)
    a7 = json.loads(js('JSON.stringify(window.__hits||[])') or '[]')
    step('G7-躯干中央点穿', (not h7['is_helmet']) and len(a7) == len(b7),
         hit=h7, hits_before=b7, hits_after=a7)

    print('== G8 岛在躯干态仍居顶中 ==')
    s8 = st()
    isl = s8['island']
    cx_island = (s8['win'][0] + round((isl[0] + isl[2] / 2) * s8['scale']))
    step('G8-岛居中', abs(cx_island - 1280) < 40 and isl[3] < 120,
         island=isl, island_center_x=cx_island)


# ---------------------------------------------------------------- p0
JS_SET = """(sel,val)=>{const el=document.querySelector(sel); if(!el) return 'no-el';
 el.focus(); el.value=val; el.dispatchEvent(new Event('input',{bubbles:true}));
 el.dispatchEvent(new Event('change',{bubbles:true})); return el.value}"""


def set_input(sel, val):
    return js(f"(()=>{{const f={JS_SET};return f({json.dumps(sel)},{json.dumps(val)})}})()")


def enter(sel):
    return js(f"(()=>{{const el=document.querySelector({json.dumps(sel)}); if(!el) return 'no-el';"
              f"el.dispatchEvent(new KeyboardEvent('keydown',{{key:'Enter',bubbles:true,cancelable:true}}));"
              f"return 'enter'}})()")


def ipc(cmd, args=None):
    a = json.dumps(args or {})
    v = js(f"window.__TAURI_INTERNALS__.invoke({json.dumps(cmd)},{a})"
           f".then(v=>JSON.stringify(v===undefined?null:v)).catch(e=>'ERR:'+e)")
    if isinstance(v, str) and v.startswith('ERR:'):
        return {'error': v[4:]}
    try:
        return json.loads(v)
    except Exception:  # noqa: BLE001
        return v


def stage_p0():
    print('== P0-0 配置本地模拟模型（走真实后端 HTTP 流式链路）==')
    models = [{
        'id': 'mock-local',
        'name': '本地模拟',
        'provider_name': 'Mock',
        'base_url': 'http://127.0.0.1:8877/v1',
        'model': 'mock-1',
        'api_key': 'sk-smoke-mock',
        'is_default': True,
        'has_api_key': True,
    }]
    r = ipc('save_chat_models', {'models': models})
    step('P0-0-配模型', isinstance(r, list) and len(r) == 1, saved=r if isinstance(r, list) else r)

    print('== P0-1 聊天：点岛 → 新会话 → 发送 → 收流 ==')
    js("window.__TAURI_INTERNALS__.invoke('helmet_show')")
    time.sleep(1.2)
    s = st()
    if s.get('mode') == 'idle':
        click(*screen_pt(s['evoke'], s))
        time.sleep(1.2)
        s = st()
    if s.get('mode') != 'chat':
        click(*screen_pt(s['island'], s))
        time.sleep(1.6)
    # 新会话
    js("""(()=>{const b=[...document.querySelectorAll('.chat-top .btn')].find(x=>x.textContent.includes('新会话'));
      if(b){b.click();return 'new'}return 'no-btn'})()""")
    time.sleep(1.2)
    before = js("document.querySelectorAll('.sess').length")
    # 选模型 + 输入 + 发送
    js("""(()=>{const sel=document.querySelector('.chat-top select'); if(!sel) return 'no-sel';
      const opt=[...sel.options].find(o=>o.textContent.includes('本地模拟'));
      if(opt){sel.value=opt.value; sel.dispatchEvent(new Event('change',{bubbles:true}));}
      return sel.value})()""")
    set_input('.composer textarea', '验收一句话')
    js("""(()=>{const b=[...document.querySelectorAll('.composer .btn')].find(x=>x.textContent.includes('发送'));
      if(b){b.click();return 'sent'}return 'no-send'})()""")
    time.sleep(4)
    msgs = json.loads(js("""JSON.stringify([...document.querySelectorAll('.msg')].map(m=>m.textContent.trim()))""") or '[]')
    s2 = st()
    step('P0-1-聊天收发', any('MOCK-REPLY' in m for m in msgs) and s2.get('sessions', 0) >= before,
         msgs=msgs[:6], sessions=s2.get('sessions'), shot=shot('chat-sent'))
    sess = ipc('list_chat_sessions')
    n_msg = 0
    if isinstance(sess, list) and sess:
        ml = ipc('list_chat_messages', {'sessionId': sess[0]['id']})
        n_msg = len(ml) if isinstance(ml, list) else 0
    step('P0-1b-会话落库', isinstance(sess, list) and len(sess) >= 1 and n_msg >= 2,
         sessions=(len(sess) if isinstance(sess, list) else sess), messages=n_msg)

    print('== P0-2 Esc → 唤起 → 待办面板 ==')
    js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
    time.sleep(1.2)
    s = st()
    click(*screen_pt(s['evoke'], s))
    time.sleep(1.4)
    js("""(()=>{const b=[...document.querySelectorAll('.nav-btn')].find(x=>x.textContent.includes('01'));
      if(b){b.click();return 'todos'}return 'no'})()""")
    time.sleep(1.0)
    before = len(ipc('list_todos') or [])
    set_input('.panel-col .row-add .field', '头盔验收待办')
    time.sleep(0.3)
    enter('.panel-col .row-add .field')
    time.sleep(1.2)
    todos = ipc('list_todos')
    added = [t for t in (todos or []) if t.get('title') == '头盔验收待办']
    step('P0-2-待办新增落库', bool(added), count=len(todos or []), added=added[:1])

    if added:
        tid = added[0]['id']
        # 改标题（行内输入 + blur）
        js(f"""(()=>{{const inp=document.querySelector('.todo-row .tt');
          if(!inp) return 'no-row'; inp.focus(); inp.value='头盔验收待办-改名';
          inp.dispatchEvent(new Event('input',{{bubbles:true}})); inp.blur(); return 'renamed'}})()""")
        time.sleep(1.0)
        todos2 = ipc('list_todos')
        renamed = [t for t in (todos2 or []) if t.get('id') == tid and t.get('title') == '头盔验收待办-改名']
        step('P0-2b-待办改标题', bool(renamed), row=renamed[:1])
        # 完成
        js("""(()=>{const c=document.querySelector('.todo-row .chk'); if(!c) return 'no-chk'; c.click(); return 'done'})()""")
        time.sleep(1.0)
        todos3 = ipc('list_todos')
        done = [t for t in (todos3 or []) if t.get('id') == tid and t.get('done')]
        step('P0-2c-待办完成', bool(done), row=done[:1])

    print('== P0-3 笔记：新建 + 写 + 自动落盘 ==')
    js("""(()=>{const b=[...document.querySelectorAll('.nav-btn')].find(x=>x.textContent.includes('02'));
      if(b){b.click();return 'notes'}return 'no'})()""")
    time.sleep(1.8)
    js("""(()=>{const b=[...document.querySelectorAll('.work-hd .btn')].find(x=>x.textContent.includes('新建'));
      if(b){b.click();return 'created'}return 'no'})()""")
    time.sleep(1.8)
    r1 = set_input('.note-ed input.title', '头盔笔记-验收')
    time.sleep(1.2)
    r2 = set_input('.note-ed textarea', '这是头盔面板里写下的正文。' + chr(10) + '第二行。')
    time.sleep(3.0)
    st_txt = js("(document.querySelector('.note-ed .saved')||{}).textContent")
    notes = ipc('list_notes')
    hit_note = [n for n in (notes or []) if n.get('title') == '头盔笔记-验收']
    # list_notes 走 list_meta，只给元信息（content 恒为空串，设计如此）；
    # 正文必须用 get_note 单条回读，否则永远误判「没落盘」。
    full = ipc('get_note', {'noteId': hit_note[0]['id']}) if hit_note else None
    body_db = (full or {}).get('content') or ''
    step('P0-3-笔记落库', bool(full) and '头盔面板' in body_db,
         notes=len(notes or []),
         row={'id': (full or {}).get('id'), 'title': (full or {}).get('title'),
              'content': body_db, 'updated_at': (full or {}).get('updated_at')},
         r1=r1, r2=r2, status=st_txt)

    print('== P0-4 剪贴板：系统复制 → 面板取用 ==')
    subprocess.run(['powershell', '-NoProfile', '-Command',
                    "Set-Clipboard -Value 'HELMET-CLIP-验收-7788'"], capture_output=True)
    time.sleep(2.5)
    js("""(()=>{const b=[...document.querySelectorAll('.nav-btn')].find(x=>x.textContent.includes('03'));
      if(b){b.click();return 'clip'}return 'no'})()""")
    time.sleep(1.2)
    js("""(()=>{const b=[...document.querySelectorAll('.work-hd .btn')].find(x=>x.textContent.includes('刷新'));
      if(b){b.click();return 'refreshed'}return 'no'})()""")
    time.sleep(1.2)
    n_clip = js("document.querySelectorAll('.clip-item').length")
    ok_clip = isinstance(n_clip, (int, float)) and n_clip > 0
    item_text = js("(document.querySelector('.clip-item .t')||{}).textContent||''")
    step('P0-4-剪贴板列表', ok_clip, items=n_clip, first=item_text)

    if ok_clip:
        # 取用第一条 → 应回系统剪贴板并收起头盔
        js("(()=>{const b=document.querySelector('.clip-item'); if(b){b.click();return 'take'}return 'no'})()")
        time.sleep(1.6)
        s4 = st()
        got = subprocess.run(['powershell', '-NoProfile', '-Command', 'Get-Clipboard'],
                             capture_output=True, text=True).stdout.strip()
        step('P0-4b-剪贴板取用', s4.get('mode') == 'idle' and len(got) > 0,
             mode=s4.get('mode'), clipboard=got[:60])

    print('== P0-5 速达：资源落库 → 面板调起 → 回穿透区 ==')
    res = ipc('create_resource', {
        'kind': 'app', 'name': '计算器', 'target': r'C:\Windows\System32\calc.exe',
        'category': None, 'icon': None, 'args': None, 'zoneId': None,
        'description': '头盔验收用', 'remark': None, 'remarkLabel': None,
    })
    s = st()
    if s.get('mode') == 'idle':
        click(*screen_pt(s['evoke'], s))
        time.sleep(1.2)
        s = st()
    js("""(()=>{const b=[...document.querySelectorAll('.nav-btn')].find(x=>x.textContent.includes('04'));
      if(b){b.click();return 'launch'}return 'no'})()""")
    time.sleep(1.2)
    n_l = js("document.querySelectorAll('.launch-item').length")
    js("""(()=>{const b=[...document.querySelectorAll('.launch-item')].find(x=>x.textContent.includes('计算器'));
      if(b){b.click();return 'launched'}return 'no'})()""")
    time.sleep(2.5)
    s5 = st()
    ps = subprocess.run(['powershell', '-NoProfile', '-Command',
                         "Get-Process -Name CalculatorApp,calc -ErrorAction SilentlyContinue | Measure-Object | % Count"],
                        capture_output=True, text=True).stdout.strip()
    step('P0-5-速达调起', isinstance(n_l, (int, float)) and n_l > 0 and s5.get('mode') == 'idle',
         items=n_l, mode=s5.get('mode'), calc_procs=ps)
    subprocess.run(['powershell', '-NoProfile', '-Command',
                    "Stop-Process -Name CalculatorApp,calc -Force -ErrorAction SilentlyContinue"],
                   capture_output=True)

    print('== P0-6 一处搜索：待办 / 笔记 / 速达 → 直达 ==')
    s = st()
    if s.get('mode') == 'idle':
        click(*screen_pt(s['evoke'], s))
        time.sleep(1.2)
    set_input('.quick-search input', '头盔')
    time.sleep(1.2)
    js("(()=>{const el=document.querySelector('.quick-search input'); el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true})); return 'enter'})()")
    time.sleep(1.4)
    kinds = json.loads(js("JSON.stringify([...document.querySelectorAll('.search-hit .kind')].map(e=>e.textContent.trim()))") or '[]')
    step('P0-6-搜索命中', len(kinds) >= 2, kinds=kinds, shot=shot('search'))

    # 点笔记结果 → 笔记面板打开那一条
    clicked = js("""(()=>{const b=[...document.querySelectorAll('.search-hit')].find(x=>x.textContent.includes('笔记'));
      if(b){b.click();return 'note-hit'}return 'no'})()""")
    time.sleep(1.2)
    s6 = st()
    cur_title = js("(document.querySelector('.note-ed input.title')||{}).value||''")
    step('P0-6b-搜索直达笔记', s6.get('panel') == 'notes' and '头盔笔记' in str(cur_title),
         panel=s6.get('panel'), note_title=cur_title, clicked=clicked)

    print('== P0-7 上下班配置 → 岛上剩余% ==')
    js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
    time.sleep(1.2)
    s = st()
    if s.get('mode') != 'idle':
        js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
        time.sleep(1.2)
        s = st()
    js("document.querySelector('.island-gear').click()")
    time.sleep(1.4)
    set_input('.hours-pop input[type=time]', '09:00')
    js("""(()=>{const i=[...document.querySelectorAll('.hours-pop input[type=time]')][1];
      if(!i) return 'no'; i.value='18:30'; i.dispatchEvent(new Event('input',{bubbles:true})); return i.value})()""")
    time.sleep(0.2)
    js("""(()=>{const b=[...document.querySelectorAll('.hours-pop .btn')].find(x=>x.textContent.includes('保存'));
      if(b){b.click();return 'saved'}return 'no'})()""")
    time.sleep(1.4)
    ls = js("localStorage.getItem('rr.hud.hours')")
    s7 = st()
    pct = js("(document.querySelector('.island-pct')||{}).textContent||''")
    n = int(''.join(ch for ch in str(pct) if ch.isdigit()) or -1)
    step('P0-7-日衰可配', bool(ls) and 0 <= n <= 100, hours=ls, pct=pct, mode=s7.get('mode'))


if __name__ == '__main__':
    stage = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if stage in ('geom', 'all'):
        stage_geom()
    if stage in ('p0', 'all'):
        stage_p0()
    out = os.path.join(HERE, f'v08_result_{stage}.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(RESULT, f, ensure_ascii=False, indent=1)
    fails = [r['step'] for r in RESULT if not r['ok']]
    print('\n== 汇总 ==', len(RESULT) - len(fails), 'pass /', len(fails), 'fail')
    if fails:
        print('FAIL:', fails)
    print('result ->', out)