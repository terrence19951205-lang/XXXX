"""shell-hub v4 本块验收（R1–R8）。

只验本块改动（侧栏两端圆角收口 / 笔记面板同款边框 / 产品名 shell-hub）与
上一会话交互是否回归（中央穿透、岛不挡主体）。
真窗口 + 真鼠标 + CDP；只起停 src-tauri/target/debug/x-hub.exe，不碰官方那份。
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
import ctypes.wintypes as wt  # noqa: E402
from win_inspect import find_windows, info, hit, click, move, u32  # noqa: E402
from websockets.sync.client import connect  # noqa: E402

PORT = 9222
RESULT = []
SW, SH = u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
CX, CY = SW // 2, SH // 2

FORBIDDEN = ['头盔工作台', '现实突袭', 'REALITY RAID']

JS_STATE = r"""(()=>{
 const q=s=>document.querySelector(s);
 const r=e=>{if(!e)return null;const b=e.getBoundingClientRect();
   return [Math.round(b.x),Math.round(b.y),Math.round(b.width),Math.round(b.height)]};
 const root=q('.helmet-root');
 const h=window.__helmet||{};
 return JSON.stringify({
  mode: root?root.dataset.mode:null,
  geo: h.geo||null, docked: h.docked===true,
  iw: innerWidth, ih: innerHeight,
  island: r(q('.island')), hot: r(q('.island-hot')), toggle: r(q('.island-toggle')),
  cabin: r(q('.island-chat')),
  rail: r(q('.rail')), panel: r(q('.panel-col')), search: r(q('.eave-bot')),
  deckOpen: !!(q('.hud')&&q('.hud').classList.contains('is-open')),
  hudVis: q('.hud')?getComputedStyle(q('.hud')).visibility:null,
  brandCn: (q('.island-brand .cn')||{}).textContent||'',
  brandEn: (q('.island-brand .en')||{}).textContent||'',
  boot: !!q('.boot')
 })})()"""


def js(expr, timeout=30):
    t = cdp.pick(PORT, 'Helmet')
    r = cdp.evaluate(t['webSocketDebuggerUrl'], expr, timeout=timeout)
    res = r.get('result', {})
    if res.get('exceptionDetails'):
        return 'EXC:' + json.dumps(res['exceptionDetails'], ensure_ascii=False)[:300]
    return res.get('result', {}).get('value')


def jsj(expr):
    v = js(expr)
    if isinstance(v, str) and v.startswith('{'):
        try:
            return json.loads(v)
        except Exception:  # noqa: BLE001
            return {'raw': v}
    return {'raw': v}


def helmet_win():
    for h in find_windows('Helmet'):
        d = info(h)
        if d['class'] == 'Tauri Window':
            return d
    return None


def main_win(pid):
    """按 pid 列出本进程的 Tauri 顶层窗（不靠标题猜，避免漏掉主窗）"""
    out = []
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def cb(hwnd, lp):
        d = info(hwnd)
        if d['pid'] == pid and d['class'] == 'Tauri Window':
            out.append(d)
        return True

    u32.EnumWindows(CB(cb), 0)
    return out


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


def shot(name, clip=None, scale=1):
    try:
        t = cdp.pick(PORT, 'Helmet')
        params = {'format': 'png', 'fromSurface': True}
        if clip:
            params['clip'] = {'x': clip[0], 'y': clip[1], 'width': clip[2],
                              'height': clip[3], 'scale': scale}
        with connect(t['webSocketDebuggerUrl'], max_size=64 * 1024 * 1024) as ws:
            ws.send(json.dumps({'id': 1, 'method': 'Page.captureScreenshot', 'params': params}))
            while True:
                m = json.loads(ws.recv())
                if m.get('id') == 1:
                    p = os.path.join(HERE, f'v4_{name}.png')
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


def skip_boot():
    end = time.time() + 12
    while time.time() < end:
        if st().get('boot'):
            break
        time.sleep(0.25)
    js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))")
    for _ in range(24):
        time.sleep(0.25)
        if not st().get('boot'):
            return True
    return False


def open_deck():
    """贴顶态 → 挪到顶部热区 → 点 ▾ 打开躯干"""
    raise_helmet()
    move(CX, CY)
    time.sleep(0.3)
    d = st()
    if d.get('mode') == 'deck':
        return d
    hot = d.get('hot') or [0, 0, 0, 0]
    move(*screen_pt(hot, d, 0.5, 0.5))
    time.sleep(0.9)
    d = st()
    tg = d.get('toggle') or [0, 0, 0, 0]
    click(*screen_pt(tg, d, 0.5, 0.5))
    time.sleep(1.5)
    return st()


def inter(a, b):
    if not a or not b:
        return 0
    x = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    y = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    return x * y


# ---------------------------------------------------------------- R1 / R2
JS_CHROME = r"""(()=>{
 const q=s=>document.querySelector(s), qa=s=>[...document.querySelectorAll(s)];
 const r=e=>{if(!e)return null;const b=e.getBoundingClientRect();
   return [Math.round(b.x),Math.round(b.y),Math.round(b.width),Math.round(b.height)]};
 const rail=q('.rail'), pc=q('.panel-col');
 const s = rail?getComputedStyle(rail):null;
 const b4 = rail?getComputedStyle(rail,'::before'):null;
 const a4 = rail?getComputedStyle(rail,'::after'):null;
 // 侧栏两端附近的装饰：任何 .fx 下可见元素，且横向压到侧栏范围
 const rr = r(rail);
 const deco = qa('.fx *').filter(e=>{
   const c=getComputedStyle(e); if(c.display==='none'||c.visibility==='hidden')return false;
   if(!e.offsetWidth&&!e.offsetHeight)return false;
   if(e.children.length>0||e.classList.contains('scan')||e.classList.contains('corners'))return false;
   const b=r(e); if(!b)return false;
   return b[0] < (rr?rr[0]+rr[2]+2:0);
 }).map(e=>({cls:String(e.className), rect:r(e)}));
 // 侧栏内部/svg 切角描边
 const svgs = qa('.rail svg').map(e=>({cls:String(e.className), disp:getComputedStyle(e).display}));
 const cornerKids = qa('.fx .corners > i').map(e=>({cls:String(e.className),
   disp:getComputedStyle(e).display}));
 return JSON.stringify({
  rail: rr,
  clip: s?s.clipPath:null,
  border: s?[s.borderTopWidth,s.borderTopStyle,s.borderTopColor,s.borderLeftWidth]:null,
  radius: s?s.borderTopLeftRadius:null,
  shadow: s?s.boxShadow:null,
  before: [b4?b4.content:null, b4?b4.display:null],
  after: [a4?a4.content:null, a4?a4.display:null],
  deco, svgs, cornerKids,
  panel: pc?r(pc):null,
  panelClip: pc?getComputedStyle(pc).clipPath:null,
  panelBorder: pc?[getComputedStyle(pc).borderTopWidth,getComputedStyle(pc).borderTopColor]:null,
  panelRadius: pc?getComputedStyle(pc).borderTopLeftRadius:null,
  panelShadow: pc?getComputedStyle(pc).boxShadow:null
 })})()"""


def hairline(w):
    """1px 边框在 150% 缩放下被换算成 0.667 设备对齐 CSS px，按「细线」判而不是死比 1px"""
    try:
        return 0 < float(str(w).replace('px', '')) <= 1.1
    except Exception:  # noqa: BLE001
        return False


def r1_r2(d):
    print('== R1/R2 侧栏两端 ==', flush=True)
    v = jsj(JS_CHROME)
    b = v.get('border') or ['', '', '', '']
    ok_rail = (v.get('clip') == 'none'
               and hairline(b[0]) and b[1] == 'solid'
               and 'rgba(0, 229, 255, 0.22)' in str(v.get('border'))
               and v.get('radius') == '12px'
               and 'inset' in str(v.get('shadow')) and '0px 8px 24px' in str(v.get('shadow'))
               and v.get('before', [None])[0] in (None, 'none', 'normal')
               and v.get('after', [None])[0] in (None, 'none', 'normal'))
    step('R1-侧栏圆角细边·无切角折线', ok_rail,
         clip=v.get('clip'), border=v.get('border'), radius=v.get('radius'),
         shadow=v.get('shadow'), before=v.get('before'), after=v.get('after'),
         rail=v.get('rail'), raw=None if ok_rail else v)
    left_deco = [x for x in (v.get('deco') or []) if x['rect'][0] < (v.get('rail') or [0, 0, 0, 0])[2]]
    kids = v.get('cornerKids') or []
    tl_bl_hidden = all(
        k['disp'] == 'none' for k in kids if k['cls'] in ('tl', 'bl')) if kids else False
    svgs_hidden = all(s['disp'] == 'none' for s in (v.get('svgs') or []))
    ok_r2 = tl_bl_hidden and svgs_hidden and not left_deco
    step('R2-两端无瞄准具/┌┘ 端饰', ok_r2,
         corner_kids=kids, tl_bl_hidden=tl_bl_hidden,
         rail_svgs=v.get('svgs'), svgs_hidden=svgs_hidden,
         left_side_fx=left_deco, shot=shot('rail', clip=[max(0, (v.get('rail') or [0, 0, 0, 0])[0] - 18),
                                                        max(0, (v.get('rail') or [0, 0, 0, 0])[1] - 18),
                                                        (v.get('rail') or [0, 0, 0, 0])[2] + 36,
                                                        (v.get('rail') or [0, 0, 0, 0])[3] + 36], scale=2))
    return v


# ---------------------------------------------------------------- R5
def r5_pierce():
    print('== R5 中央穿透未回归 ==', flush=True)
    raise_helmet()
    move(CX, CY)
    time.sleep(0.6)
    arm_hits()
    b = hits()
    hc = hit_at(CX, CY)
    click(CX, CY)
    time.sleep(0.4)
    a = hits()
    ok = (not hc['is_helmet']) and len(a) == len(b)
    step('R5-展躯干后中央仍可点穿', ok, hit=hc, hits_before=b, hits_after=a)


# ---------------------------------------------------------------- R4 / R8
def r4_r8(d):
    print('== R4/R8 笔记面板 ==', flush=True)
    js("""(()=>{const b=[...document.querySelectorAll('.nav-btn')].find(x=>/笔记/.test(x.innerText));
       b&&b.click(); return 'ok'})()""")
    time.sleep(1.4)
    v = jsj(JS_CHROME)
    pb = v.get('panelBorder') or ['', '']
    ok_border = (v.get('panelClip') == 'none'
                 and hairline(pb[0])
                 and 'rgba(0, 229, 255, 0.22)' in str(v.get('panelBorder'))
                 and v.get('panelRadius') == '12px'
                 and 'inset' in str(v.get('panelShadow')))

    # 内容是否完整落在面板内（不被切角裁掉）
    bounds = jsj(r"""(()=>{
     const q=s=>document.querySelector(s), qa=s=>[...document.querySelectorAll(s)];
     const pc=q('.panel-col'); if(!pc) return JSON.stringify({err:'no-panel'});
     const pb=pc.getBoundingClientRect();
     const r=e=>{const b=e.getBoundingClientRect();
       return [Math.round(b.x),Math.round(b.y),Math.round(b.width),Math.round(b.height)]};
     const sel='.work-hd, .work-hd .title, .work-hd .btn, .work-bd, .notes-wrap, .notes-split,'
       +' .note-list, .note-li, .note-ed, .note-ed input.title, .note-ed textarea, .note-ed .bar,'
       +' .panel-hint, .row-add, .todo-row, .launch-row, .clip-row';
     const items=qa(sel).filter(e=>{
       const c=getComputedStyle(e); if(c.display==='none'||c.visibility==='hidden')return false;
       if(!e.offsetWidth&&!e.offsetHeight)return false;
       return pc.contains(e)||e===pc;
     }).map(e=>({cls:String(e.className).slice(0,40), rect:r(e)}));
     const T=1.5;
     const out=items.filter(o=>o.rect[0]<pb.x-T||o.rect[1]<pb.y-T
       ||o.rect[0]+o.rect[2]>pb.x+pb.width+T||o.rect[1]+o.rect[3]>pb.y+pb.height+T);
     return JSON.stringify({panel:r(pc), count:items.length, out:out,
       innerText:(pc.innerText||'').replace(/\s+/g,' ').slice(0,120),
       ta:(q('.note-ed textarea')||{}).clientHeight||0,
       listN:qa('.note-li').length})})()""")
    print('bounds:', json.dumps(bounds, ensure_ascii=False), flush=True)
    ok_content = (bounds.get('count', 0) >= 5 and not bounds.get('out')
                  and (bounds.get('ta') or 0) > 60)
    pc = bounds.get('panel') or [0, 0, 0, 0]
    step('R4-笔记面板改圆角细边·无切角/瞄具',
         ok_border and ok_content,
         panel_clip=v.get('panelClip'), panel_border=v.get('panelBorder'),
         panel_radius=v.get('panelRadius'), panel_shadow=v.get('panelShadow'),
         panel=pc, content_items=bounds.get('count'), out_of_bounds=bounds.get('out'),
         textarea_h=bounds.get('ta'), note_list=bounds.get('listN'),
         shot=shot('notes', clip=[max(0, pc[0] - 24), max(0, pc[1] - 24),
                                  pc[2] + 48, pc[3] + 48], scale=1.5))

    # R8：其它工作面板（待办/剪贴板/速达）同样完整
    outs = {}
    counts = {}
    for key, label in (('todos', '待办'), ('clipboard', '剪贴板'), ('launch', '速达')):
        js("(()=>{const b=[...document.querySelectorAll('.nav-btn')].find(x=>x.innerText.indexOf(%s)>=0);"
           "b&&b.click();return 'ok'})()" % json.dumps(label))
        time.sleep(1.1)
        b2 = jsj(r"""(()=>{
         const q=s=>document.querySelector(s), qa=s=>[...document.querySelectorAll(s)];
         const pc=q('.panel-col'); if(!pc) return JSON.stringify({err:'no-panel'});
         const pb=pc.getBoundingClientRect();
         const r=e=>{const b=e.getBoundingClientRect();
           return [Math.round(b.x),Math.round(b.y),Math.round(b.width),Math.round(b.height)]};
         const items=qa('.work-hd, .work-hd .title, .work-bd, .panel-hint, .row-add, .todo-row,'
           +' .launch-row, .clip-row, .empty').filter(e=>{
           const c=getComputedStyle(e); if(c.display==='none'||c.visibility==='hidden')return false;
           if(!e.offsetWidth&&!e.offsetHeight)return false; return pc.contains(e);}).map(e=>r(e));
         const T=1.5;
         const out=items.filter(b=>b[0]<pb.x-T||b[1]<pb.y-T
           ||b[0]+b[2]>pb.x+pb.width+T||b[1]+b[3]>pb.y+pb.height+T);
         return JSON.stringify({count:items.length, out:out})})()""")
        outs[key] = b2.get('out')
        counts[key] = b2.get('count')
        print(key, json.dumps(b2, ensure_ascii=False), flush=True)

    ok_r8 = (not bounds.get('out')) and all(not v2 for v2 in outs.values()) \
        and all((c or 0) >= 2 for c in counts.values())
    step('R8-从侧栏打开各工作面板内容完整（不裁切/不挡）', ok_r8,
         notes_out=bounds.get('out'), others_out=outs, others_count=counts,
         textarea_h=bounds.get('ta'))
    # 回到笔记面板，留着后面截图
    js("""(()=>{const b=[...document.querySelectorAll('.nav-btn')].find(x=>/笔记/.test(x.innerText));
       b&&b.click(); return 'ok'})()""")
    time.sleep(1.0)


# ---------------------------------------------------------------- R6
def r6(pid):
    print('== R6 产品名 shell-hub ==', flush=True)
    txt = js("document.body.innerText||''") or ''
    brand = js("JSON.stringify([(document.querySelector('.island-brand .cn')||{}).textContent,"
               "(document.querySelector('.island-brand .en')||{}).textContent])")
    bad_body = [w for w in FORBIDDEN if w in txt]
    wins = main_win(pid) if pid else []
    # HUD 窗 label='Helmet' 是 Rust 侧内部 label（skip_taskbar + 无边框，从不显示）；
    # 只对用户能看到的窗口标题判口径
    shown = [t for t in wins if not t.get('ex_toolwindow') and t['title'] != 'Helmet']
    tlist = [t['title'] for t in wins]
    shown_titles = [t['title'] for t in shown]
    bad_title = [n for n in shown_titles if any(w.lower() in n.lower() for w in FORBIDDEN)]
    has_shell = any('shell-hub' in n.lower() for n in shown_titles)
    hw = helmet_win()
    step('R6-文案与窗口标题为 shell-hub（无旧名）',
         not bad_body and not bad_title and has_shell and 'SHELL-HUB' in (brand or ''),
         body_hits=bad_body, native_titles=tlist, shown_titles=shown_titles,
         bad_titles=bad_title, has_shell_hub=has_shell, island_brand=brand,
         hud_internal_label=(hw or {}).get('title'),
         hud_taskbar_hidden=not (hw or {}).get('ex_appwindow', True),
         shot=shot('deck'))


# ---------------------------------------------------------------- R7
def r7(d):
    print('== R7 岛不挡主体 ==', flush=True)
    o = jsj(r"""(()=>{
     const q=s=>document.querySelector(s);
     const r=e=>{if(!e)return null;const b=e.getBoundingClientRect();
       return [Math.round(b.x),Math.round(b.y),Math.round(b.width),Math.round(b.height)]};
     return JSON.stringify({island:r(q('.island')), rail:r(q('.rail')),
       panel:r(q('.panel-col')), eave:r(q('.eave-bot')), hudVis:q('.hud')?getComputedStyle(q('.hud')).visibility:null,
       mode:(q('.helmet-root')||{}).dataset?q('.helmet-root').dataset.mode:null})})()""")
    i1 = inter(o.get('island'), o.get('rail'))
    i2 = inter(o.get('island'), o.get('panel'))
    i3 = inter(o.get('island'), o.get('eave'))
    step('R7a-展躯干岛不压侧栏/面板/底栏',
         i1 == 0 and i2 == 0 and i3 == 0 and o.get('hudVis') == 'visible',
         island=o.get('island'), rail=o.get('rail'), panel=o.get('panel'),
         eave=o.get('eave'), overlaps=[i1, i2, i3])

    # 对话态
    raise_helmet()
    d1 = st()
    isl = d1.get('island') or [0, 0, 0, 0]
    click(*screen_pt(isl, d1, 0.3, 0.5))
    time.sleep(1.6)
    o2 = jsj(r"""(()=>{
     const q=s=>document.querySelector(s), qa=s=>[...document.querySelectorAll(s)];
     const r=e=>{if(!e)return null;const b=e.getBoundingClientRect();
       return [Math.round(b.x),Math.round(b.y),Math.round(b.width),Math.round(b.height)]};
     const cab=q('.island-chat');
     const kids=qa('.island-chat *').filter(e=>{const c=getComputedStyle(e);
       if(c.display==='none'||c.visibility==='hidden')return false;
       return e.offsetWidth>0&&e.offsetHeight>0;}).map(e=>r(e));
     const b=r(cab); const T=1.5;
     const out=kids.filter(k=>k[0]<b[0]-T||k[1]<b[1]-T
       ||k[0]+k[2]>b[0]+b[2]+T||k[1]+k[3]>b[1]+b[3]+T);
     return JSON.stringify({mode:(q('.helmet-root')||{}).dataset.mode,
       cabin:b, hudVis:q('.hud')?getComputedStyle(q('.hud')).visibility:null,
       out:out.slice(0,6), kids:kids.length, iw:innerWidth, ih:innerHeight})})()""")
    b = o2.get('cabin') or [0, 0, 0, 0]
    ok2 = (o2.get('mode') == 'chat' and b[2] > 380 and b[3] > 300
           and not o2.get('out') and o2.get('hudVis') != 'visible')
    step('R7b-对话舱内容完整·躯干收起不挡主体', ok2,
         mode=o2.get('mode'), cabin=b, kids=o2.get('kids'), out=o2.get('out'),
         hud_vis=o2.get('hudVis'), shot=shot('chat'))
    js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
    time.sleep(1.2)


def main():
    pid = None
    try:
        targets = cdp.list_targets(PORT)
    except Exception:  # noqa: BLE001
        targets = []
    has = any('Helmet' in (t.get('title') or '') for t in targets)
    if not has:
        pid, _ok = launch_smoke.launch('run-v4.log')
        print('launched:', pid, flush=True)
    if not wait_ready():
        print('FAIL: 头盔窗没起来', flush=True)
        return 1
    if not pid:
        hw = helmet_win()
        pid = (hw or {}).get('pid')
    time.sleep(0.8)
    skip_boot()
    d = open_deck()
    print('deck state:', json.dumps({k: d.get(k) for k in
                                     ('mode', 'deckOpen', 'rail', 'panel', 'island')},
                                    ensure_ascii=False), flush=True)
    v = r1_r2(d)
    r5_pierce()
    d = st()
    if d.get('mode') != 'deck':
        d = open_deck()
    r4_r8(d)
    r6(pid)
    r7(st())

    ok = sum(1 for r in RESULT if r['ok'])
    print('\n==== 汇总 %d/%d ====' % (ok, len(RESULT)), flush=True)
    for r in RESULT:
        print(('PASS ' if r['ok'] else 'FAIL ') + r['step'], flush=True)
    with open(os.path.join(HERE, 'v4_result.json'), 'w', encoding='utf-8') as f:
        json.dump(RESULT, f, ensure_ascii=False, indent=1)
    return 0 if ok == len(RESULT) else 2


if __name__ == '__main__':
    sys.exit(main())