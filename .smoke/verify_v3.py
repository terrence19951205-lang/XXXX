"""v3 岛交互 + ASCII 视觉 · 针对性验收（V1–V10）。

只做本轮改动相关的十条；不重跑完整 persist/P0 套件。
真窗口 + 真鼠标 + CDP；不动官方 x-hub（只有 src-tauri\\target\\debug 那份会被起停）。
"""
import base64
import ctypes
import json
import os
import sys
import time

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cdp  # noqa: E402
import launch_smoke  # noqa: E402
from win_inspect import find_windows, info, hit, click, move, u32  # noqa: E402
from websockets.sync.client import connect  # noqa: E402

PORT = 9222
RESULT = []
SW, SH = u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
CX, CY = SW // 2, SH // 2

JS_STATE = r"""(()=>{
 const q=s=>document.querySelector(s);
 const r=e=>{if(!e)return null;const b=e.getBoundingClientRect();
   return [Math.round(b.x),Math.round(b.y),Math.round(b.width),Math.round(b.height)]};
 const root=q('.helmet-root');
 const h=window.__helmet||{};
 return JSON.stringify({
  mode: root?root.dataset.mode:null,
  geo: h.geo||null, docked: h.docked===true, hover: h.hover===true, bootFlag: h.boot===true,
  iw: innerWidth, ih: innerHeight,
  island: r(q('.island')), hot: r(q('.island-hot')), lip: r(q('.island-lip-tip')),
  toggle: r(q('.island-toggle')), cabin: r(q('.island-chat')),
  rail: r(q('.rail')), panel: r(q('.panel-col')), search: r(q('.eave-bot')),
  deckOpen: !!(q('.hud')&&q('.hud').classList.contains('is-open')),
  hudVis: q('.hud')?getComputedStyle(q('.hud')).visibility:null,
  evoke: !!q('.evoke'), rightRail: !!(q('.rail-r')||q('.right-rail')),
  boot: !!q('.boot'), bootHook: window.__helmetBoot||null,
  dbg: !!q('.dbg'),
  fxOp: q('.fx')?getComputedStyle(q('.fx')).opacity:null,
  scanOp: q('.fx .scan')?getComputedStyle(q('.fx .scan')).opacity:null,
  claw: /claw/i.test(document.body.innerText||''),
  toggleChev: (q('.island-toggle .chev')||{}).textContent||'',
  pct: (q('.island-pct')||{}).textContent||''
 })})()"""


def js(expr, timeout=30):
    t = cdp.pick(PORT, 'Helmet')
    r = cdp.evaluate(t['webSocketDebuggerUrl'], expr, timeout=timeout)
    res = r.get('result', {})
    if res.get('exceptionDetails'):
        return 'EXC:' + json.dumps(res['exceptionDetails'], ensure_ascii=False)[:300]
    return res.get('result', {}).get('value')


def ipc(cmd, args=None):
    a = json.dumps(args or {})
    v = js(f"window.__TAURI_INTERNALS__.invoke({json.dumps(cmd)},{a})"
           f".then(v=>JSON.stringify(v===undefined?null:v)).catch(e=>'ERR:'+String(e))")
    if isinstance(v, str) and v.startswith('ERR:'):
        return {'error': v[4:]}
    try:
        return json.loads(v)
    except Exception:  # noqa: BLE001
        return v


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
        scale = W / (d['iw'] or 1)
        d['win'] = h['rect']
        d['scale'] = round(scale, 4)
        d['win_css'] = [round(W / scale), round(H / scale)]
        d['win_phys_h'] = H
    return d


def move_fast(x, y):
    """只挪光标不等待（用来量 450ms 收起的中间态）"""
    u32.SetCursorPos(int(x), int(y))


def screen_pt(rect, s, fx=0.5, fy=0.5):
    L, T = s['win'][0], s['win'][1]
    sc = s['scale']
    return (L + round((rect[0] + rect[2] * fx) * sc), T + round((rect[1] + rect[3] * fy) * sc))


def raise_helmet():
    hl = helmet_win()
    if not hl:
        return
    h = int(hl['hwnd'], 16)
    SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 0x2, 0x1, 0x10
    u32.SetWindowPos(h, ctypes.c_void_p(-1), 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def hit_at(x, y):
    h = hit(x, y)
    hl = helmet_win()
    h['is_helmet'] = bool(hl and h['root'] == hl['hwnd'])
    return h


def step(tag, ok, **kv):
    row = {'step': tag, 'ok': bool(ok)}
    row.update(kv)
    RESULT.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)


def shot(name):
    try:
        t = cdp.pick(PORT, 'Helmet')
        with connect(t['webSocketDebuggerUrl'], max_size=64 * 1024 * 1024) as ws:
            ws.send(json.dumps({'id': 1, 'method': 'Page.captureScreenshot',
                                'params': {'format': 'png', 'fromSurface': True}}))
            while True:
                m = json.loads(ws.recv())
                if m.get('id') == 1:
                    p = os.path.join(HERE, f'v3_{name}.png')
                    with open(p, 'wb') as f:
                        f.write(base64.b64decode(m['result']['data']))
                    return p
    except Exception as e:  # noqa: BLE001
        return 'ERR ' + str(e)


def wait_ready(timeout=40):
    end = time.time() + timeout
    while time.time() < end:
        v = js("!!(document.querySelector('.helmet-root')&&document.querySelector('.island'))")
        if v is True:
            return True
        time.sleep(0.4)
    return False


def arm_hits():
    js("""(()=>{if(window.__hits)return 'on';window.__hits=[];
      document.addEventListener('pointerdown',e=>{const t=e.target.closest?e.target.closest('.hit'):null;
        window.__hits.push((t?t.className:'none')+'@'+Math.round(e.clientX)+','+Math.round(e.clientY))},true);
      return 'armed'})()""")


def hits():
    v = js('JSON.stringify(window.__hits||[])')
    try:
        return json.loads(v)
    except Exception:  # noqa: BLE001
        return []


# ---------------------------------------------------------------- V7 开场
def v7_boot():
    print('== V7 开场 ASCII 海洋 ==', flush=True)
    # 等开场出现（窗口 show 后才放）
    saw = None
    end = time.time() + 12
    while time.time() < end:
        d = st()
        if d.get('boot'):
            saw = d
            break
        time.sleep(0.25)
    p1 = shot('boot') if saw else None
    h1 = (saw or {}).get('bootHook') or {}
    time.sleep(1.2)
    h2 = (st().get('bootHook') or {})
    moving = bool(saw) and int(h2.get('frames') or 0) > int(h1.get('frames') or 0)

    # 跳过：Enter
    js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))")
    ok_skip = False
    for _ in range(20):
        time.sleep(0.25)
        if not st().get('boot'):
            ok_skip = True
            break
    d_end = st()
    h3 = d_end.get('bootHook') or {}
    time.sleep(1.5)
    h4 = st().get('bootHook') or {}
    frozen = (h4.get('frames') == h3.get('frames')) and not h4.get('active')
    step('V7-开场鲨鱼可跳过且结束后卸载',
         bool(saw) and moving and ok_skip and frozen and not d_end.get('boot'),
         saw_boot=bool(saw), frames_1=h1.get('frames'), frames_2=h2.get('frames'),
         sharks=h2.get('sharks'), reduced=h2.get('reduced'), skipped=ok_skip,
         frames_end=h3.get('frames'), frames_after=h4.get('frames'),
         hook_end=h4, canvas_gone=not d_end.get('boot'), shot=p1)
    return d_end


# ---------------------------------------------------------------- V1..V3
def v1_v2_v3():
    print('== V1 贴顶收起 ==', flush=True)
    # 先把光标挪到屏幕中央（窗外），否则「鼠标还在岛上」本来就不该收
    raise_helmet()
    move(CX, CY)
    d = st()
    # 开场结束后 450ms 才贴顶，给足时间
    for _ in range(20):
        if d.get('docked') and (d.get('win_phys_h') or 999) < 60:
            break
        time.sleep(0.3)
        d = st()
    isl = d.get('island') or [0, 0, 0, 0]
    lip_visible = (isl[1] + isl[3]) <= 8  # 岛只剩 ≤8px 露在窗内
    hc = hit_at(CX, CY)
    step('V1-默认空闲贴顶·中央可点穿',
         d.get('geo') == 'lip' and d.get('docked') and lip_visible
         and (d.get('win_phys_h') or 999) < 60 and not hc['is_helmet'],
         geo=d.get('geo'), docked=d.get('docked'), island=isl,
         win_phys_h=d.get('win_phys_h'), win_css=d.get('win_css'),
         lip=d.get('lip'), hit_center=hc, shot=shot('docked'))

    print('== V2 顶部热区唤出 ==', flush=True)
    hot = d.get('hot') or [0, 0, 0, 0]
    x, y = screen_pt(hot, d, 0.5, 0.5)
    move(x, y)
    time.sleep(0.8)
    d2 = st()
    isl2 = d2.get('island') or [0, 0, 0, 0]
    step('V2-移到顶部热区后完整显示',
         (not d2.get('docked')) and d2.get('geo') == 'band' and isl2[3] >= 36
         and (d2.get('win_phys_h') or 0) > (d.get('win_phys_h') or 0),
         hot=hot, hover_pt=[x, y], docked=d2.get('docked'), geo=d2.get('geo'),
         island=isl2, win_phys_h=d2.get('win_phys_h'), toggle_chev=d2.get('toggleChev'),
         shot=shot('revealed'))

    print('== V3 移开 450ms 后再贴顶 ==', flush=True)
    move_fast(120, 900)
    time.sleep(0.3)
    mid = st()
    time.sleep(1.0)
    d3 = st()
    step('V3-移开后再次贴顶',
         (not mid.get('docked')) and d3.get('docked') and d3.get('geo') == 'lip'
         and (d3.get('win_phys_h') or 999) < 60,
         mid_docked=mid.get('docked'), mid_geo=mid.get('geo'),
         docked=d3.get('docked'), geo=d3.get('geo'),
         win_phys_h=d3.get('win_phys_h'), island=d3.get('island'))
    return d3


# ---------------------------------------------------------------- V4
def v4_chat(d):
    print('== V4 点岛主体 → 对话舱 ==', flush=True)
    hot = d.get('hot') or [0, 0, 0, 0]
    move(*screen_pt(hot, d, 0.5, 0.5))
    time.sleep(0.8)
    d1 = st()
    body = d1.get('island') or [0, 0, 0, 0]
    click(*screen_pt(body, d1, 0.3, 0.5))
    time.sleep(1.6)
    d2 = st()
    cab = d2.get('cabin') or [0, 0, 0, 0]
    ok = (d2.get('mode') == 'chat' and cab[2] > 380 and cab[3] > 300
          and not d2.get('claw') and d2.get('win_css', [0])[0] > 1200)
    step('V4-点岛主体开通用 AI 对话舱（无 claw）',
         ok, mode=d2.get('mode'), cabin=cab, claw=d2.get('claw'),
         win_css=d2.get('win_css'), shot=shot('chat'))

    # 收对话 → idle
    js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
    time.sleep(1.4)
    d3 = st()
    if d3.get('docked'):
        hot = d3.get('hot') or [0, 0, 0, 0]
        move(*screen_pt(hot, d3, 0.5, 0.5))
        time.sleep(0.8)
        d3 = st()
    # 点三角：必须开躯干，不能被当成开对话
    tg = d3.get('toggle') or [0, 0, 0, 0]
    click(*screen_pt(tg, d3, 0.5, 0.5))
    time.sleep(1.5)
    d4 = st()
    step('V4b-点三角不被当成开对话',
         d4.get('mode') == 'deck' and not d4.get('cabin'),
         mode_after_esc=d3.get('mode'), mode_after_toggle=d4.get('mode'),
         cabin=d4.get('cabin'), chev=d4.get('toggleChev'))
    return d4


# ---------------------------------------------------------------- V5 / V6
def v5_v6(d):
    print('== V5 ▾/▴ 展开与收回躯干 ==', flush=True)
    rail, panel, search = d.get('rail'), d.get('panel'), d.get('search')
    ok_open = (d.get('mode') == 'deck' and d.get('deckOpen') and d.get('hudVis') == 'visible'
               and rail and panel and search and not d.get('rightRail')
               and not d.get('evoke') and d.get('toggleChev') == '▴')
    shot_deck = shot('deck')

    print('== V6 躯干态中央点穿 ==', flush=True)
    raise_helmet()
    move(CX, CY)
    time.sleep(0.6)
    arm_hits()
    b = hits()
    hc = hit_at(CX, CY)
    click(CX, CY)
    time.sleep(0.4)
    a = hits()
    ok_pierce = (not hc['is_helmet']) and len(a) == len(b)
    step('V6-展开躯干后中央仍点穿·装饰不接点击',
         ok_pierce, hit=hc, hits_before=b, hits_after=a, rail=rail, panel=panel, search=search)

    # 再点 ▴ 收回
    d1 = st()
    tg = d1.get('toggle') or [0, 0, 0, 0]
    click(*screen_pt(tg, d1, 0.5, 0.5))
    time.sleep(1.4)
    d2 = st()
    ok_close = (d2.get('mode') == 'idle' and not d2.get('deckOpen')
                and not d2.get('cabin') and not d2.get('evoke'))
    step('V5-▾ 展开 / ▴ 收回·无独立展开按钮或 evoke 条',
         ok_open and ok_close, deck_open=ok_open, mode_after=d2.get('mode'),
         deck_after=d2.get('deckOpen'), evoke=d2.get('evoke'),
         hud_vis=d2.get('hudVis'), chev=d2.get('toggleChev'), shot=shot_deck)
    return d2


# ---------------------------------------------------------------- V8
def v8_rail(d):
    print('== V8 左轨两端无折线/L 形/┌┘ 端饰 ==', flush=True)
    # 需要躯干在开
    if d.get('mode') != 'deck':
        tg = d.get('toggle') or [0, 0, 0, 0]
        click(*screen_pt(tg, d, 0.5, 0.5))
        time.sleep(1.4)
    expr = r"""(()=>{const el=document.querySelector('.rail');
     if(!el) return 'no-rail';
     const b=getComputedStyle(el,'::before'), a=getComputedStyle(el,'::after'), s=getComputedStyle(el);
     const kids=[...el.children].map(c=>c.className);
     return JSON.stringify({
       beforeContent:b.content, beforeBorder:[b.borderTopWidth,b.borderLeftWidth,b.borderBottomWidth],
       beforeBg:b.backgroundImage, beforeW:b.width, beforeH:b.height,
       afterContent:a.content, afterBorder:[a.borderTopWidth,a.borderRightWidth,a.borderBottomWidth],
       afterBg:a.backgroundImage, afterW:a.width, afterH:a.height,
       railBorder:[s.borderTopWidth,s.borderBottomWidth,s.borderLeftWidth,s.borderRightWidth],
       railBorderColor:s.borderTopColor, kids,
       railText:(el.innerText||'').replace(/\s+/g,' ').slice(0,80)
     })})()"""
    v = js(expr)
    rail_ok = isinstance(v, str) and v.startswith('{')
    info_d = json.loads(v) if rail_ok else {}
    bare = all(x in ('none', 'normal', '""') for x in [info_d.get('beforeContent'), info_d.get('afterContent')])
    noborder = all(float(x.replace('px', '0')) == 0 for x in info_d.get('railBorder', ['0px']))
    step('V8-左轨无端头折线装饰',
         rail_ok and bare and noborder,
         before=info_d.get('beforeContent'), after=info_d.get('afterContent'),
         before_border=info_d.get('beforeBorder'), after_border=info_d.get('afterBorder'),
         rail_border=info_d.get('railBorder'), kids=info_d.get('kids'),
         shot=shot('rail'))


# ---------------------------------------------------------------- V9
def v9_scan(d):
    print('== V9 扫描层/角标 ==', flush=True)
    if d.get('mode') != 'deck':
        tg = d.get('toggle') or [0, 0, 0, 0]
        click(*screen_pt(tg, d, 0.5, 0.5))
        time.sleep(1.4)
    d_deck = st()
    deck_fx = d_deck.get('fxOp')
    # 收回 → idle
    tg = d_deck.get('toggle') or [0, 0, 0, 0]
    click(*screen_pt(tg, d_deck, 0.5, 0.5))
    time.sleep(1.6)
    d_idle = st()
    # 对话态
    body = d_idle.get('island') or [0, 0, 0, 0]
    if not d_idle.get('docked'):
        click(*screen_pt(body, d_idle, 0.3, 0.5))
        time.sleep(1.5)
    d_chat = st()
    js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
    time.sleep(1.2)
    ok = (float(d_deck.get('scanOp') or 0) > 0  # 躯干允许扫描层
          and float(d_idle.get('fxOp') or 1) == 0 and float(d_idle.get('scanOp') or 1) == 0
          and float(d_chat.get('fxOp') or 1) == 0 and float(d_chat.get('scanOp') or 1) == 0
          and not d_idle.get('dbg') and not d_chat.get('dbg') and not d_deck.get('dbg'))
    step('V9-对话/收起态无全屏扫描层·无 dbg 角标',
         ok, deck_fx=deck_fx, deck_scan=d_deck.get('scanOp'),
         idle_fx=d_idle.get('fxOp'), idle_scan=d_idle.get('scanOp'),
         chat_fx=d_chat.get('fxOp'), chat_scan=d_chat.get('scanOp'),
         dbg=[d_deck.get('dbg'), d_idle.get('dbg'), d_chat.get('dbg')])


# ---------------------------------------------------------------- V10
def v10_note():
    print('== V10 笔记写入 + get_note 读回 ==', flush=True)
    title = 'v3验收-岛交互笔记'
    body = '第三条岛交互验收写入的正文（ASCII 视觉与贴顶共存）。'
    created = ipc('create_note_in', {'title': title, 'content': body,
                                     'folderId': None, 'sourceUrl': None})
    nid = None
    if isinstance(created, dict):
        nid = created.get('id')
    got = ipc('get_note', {'noteId': nid}) if nid else {}
    content = (got or {}).get('content') if isinstance(got, dict) else None
    # 面板里能看到这条（走 list_notes → 同一份 SQLite）
    d = st()
    tg = d.get('toggle') or [0, 0, 0, 0]
    click(*screen_pt(tg, d, 0.5, 0.5))
    time.sleep(1.2)
    js("""(()=>{const b=[...document.querySelectorAll('.nav-btn')].find(x=>/笔记/.test(x.innerText));
       b&&b.click(); return 'ok'})()""")
    time.sleep(1.4)
    visible = js(f"document.body.innerText.indexOf({json.dumps(title)})>=0")
    step('V10-笔记写入并 get_note 读回非空正文',
         bool(nid) and isinstance(content, str) and len(content) >= 10 and visible is True,
         note_id=nid, content_len=(len(content) if isinstance(content, str) else None),
         content=content, panel_visible=visible, shot=shot('note'))
    js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
    time.sleep(1.0)


def main():
    try:
        targets = cdp.list_targets(PORT)
    except Exception:  # noqa: BLE001
        targets = []
    has = any('Helmet' in (t.get('title') or '') for t in targets)
    if not has:
        pid = launch_smoke.launch('run-v10.log')
        print('launched:', pid, flush=True)
    if not wait_ready():
        print('FAIL: 头盔窗没起来', flush=True)
        return 1
    time.sleep(0.6)
    v7_boot()
    d = v1_v2_v3()
    d = v4_chat(d)
    d = v5_v6(d)
    v8_rail(d)
    v9_scan(st())
    v10_note()

    ok = sum(1 for r in RESULT if r['ok'])
    print('\n==== 汇总 %d/%d ====' % (ok, len(RESULT)), flush=True)
    for r in RESULT:
        print(('PASS ' if r['ok'] else 'FAIL ') + r['step'], flush=True)
    with open(os.path.join(HERE, 'v3_result.json'), 'w', encoding='utf-8') as f:
        json.dump(RESULT, f, ensure_ascii=False, indent=1)
    return 0 if ok == len(RESULT) else 2


if __name__ == '__main__':
    sys.exit(main())