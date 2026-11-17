"""shell-hub B1–B5 验收：开场 = 探索稿 v3 的 ASCII 鲨鱼海洋，岛/侧栏/品牌回归。

对照物：
  .refs/reality-raid-hud-v08-ascii-explore-v3.html   开场（AsciiSharks.OceanEngine）+ 岛交互
  .refs/reality-raid-hud-v08-ascii-explore-v4.html   侧栏圆角细边

只起停 src-tauri/target/debug/x-hub.exe（冒烟构建），不碰官方发行版进程。
真窗口 + 真鼠标 + CDP；结果写 .smoke/v5_result.json，截图 .smoke/v5_*.png。
"""
import base64
import ctypes
import json
import os
import sys
import time

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
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
EXE = os.path.join(ROOT, 'src-tauri', 'target', 'debug', 'x-hub.exe')

# 探索稿 v3 原样抄下来的四条鲨
WANT_KINDS = ['classic', 'mako', 'hammerhead', 'thresher']


def js(expr, timeout=30):
    t = cdp.pick(PORT, 'Helmet')
    r = cdp.evaluate(t['webSocketDebuggerUrl'], expr, timeout=timeout)
    res = r.get('result', {})
    if res.get('exceptionDetails'):
        return 'EXC:' + json.dumps(res['exceptionDetails'], ensure_ascii=False)[:300]
    return res.get('result', {}).get('value')


def jsj(expr):
    v = js(expr)
    if isinstance(v, str) and v.startswith(('{', '[', 'null')):
        try:
            return json.loads(v)
        except Exception:  # noqa: BLE001
            return {'raw': v}
    return {'raw': v}


def shot(name, clip=None):
    try:
        t = cdp.pick(PORT, 'Helmet')
        params = {'format': 'png', 'fromSurface': True}
        if clip:
            params['clip'] = {'x': clip[0], 'y': clip[1], 'width': clip[2], 'height': clip[3], 'scale': 1}
        with connect(t['webSocketDebuggerUrl'], max_size=64 * 1024 * 1024) as ws:
            ws.send(json.dumps({'id': 1, 'method': 'Page.captureScreenshot', 'params': params}))
            while True:
                m = json.loads(ws.recv())
                if m.get('id') == 1:
                    p = os.path.join(HERE, f'v5_{name}.png')
                    with open(p, 'wb') as f:
                        f.write(base64.b64decode(m['result']['data']))
                    return p
    except Exception as e:  # noqa: BLE001
        return 'ERR ' + str(e)


def helmet_win():
    """HUD 窗 = class 'Tauri Window' 且内部标题正好是 'Helmet' 的那个。
    注意：主窗标题是 'shell-hub (helmet smoke)'，子串匹配 'Helmet' 会把它也捞进来，
    坐标一错点击就落到几百像素外（踩过）。"""
    cand = [info(h) for h in find_windows('Helmet')]
    cand = [d for d in cand if d['class'] == 'Tauri Window']
    for d in cand:
        if d['title'].strip().lower() == 'helmet':
            return d
    return cand[0] if cand else None


def win_titles(pid):
    out = []

    class W:
        pass
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def cb(hwnd, lp):
        d = info(hwnd)
        if d['pid'] == pid:
            out.append({'title': d['title'], 'class': d['class'],
                        'visible': bool(u32.IsWindowVisible(hwnd))})
        return True

    u32.EnumWindows(CB(cb), 0)
    return out


JS_BOOT = r"""(()=>{
 const q=s=>document.querySelector(s);
 const r=e=>{if(!e)return null;const b=e.getBoundingClientRect();
   return [Math.round(b.x),Math.round(b.y),Math.round(b.width),Math.round(b.height)]};
 const b=q('.rra-boot'), cv=q('.rra-boot-ocean'), bar=q('.rra-boot-bar i');
 const h=window.__helmetBoot||null;
 return JSON.stringify({
  boot: !!b,
  cls: b?b.className:null,
  canvas: r(cv),
  canvasPix: cv?[cv.width,cv.height]:null,
  titleCn: (q('.rra-boot-title .cn')||{}).textContent||'',
  titleEn: (q('.rra-boot-title .en')||{}).textContent||'',
  hint: (q('.rra-boot-title .hint')||{}).textContent||'',
  capB: (q('.rra-boot-cap b')||{}).textContent||'',
  capSpan: (q('.rra-boot-cap span')||{}).textContent||'',
  skip: (q('.rra-skip')||{}).textContent||'',
  barW: bar?bar.style.width:null,
  barTransition: bar?bar.style.transition:null,
  hook: h,
  iw: innerWidth, ih: innerHeight
 })})()"""

JS_UI = r"""(()=>{
 const q=s=>document.querySelector(s), qa=s=>[...document.querySelectorAll(s)];
 const r=e=>{if(!e)return null;const b=e.getBoundingClientRect();
   return [Math.round(b.x),Math.round(b.y),Math.round(b.width),Math.round(b.height)]};
 const root=q('.helmet-root'), h=window.__helmet||{};
 const rail=q('.rail'), pc=q('.panel-col');
 const rs=rail?getComputedStyle(rail):null, ps=pc?getComputedStyle(pc):null;
 const rb=rail?getComputedStyle(rail,'::before'):null, ra=rail?getComputedStyle(rail,'::after'):null;
 return JSON.stringify({
  mode: root?root.dataset.mode:null,
  geo: h.geo||null, docked: h.docked===true,
  island: r(q('.island')), hot: r(q('.island-hot')), toggle: r(q('.island-toggle')),
  cabin: r(q('.island-chat')), chev: (q('.island-toggle')||{}).textContent||'',
  rail: r(rail), panel: r(pc),
  railBorder: rs?[rs.borderTopWidth,rs.borderTopStyle,rs.borderTopColor,rs.borderRadius]:null,
  railClip: rs?rs.clipPath:null,
  railBefore: rb?rb.display:null, railAfter: ra?ra.display:null,
  panelBorder: ps?[ps.borderTopWidth,ps.borderTopColor,ps.borderRadius]:null,
  panelClip: ps?ps.clipPath:null,
  brandCn: (q('.island-brand .cn')||{}).textContent||'',
  brandEn: (q('.island-brand .en')||{}).textContent||'',
  bodyXhub: (document.body.innerText.match(/x-hub/gi)||[]).length,
  boot: !!q('.rra-boot')
 })})()"""


def ui():
    d = jsj(JS_UI)
    h = helmet_win()
    if h and 'iw' not in d:
        pass
    if h and isinstance(d, dict) and 'raw' not in d:
        W = h['rect'][2] - h['rect'][0]
        H = h['rect'][3] - h['rect'][1]
        d['win'] = h['rect']
        d['win_phys'] = [W, H]
    return d


def screen_pt(rect, d, fx=0.5, fy=0.5):
    h = helmet_win()
    L, T = h['rect'][0], h['rect'][1]
    iw = js('innerWidth') or 1
    sc = (h['rect'][2] - h['rect'][0]) / iw
    return (L + round((rect[0] + rect[2] * fx) * sc), T + round((rect[1] + rect[3] * fy) * sc))


def raise_helmet():
    hl = helmet_win()
    if hl:
        u32.SetForegroundWindow(hl['hwnd'])
        time.sleep(0.2)


def wait_ready(timeout=45):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if js("!!(document.querySelector('.helmet-root')&&document.querySelector('.island'))") is True:
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.4)
    return False


def add(step, ok, **kw):
    RESULT.append({'step': step, 'ok': bool(ok), **kw})
    print(('PASS ' if ok else 'FAIL ') + step, flush=True)


# --------------------------------------------------------------- B1 开场
def arm_boot():
    """还没看到开场？把本会话的开场标记清掉，再 hide→show 重新触发 helmet-shown。"""
    js("(()=>{try{sessionStorage.removeItem('rr.hud.bootPlayed')}catch(e){};return 1})()")
    js("window.__TAURI_INTERNALS__.invoke('helmet_hide')")
    time.sleep(0.8)
    js("window.__TAURI_INTERNALS__.invoke('helmet_show')")


def b1():
    # 开场可能在 wait_ready 之后才起（helmet_show → bootActive）
    end = time.time() + 8
    d = {}
    while time.time() < end:
        d = jsj(JS_BOOT)
        if d.get('boot'):
            break
        time.sleep(0.2)
    armed = False
    if not d.get('boot'):
        armed = True
        arm_boot()
        end = time.time() + 8
        while time.time() < end:
            d = jsj(JS_BOOT)
            if d.get('boot'):
                break
            time.sleep(0.2)
    if not d.get('boot'):
        add('B1-开场出现', False, state=d)
        return

    time.sleep(0.6)
    d1 = jsj(JS_BOOT)
    h1 = d1.get('hook') or {}
    p1 = shot('boot')

    time.sleep(0.9)
    d2 = jsj(JS_BOOT)
    h2 = d2.get('hook') or {}
    p2 = shot('boot2')

    cv = d1.get('canvas') or [0, 0, 0, 0]
    full = abs(cv[2] - d1.get('iw', 0)) <= 2 and abs(cv[3] - d1.get('ih', 0)) <= 2
    add('B1-a 开场铺满 + 品牌 shell-hub + 跳过可点',
        d1.get('titleCn', '').strip().lower() == 'shell-hub'
        and 'SHELL HUB' in d1.get('titleEn', '').upper()
        and '移动指针搅动洋流' in d1.get('hint', '')
        and 'Enter' in d1.get('skip', '') and 'Esc' in d1.get('skip', '')
        and full,
        titleCn=d1.get('titleCn'), titleEn=d1.get('titleEn'), hint=d1.get('hint'),
        skip=d1.get('skip'), canvas=cv, viewport=[d1.get('iw'), d1.get('ih')],
        bar=d1.get('barTransition'), armed=armed, shot=p1)

    add('B1-b 引擎就是探索稿那套 AsciiSharks.OceanEngine',
        h1.get('engine') == 'AsciiSharks.OceanEngine'
        and bool(h1.get('engineClass'))
        and h1.get('sharkKinds') == WANT_KINDS
        and h1.get('sharks') == 4
        and not h1.get('reduced'),
        hook=h1, shot=p2)

    add('B1-c 海洋真在跑：帧数增长 + 画面出墨（不是空 canvas）',
        isinstance(h1.get('frames'), int) and isinstance(h2.get('frames'), int)
        and h2['frames'] > h1['frames']
        and (h2.get('ink') or 0) >= 0.01,
        frames=[h1.get('frames'), h2.get('frames')],
        ink=[h1.get('ink'), h2.get('ink')],
        barWidth=d2.get('barW'), shot=p2)

    # 跳过
    js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))")
    gone = False
    for _ in range(20):
        time.sleep(0.2)
        d = jsj(JS_BOOT)
        if not d.get('boot') and not js("!!document.querySelector('.rra-boot-ocean')"):
            gone = True
            break
    d3 = jsj(JS_BOOT)
    h3 = d3.get('hook') or {}
    time.sleep(0.7)
    d4 = jsj(JS_BOOT)
    h4 = d4.get('hook') or {}
    add('B1-d Enter 跳过 → 海洋卸载、组件拆除、帧数冻结',
        gone and h3.get('tornDown') is True and h3.get('active') is False
        and h4.get('frames') == h3.get('frames') and h3.get('sharks') == 0,
        gone=gone, hook=h3, hook_after=h4, shot=shot('after_boot'))


# --------------------------------------------------------------- B2 岛
def to_idle():
    """任何浮层都按 Esc 回空闲（v3 的岛只在 idle 才贴顶/展开）"""
    for _ in range(3):
        d = ui()
        if d.get('mode') == 'idle':
            return d
        js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
        time.sleep(0.9)
    return ui()


def hover_hot(tries=3):
    """把指针送进顶部热区，等岛从来回贴顶状态展开成完整行"""
    for _ in range(tries):
        d = ui()
        if d.get('geo') == 'band':
            return d
        hot = d.get('hot') or [0, 0, 0, 0]
        p = screen_pt(hot, d, 0.5, 0.5)
        move(p[0] - 40, p[1] + 120)   # 先真正离开，再进入，确保有一次 hover 位移
        time.sleep(0.25)
        move(*p)
        time.sleep(0.9)
        d = ui()
        if d.get('geo') == 'band':
            return d
    return ui()


def b2():
    # 不再自己 invoke('helmet_show')：后端与前端会同时 setSize，两路抢窗会把窗口缩成一条。
    # 开场结束后应用本来就会贴顶成 lip，直接做真实鼠标交互即可。
    raise_helmet()
    move(CX, CY)
    time.sleep(0.7)
    d = to_idle()
    docked_ok = d.get('docked') is True and d.get('geo') == 'lip'
    d2 = hover_hot()
    band_ok = d2.get('docked') is False and d2.get('geo') == 'band' and d2.get('chev', '').strip() == '▾'
    p = shot('revealed')

    # ▾ 展开躯干
    d3 = d2
    for _ in range(2):
        tg = d3.get('toggle') or [0, 0, 0, 0]
        pt = screen_pt(tg, d3, 0.5, 0.5)
        move(*pt)
        time.sleep(0.2)
        click(*pt)
        time.sleep(1.3)
        d3 = ui()
        if d3.get('mode') == 'deck':
            break
    deck_ok = d3.get('mode') == 'deck' and d3.get('chev', '').strip() == '▴'
    p2 = shot('deck')

    js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
    time.sleep(1.0)
    d4 = ui()
    esc_ok = d4.get('mode') == 'idle'

    # 点岛主体 → 对话舱
    d5 = to_idle()
    if d5.get('geo') != 'band':
        d5 = hover_hot()
    d6 = d5
    for _ in range(2):
        isl = d6.get('island') or [0, 0, 0, 0]
        pt = screen_pt(isl, d6, 0.55, 0.5)
        move(*pt)
        time.sleep(0.25)
        click(*pt)
        time.sleep(1.3)
        d6 = ui()
        if d6.get('mode') == 'chat':
            break
    chat_ok = d6.get('mode') == 'chat' and bool(d6.get('cabin'))
    p3 = shot('chat')
    js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
    time.sleep(0.9)
    add('B2-贴顶/顶部热区/▾开躯干/Esc收回/点岛开对话 对齐 v3',
        docked_ok and band_ok and deck_ok and esc_ok and chat_ok,
        docked=[d.get('geo'), d.get('docked')],
        band=[d2.get('geo'), d2.get('docked'), d2.get('chev')],
        deck=[d3.get('mode'), d3.get('chev')],
        after_esc=[d4.get('mode')],
        chat=[d6.get('mode'), d6.get('cabin')],
        shots=[p, p2, p3])


# --------------------------------------------------------------- B3 侧栏 / B4 品牌
def b3_b4(pid):
    d = ui()
    if d.get('mode') != 'deck':
        to_idle()
        d = hover_hot()
        for _ in range(2):
            tg = d.get('toggle') or [0, 0, 0, 0]
            pt = screen_pt(tg, d, 0.5, 0.5)
            move(*pt)
            time.sleep(0.2)
            click(*pt)
            time.sleep(1.3)
            d = ui()
            if d.get('mode') == 'deck':
                break
    # 打开笔记面板
    js("document.querySelector('.rail .nav-btn:nth-of-type(1)')?.click()")
    time.sleep(0.8)
    d = ui()
    p = shot('sidebar')

    rb = d.get('railBorder') or []
    ok_b3 = (
        d.get('railClip') in ('none', '')
        and d.get('railBefore') == 'none' and d.get('railAfter') == 'none'
        and len(rb) == 4 and 'rgba(0, 229, 255, 0.22)' in (rb[2] or '') and rb[3] == '12px'
        and (d.get('panelClip') in ('none', ''))
        and 'rgba(0, 229, 255, 0.22)' in ((d.get('panelBorder') or ['', '', ''])[1] or '')
        and (d.get('panelBorder') or ['', '', ''])[2] == '12px'
    )
    add('B3-侧栏/笔记面板圆角细边、无折线切角（v4）',
        ok_b3, rail=d.get('rail'), railBorder=rb, railClip=d.get('railClip'),
        before=d.get('railBefore'), after=d.get('railAfter'),
        panel=d.get('panel'), panelBorder=d.get('panelBorder'),
        panelClip=d.get('panelClip'), shot=p)

    titles = win_titles(pid)
    vis = [t for t in titles if t['visible'] and t['class'] == 'Tauri Window']
    bad = [t['title'] for t in vis if 'x-hub' in (t['title'] or '').lower()]
    add('B4-岛品牌 shell-hub · 可见窗标题无 x-hub',
        d.get('brandCn') == 'shell-hub' and d.get('brandEn') == 'SHELL-HUB'
        and d.get('bodyXhub') == 0 and not bad
        and any('shell-hub' in (t['title'] or '').lower() for t in vis),
        brand=[d.get('brandCn'), d.get('brandEn')],
        body_xhub=d.get('bodyXhub'),
        visible_titles=[t['title'] for t in vis], bad=bad,
        shot=shot('deck'))


# --------------------------------------------------------------- B5 事实
def b5(pid, t0):
    import subprocess
    st = os.stat(EXE)
    p = subprocess.run(['powershell', '-NoProfile', '-Command',
                        "(Get-Item '%s').VersionInfo | ConvertTo-Json" % EXE.replace('/', '\\')],
                       capture_output=True, text=True, timeout=60)
    try:
        vi = json.loads(p.stdout)
    except Exception:  # noqa: BLE001
        vi = {'raw': p.stdout[-400:]}
    upd = os.path.join(ROOT, 'src-tauri', 'target', 'debug', 'data', 'updates')
    upd_left = os.listdir(upd) if os.path.isdir(upd) else []
    cfg = {}
    try:
        with open(os.path.join(ROOT, 'src-tauri', 'target', 'debug', 'data', 'app.json'), encoding='utf-8') as f:
            cfg = json.load(f)
    except Exception:  # noqa: BLE001
        pass
    hl = helmet_win() or {}
    add('B5-烟雾 PID / 启动时间 / 可见标题 / exe / updater 未冲掉',
        (vi.get('FileVersion') == '0.9.7')
        and not upd_left and cfg.get('auto_update_enabled') is False,
        pid=pid,
        started=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t0)),
        now=time.strftime('%Y-%m-%d %H:%M:%S'),
        tz=time.strftime('%Z %z'),
        exe=EXE, exe_bytes=st.st_size, exe_mtime=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)),
        file_version=vi.get('FileVersion'), product_version=vi.get('ProductVersion'),
        file_description=vi.get('FileDescription'), product_name=vi.get('ProductName'),
        main_title=[t['title'] for t in win_titles(pid) if t['visible']],
        helmet_internal=hl.get('title'),
        updates_dir=upd_left, auto_update_enabled=cfg.get('auto_update_enabled'))


def main():
    t0 = time.time()
    pid = None
    try:
        targets = cdp.list_targets(PORT)
    except Exception:  # noqa: BLE001
        targets = []
    if not any('Helmet' in (t.get('title') or '') for t in targets):
        pid, _ok = launch_smoke.launch('run-v5.log')
        print('launched:', pid, flush=True)
    if not wait_ready():
        print('FAIL: 头盔窗没起来', flush=True)
        return 1
    hl = helmet_win()
    if not pid:
        pid = (hl or {}).get('pid')
    b1()
    b2()
    b3_b4(pid)
    b5(pid, t0)

    ok = sum(1 for r in RESULT if r['ok'])
    print('\n==== 汇总 %d/%d ====' % (ok, len(RESULT)), flush=True)
    for r in RESULT:
        print(('PASS ' if r['ok'] else 'FAIL ') + r['step'], flush=True)
    with open(os.path.join(HERE, 'v5_result.json'), 'w', encoding='utf-8') as f:
        json.dump(RESULT, f, ensure_ascii=False, indent=1)
    return 0 if ok == len(RESULT) else 2


if __name__ == '__main__':
    sys.exit(main())