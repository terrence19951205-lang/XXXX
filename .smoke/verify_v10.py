"""v10 验收：A 壳收尾 / B 设置可进 / C 快捷键 → HUD 内面板。

只连 9222 上的 Helmet 页；只杀/启动自己的 debug 烟雾进程；不改业务数据
（唯一写入：上下班时间与聊天模型选择的恢复值）。
用法：
  python verify_v10.py shell            # A1/A2/A3/A5/A6（含真鼠标点击穿透与 Esc）
  python verify_v10.py settings-pre     # B1/B2 改动 + 准备折叠态
  python verify_v10.py restart          # 杀进程→重建不可（这不编译），只重启
  python verify_v10.py settings-post    # A4 + B 重启后仍在（再还原）
  python verify_v10.py hotkeys          # C 真按键 → HUD 内面板
"""
import ctypes
import ctypes.wintypes as w
import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cdp  # noqa: E402
from websockets.sync.client import connect  # noqa: E402

EXE = os.path.join(ROOT, 'src-tauri', 'target', 'debug', 'x-hub.exe')
DATA = os.path.join(ROOT, 'src-tauri', 'target', 'debug', 'data')
APP_JSON = os.path.join(DATA, 'app.json')
LOG = os.path.join(DATA, 'logs', 'x-hub.log')
PORT = 9222

u32 = ctypes.WinDLL('user32', use_last_error=True)
u32.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(ctypes.c_uint)]
u32.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
u32.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
u32.IsWindowVisible.argtypes = [w.HWND]
u32.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u32.mouse_event.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
u32.WindowFromPoint.restype = w.HWND
u32.WindowFromPoint.argtypes = [w.POINT]
u32.GetAncestor.restype = w.HWND
u32.GetAncestor.argtypes = [w.HWND, ctypes.c_uint]
u32.GetForegroundWindow.restype = w.HWND
u32.SetForegroundWindow.argtypes = [w.HWND]
u32.keybd_event.argtypes = [ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_uint, ctypes.c_void_p]


# ------------------------------------------------------------------ 基础
def pid_of():
    out = subprocess.run(['powershell', '-NoProfile', '-Command',
                          '(Get-Process x-hub -ErrorAction SilentlyContinue | Select-Object -First 1).Id'],
                         capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() else None


def win_title(h):
    b = ctypes.create_unicode_buffer(256)
    u32.GetWindowTextW(h, b, 256)
    return b.value


def windows(pid):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, lp):
        p = ctypes.c_uint()
        u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid:
            r = w.RECT()
            u32.GetWindowRect(h, ctypes.byref(r))
            out.append({'hwnd': hex(h), 'title': win_title(h),
                        'visible': bool(u32.IsWindowVisible(h)),
                        'rect': [r.left, r.top, r.right, r.bottom]})
        return True

    u32.EnumWindows(cb, 0)
    return out


def helmet_hwnd(pid):
    for x in windows(pid):
        if x['title'] == 'Helmet':
            return int(x['hwnd'], 16), x
    return None, None


def click_at(x, y):
    u32.SetCursorPos(int(x), int(y))
    time.sleep(0.25)
    u32.mouse_event(0x2, 0, 0, 0, None)
    time.sleep(0.05)
    u32.mouse_event(0x4, 0, 0, 0, None)
    time.sleep(0.35)


def move_to(x, y):
    u32.SetCursorPos(int(x), int(y))
    time.sleep(0.55)


VK = {'ctrl': 0x11, 'shift': 0x10, 'alt': 0x12, '`': 0xC0, 'k': 0x4B, 'n': 0x4E, 'space': 0x20}


def hotkey(mods, key):
    for m in mods:
        u32.keybd_event(VK[m], 0, 0, None)
    u32.keybd_event(VK[key], 0, 0, None)
    time.sleep(0.06)
    u32.keybd_event(VK[key], 0, 2, None)
    for m in reversed(mods):
        u32.keybd_event(VK[m], 0, 2, None)
    time.sleep(0.35)


def fg_title():
    h = u32.GetForegroundWindow()
    return {'hwnd': hex(h), 'title': win_title(h)}


def hit_at(x, y):
    h = u32.WindowFromPoint(w.POINT(int(x), int(y)))
    root = u32.GetAncestor(h, 2) if h else 0
    return {'root_title': win_title(root) if root else None}


# ------------------------------------------------------------------ CDP
WS = None


def connect_ws(wait=60):
    global WS
    t0 = time.time()
    while time.time() - t0 < wait:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json', timeout=3) as r:
                ts = json.loads(r.read().decode('utf-8', 'replace'))
            cand = [t for t in ts if 'Helmet' in (t.get('title') or '')]
            if cand:
                WS = cand[0]['webSocketDebuggerUrl']
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)
    return False


def js(expr, timeout=30):
    if WS is None and not connect_ws(20):
        raise RuntimeError('CDP 未就绪')
    r = cdp.evaluate(WS, expr, timeout=timeout)
    res = r.get('result', {})
    if res.get('exceptionDetails'):
        raise RuntimeError(json.dumps(res['exceptionDetails'], ensure_ascii=False)[:300])
    return res.get('result', {}).get('value')


def state():
    s = js("""JSON.stringify({
      mode: __helmet.mode, panel: __helmet.panel, geo: __helmet.geo, docked: __helmet.docked,
      ignoring: __helmet.ignoring, boot: __helmet.boot, pct: __helmet.pct,
      hours: __helmet.hours, island: __helmet.island, view: __helmet.viewport,
      deck: !!document.querySelector('.hud.is-open'), chat: !!document.querySelector('.island-chat'),
      notes: __helmet.notes, lsCollapsed: localStorage.getItem('rr.hud.collapsed.v10'),
      lsHours: localStorage.getItem('rr.hud.hours'),
      pctText: (document.querySelector('.island-pct')||{}).textContent || '',
      model: (() => { const s = document.querySelector('.set-block select'); return s ? s.value : null; })(),
      active: (() => { const a = document.activeElement; if (!a) return '';
        const p = a.parentElement;
        return [a.tagName, a.className || '', p ? (p.className || '') : ''].join('|'); })(),
    })""")
    return json.loads(s) if isinstance(s, str) else s


def shot(name):
    with connect(WS, max_size=64 * 1024 * 1024, open_timeout=15, close_timeout=5) as ws:
        ws.send(json.dumps({'id': 1, 'method': 'Page.enable'}))
        ws.send(json.dumps({'id': 2, 'method': 'Page.captureScreenshot',
                            'params': {'format': 'png', 'captureBeyondViewport': False}}))
        end = time.time() + 30
        while time.time() < end:
            m = json.loads(ws.recv())
            if m.get('id') == 2:
                import base64
                data = m.get('result', {}).get('data')
                p = os.path.join(HERE, name)
                if data:
                    open(p, 'wb').write(base64.b64decode(data))
                return p
    return None


def key_escape():
    with connect(WS, max_size=16 * 1024 * 1024, open_timeout=15, close_timeout=5) as ws:
        ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
        msg = {'id': 2, 'method': 'Input.dispatchKeyEvent', 'params': {
            'type': 'keyDown', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27,
            'nativeVirtualKeyCode': 27}}
        ws.send(json.dumps(msg))
        ws.send(json.dumps({'id': 3, 'method': 'Input.dispatchKeyEvent', 'params': {
            'type': 'keyUp', 'key': 'Escape', 'code': 'Escape', 'windowsVirtualKeyCode': 27,
            'nativeVirtualKeyCode': 27}}))
        time.sleep(0.4)


def key_enter():
    with connect(WS, max_size=16 * 1024 * 1024, open_timeout=15, close_timeout=5) as ws:
        ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
        for i, typ in enumerate(('keyDown', 'keyUp'), start=2):
            ws.send(json.dumps({'id': i, 'method': 'Input.dispatchKeyEvent', 'params': {
                'type': typ, 'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13}}))
        time.sleep(0.3)


def out(name, data):
    p = os.path.join(HERE, name)
    json.dump(data, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('WROTE', p, flush=True)


def wait_ready(timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if js('!!window.__helmet'):
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)
    return False


def screen_pt(sel, frac=0.5):
    """CSS 元素中心 → 屏幕物理坐标（scale 由 __helmet.frame 提供，缺则 1）"""
    info = js("""(() => {
      const e = document.querySelector(%s);
      if (!e) return null;
      const r = e.getBoundingClientRect();
      return {x: r.left + r.width*%s, y: r.top + r.height/2};
    })()""" % (json.dumps(sel), frac))
    return info


_DPI_K = None


def dpi_k():
    """窗口矩形来自 Tauri，单位是 DIP；SetCursorPos 要的是物理像素，两者差 monitor_width/innerWidth。"""
    global _DPI_K
    if _DPI_K is None:
        import mss
        with mss.mss() as s:
            mon = s.monitors[0]
        _DPI_K = mon['width'] / max(1, js('innerWidth'))
    return _DPI_K


def to_screen(css_pt, rect, scale=None):
    """CSS 坐标 → 屏幕物理像素。scale 参数保留但不再使用：真正的换算因子是 dpi_k()。"""
    k = dpi_k()
    return (rect[0] + css_pt['x']) * k, (rect[1] + css_pt['y']) * k


def ensure_deck():
    st = state()
    if st['mode'] != 'deck':
        js("document.querySelector('[data-nav=\\\"todos\\\"]').click()")
        time.sleep(1.2)
    return state()


# ================================================================== 下层背板窗口
# 自建 Win32 窗口当“下层应用”：把 WM_LBUTTONDOWN 计数，点穿与否都有硬证据。
_backdrop = {'hwnd': None, 'hits': 0, 'proc': None, 'thread': None}

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, w.HWND, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [('style', ctypes.c_uint), ('lpfnWndProc', WNDPROC),
                ('cbClsExtra', ctypes.c_int), ('cbWndExtra', ctypes.c_int),
                ('hInstance', w.HINSTANCE), ('hIcon', w.HICON), ('hCursor', w.HANDLE),
                ('hbrBackground', w.HBRUSH), ('lpszMenuName', w.LPCWSTR),
                ('lpszClassName', w.LPCWSTR)]


u32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
u32.CreateWindowExW.restype = w.HWND
u32.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]
u32.DefWindowProcW.restype = ctypes.c_ssize_t
u32.DefWindowProcW.argtypes = [w.HWND, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
u32.ShowWindow.argtypes = [w.HWND, ctypes.c_int]
u32.GetMessageW.argtypes = [ctypes.POINTER(w.MSG), w.HWND, ctypes.c_uint, ctypes.c_uint]


def _wndproc(hwnd, msg, wp, lp):
    if msg == 0x0201:  # WM_LBUTTONDOWN
        _backdrop['hits'] += 1
    return u32.DefWindowProcW(hwnd, msg, wp, lp)


def start_backdrop():
    if _backdrop['hwnd']:
        return {'hwnd': _backdrop['hwnd'], 'hits': _backdrop['hits']}
    inst = ctypes.windll.kernel32.GetModuleHandleW(None)
    proc = WNDPROC(_wndproc)
    wc = WNDCLASSW()
    wc.lpfnWndProc = proc
    wc.hInstance = inst
    wc.lpszClassName = 'V10BackdropWnd'
    wc.hbrBackground = ctypes.cast(5, w.HBRUSH)  # COLOR_WINDOW+1
    u32.RegisterClassW(ctypes.byref(wc))
    _backdrop['proc'] = proc

    def run():
        h = u32.CreateWindowExW(0, 'V10BackdropWnd', 'V10-Backdrop', 0x00CF0000 | 0x10000000,
                                200, 150, 1900, 1200, None, None, inst, None)
        if not h:
            return
        _backdrop['hwnd'] = h
        u32.ShowWindow(h, 4)  # SW_SHOWNOACTIVATE：不抢前台
        msg = w.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u32.TranslateMessage(ctypes.byref(msg))
            u32.DispatchMessageW(ctypes.byref(msg))

    import threading
    t = threading.Thread(target=run, daemon=True)
    t.start()
    _backdrop['thread'] = t
    for _ in range(40):
        time.sleep(0.1)
        if _backdrop['hwnd']:
            break
    if not _backdrop['hwnd']:
        return None
    u32.SetWindowPos(_backdrop['hwnd'], 0, 200, 150, 1900, 1200, 0x0040)
    time.sleep(0.3)
    return {'hwnd': _backdrop['hwnd'], 'hits': _backdrop['hits']}


u32.TranslateMessage.argtypes = [ctypes.POINTER(w.MSG)]
u32.DispatchMessageW.argtypes = [ctypes.POINTER(w.MSG)]


def backdrop_hits():
    return _backdrop['hits']


def close_backdrop():
    if _backdrop['hwnd']:
        u32.DestroyWindow(_backdrop['hwnd'])
        _backdrop['hwnd'] = None


u32.DestroyWindow.argtypes = [w.HWND]


# ================================================================== PHASE shell
def settle_full(timeout=8):
    """等躯干铺满、视口稳定（开场/尺寸动画期间量到的坐标会偏）"""
    t0 = time.time()
    last = None
    stable = 0
    while time.time() - t0 < timeout:
        st = state()
        cur = tuple(st['view'])
        if st['geo'] == 'full' and cur == last:
            stable += 1
            if stable >= 2:
                return st
        else:
            stable = 0
        last = cur
        time.sleep(0.3)
    return state()


def phase_shell():
    wait_ready()
    pid = pid_of()
    hwnd, win = helmet_hwnd(pid)
    res = {'pid': pid, 'title': win_title(hwnd), 'items': {}}
    if state()['boot']:
        key_enter()
        time.sleep(2.5)
    ensure_deck()
    st_geo = settle_full()
    hwnd, win = helmet_hwnd(pid)
    rect = win['rect']
    # 物理/CSS 比例按“当前窗口宽度 ÷ 当前视口宽度”现算：frameRect 可能是别的几何下记的
    scale = (rect[2] - rect[0]) / max(1, js('innerWidth'))
    res['geometry'] = {'window_rect': rect, 'viewport': st_geo['view'], 'scale': scale,
                       'devicePixelRatio': js('devicePixelRatio')}

    # --- 下层窗口：自建 Win32 背板（记录 WM_LBUTTONDOWN）
    backdrop = start_backdrop()
    base_hits = backdrop_hits()

    # 透明点：躯体右侧空白，确认不在任何 .hit 上
    probe = js("""(() => {
      const cw = innerWidth, ch = innerHeight;
      const cands = [[cw-60, ch*0.5], [cw*0.9, ch*0.62], [cw*0.6, ch*0.8]];
      for (const [x,y] of cands) {
        const el = document.elementFromPoint(x, y);
        const hit = el && el.closest && el.closest('.hit');
        if (!hit) return {x, y, tag: el ? el.tagName : null};
      }
      return null;
    })()""")
    hwnd, win = helmet_hwnd(pid)
    rect = win['rect']
    px, py = to_screen(probe, rect, scale) if probe else (rect[0] + 400, rect[1] + 300)
    move_to(px, py)
    time.sleep(0.7)
    st_pt = {'css': probe, 'screen': [px, py], 'window_rect': rect,
             'ignoring': state()['ignoring'], 'window_from_point': hit_at(px, py),
             'backdrop_hits_before': backdrop_hits()}
    click_at(px, py)
    time.sleep(0.5)
    st_pt['backdrop_hits_after'] = backdrop_hits()
    st_pt['fg_after_click'] = fg_title()
    st_pt['passthrough_ok'] = backdrop_hits() > base_hits
    st_pt['panel_unchanged'] = state()['panel']
    res['items']['A1_transparent_passthrough'] = st_pt

    # 控件命中区：轨道「启动常用」按钮（每次点击前重取 rect + elementFromPoint 校验落点）
    bx = by = None
    for _ in range(8):
        hwnd, win = helmet_hwnd(pid)
        rect = win['rect']
        btn = screen_pt('[data-nav="launch"]')
        if not btn:
            time.sleep(0.4)
            continue
        sc = (rect[2] - rect[0]) / max(1, js('innerWidth'))
        bx, by = to_screen(btn, rect, sc)
        nav = js("""(() => { const e = document.elementFromPoint(%s, %s);
          const n = e && e.closest ? e.closest('[data-nav]') : null;
          return n ? n.dataset.nav : (e ? e.tagName : null); })()""" % (btn['x'], btn['y']))
        if nav == 'launch':
            break
        time.sleep(0.4)
    move_to(bx, by)
    time.sleep(0.7)
    before_panel = state()['panel']
    ignoring_on_hit = state()['ignoring']
    hits_before_btn = backdrop_hits()
    click_at(bx, by)
    time.sleep(0.9)
    st_btn = state()
    res['items']['A1_hit_control_clickable'] = {
        'target': '[data-nav="launch"]', 'screen': [bx, by], 'window_rect': rect,
        'ignoring_before_click': ignoring_on_hit,
        'panel_before': before_panel, 'panel_after': st_btn['panel'],
        'mode_after': st_btn['mode'], 'fg_after': fg_title(),
        'backdrop_hits_delta': backdrop_hits() - hits_before_btn,
        'ok': st_btn['panel'] == 'launch' and st_btn['mode'] == 'deck' and ignoring_on_hit is False,
    }
    res['items']['A1_screenshot'] = shot('v10_shell_passthrough.png')
    close_backdrop()

    # --- A5 Esc：展开态 → idle → 贴顶
    key_escape()
    time.sleep(1.8)
    st_esc = state()
    hwnd2, win2 = helmet_hwnd(pid)
    res['items']['A5_esc_retreat'] = {
        'mode': st_esc['mode'], 'geo': st_esc['geo'], 'docked': st_esc['docked'],
        'window_visible': win2['visible'], 'window_rect': win2['rect'],
        'window_height_px': win2['rect'][3] - win2['rect'][1],
        'helmet_alive': win2['visible'],
        'ok': st_esc['mode'] == 'idle' and st_esc['docked'] and win2['visible']
              and (win2['rect'][3] - win2['rect'][1]) <= 12,
    }

    # --- A2 收起只留岛+热区（唇边 10px；无侧栏/大面板）
    res['items']['A2_collapsed_only_lip'] = {
        'docked': st_esc['docked'], 'geo': st_esc['geo'],
        'hud_deck_open': st_esc['deck'], 'chat_open': st_esc['chat'],
        'window_rect': win2['rect'], 'window_height': win2['rect'][3] - win2['rect'][1],
        'hot_zone_hit': hit_at((win2['rect'][0] + win2['rect'][2]) / 2, win2['rect'][1] + 2),
        'ok': st_esc['docked'] and st_esc['geo'] == 'lip' and not st_esc['deck']
              and not st_esc['chat'] and (win2['rect'][3] - win2['rect'][1]) <= 12,
    }
    res['items']['A2_screenshot'] = shot('v10_shell_lip.png')

    # --- 顶部热区唤出
    cx = (win2['rect'][0] + win2['rect'][2]) // 2
    move_to(cx, win2['rect'][1] + 2)
    time.sleep(1.5)
    st_rev = state()
    hwnd3, win3 = helmet_hwnd(pid)
    res['items']['A2_reveal_hotzone'] = {
        'docked_after_hover': st_rev['docked'], 'geo': st_rev['geo'],
        'window_height': win3['rect'][3] - win3['rect'][1],
        'island_w': st_rev['island']['w'],
        'ok': st_rev['docked'] is False and st_rev['geo'] == 'band'
              and (win3['rect'][3] - win3['rect'][1]) > 20,
    }

    # --- A3 band 透明留边不抢点：移到岛左侧留边（窗口内、.hit 外）
    left_pad = js("""(() => {
      const r = document.querySelector('.island').getBoundingClientRect();
      return {x: r.left - 6, y: r.top + r.height/2};
    })()""")
    lx, ly = to_screen(left_pad, win3['rect'], scale)
    move_to(lx, ly)
    time.sleep(0.9)
    st_pad = state()
    res['items']['A3_margin_not_stealing'] = {
        'point': [lx, ly], 'ignoring': st_pad['ignoring'], 'hit': hit_at(lx, ly),
        'ok': st_pad['ignoring'] is True,
    }

    # --- A6 禁球 + 主窗不作第二入口
    wins = windows(pid)
    vis = [x for x in wins if x['visible'] and x['title']]
    res['items']['A6_no_ball'] = {
        'ball_windows': [x for x in wins if '悬浮球' in (x['title'] or '')],
        'visible_titled_windows': vis,
        'main_window': [x for x in wins if 'shell-hub' in (x['title'] or '')],
        'cbtargets': [t['title'] for t in cdp.list_targets(PORT)],
        'ok': not any('悬浮球' in (x['title'] or '') for x in wins)
              and all(not x['visible'] for x in wins if 'shell-hub' in (x['title'] or '')),
    }
    out('v10_shell.json', res)
    print(json.dumps({k: (v.get('ok') if isinstance(v, dict) else v)
                      for k, v in res['items'].items()}, ensure_ascii=False, indent=1))


u32.TranslateMessage.argtypes = [ctypes.POINTER(w.MSG)]
u32.DispatchMessageW.argtypes = [ctypes.POINTER(w.MSG)]

def windows_any():
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, lp):
        if u32.IsWindowVisible(h):
            t = win_title(h)
            if t:
                out.append({'hwnd': hex(h), 'title': t})
        return True

    u32.EnumWindows(cb, 0)
    return out


u32.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int,
                             ctypes.c_int, ctypes.c_int, ctypes.c_uint]


# ================================================================== PHASE settings-pre
def phase_settings_pre():
    wait_ready()
    pid = pid_of()
    res = {'pid': pid}
    ensure_deck()
    js("document.querySelector('[data-nav=\\\"settings\\\"]').click()")
    time.sleep(1.2)
    st0 = state()
    orig_hours = json.loads(st0['lsHours'] or '{"start":"09:00","end":"18:30"}')

    # B1 上下班 → 岛 %
    pct_before = st0['pctText']
    ok_set = js("""(() => {
      const b = [...document.querySelectorAll('.set-block')].find(x => /上下班/.test(x.textContent));
      if (!b) return false;
      const ins = [...b.querySelectorAll('input')];
      const set = (e, v) => { const d = Object.getOwnPropertyDescriptor(e.constructor.prototype, 'value');
        d.set.call(e, v); e.dispatchEvent(new Event('input', {bubbles: true})); };
      set(ins[0], '00:00'); set(ins[1], '23:59');
      const btn = [...b.querySelectorAll('button')].find(x => /保存/.test(x.textContent));
      if (btn) btn.click();
      return true;
    })()""")
    time.sleep(1.4)
    st1 = state()
    res['B1_hours'] = {
        'panel': st0['panel'], 'settings_open': st0['panel'] == 'settings',
        'pct_before': pct_before, 'pct_after': st1['pctText'],
        'hours_before': orig_hours, 'hours_after': st1['lsHours'],
        'island_label': st1['hours'], 'applied': ok_set,
        'ok': ok_set and st1['lsHours'] != st0['lsHours'] and st1['pctText'] != pct_before,
    }

    # B2 聊天模型：下拉 → 写 config（用空值做一个可回滚的真实变更）
    sel_opts = js("""(() => {
      const s = document.querySelector('.set-block select');
      return s ? {value: s.value, opts: [...s.options].map(o => o.value)} : null;
    })()""")
    js("""(() => {
      const s = document.querySelector('.set-block select');
      if (!s) return false;
      const d = Object.getOwnPropertyDescriptor(s.constructor.prototype, 'value');
      d.set.call(s, ''); s.dispatchEvent(new Event('change', {bubbles: true}));
      return true;
    })()""")
    time.sleep(1.2)
    cfg = json.load(open(APP_JSON, encoding='utf-8'))
    res['B2_model'] = {
        'options': sel_opts, 'new_value': cfg.get('chat_selected_model'),
        'config_chat_selected_model': cfg.get('chat_selected_model'),
        'ok': cfg.get('chat_selected_model') == '' and bool(sel_opts and sel_opts['opts']),
    }
    res['shot'] = shot('v10_settings.png')

    # 准备 A4：收敛成折叠态（先把光标移出岛，否则 hover 会钉住不贴顶）
    move_to(200, 900)
    key_escape()
    time.sleep(0.6)
    move_to(200, 900)
    time.sleep(1.4)
    st2 = state()
    res['prep_collapsed'] = {'docked': st2['docked'], 'geo': st2['geo'],
                             'lsCollapsed': st2['lsCollapsed'],
                             'window': helmet_hwnd(pid)[1]}
    res['orig'] = {'hours': orig_hours, 'model': sel_opts['value'] if sel_opts else ''}
    out('v10_settings.json', res)
    print(json.dumps({k: v for k, v in res.items() if k.startswith(('B', 'prep'))},
                     ensure_ascii=False, indent=1))


# ================================================================== PHASE restart
def kill_pid(pid):
    subprocess.run(['powershell', '-NoProfile', '-Command',
                    f'Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue'],
                   capture_output=True, text=True)
    for _ in range(20):
        if pid_of() is None:
            return True
        time.sleep(0.5)
    return False


def launch():
    cfg = json.load(open(os.path.join(HERE, 'tauri.smoke.json'), encoding='utf-8'))
    args = cfg['app']['windows'][0]['additionalBrowserArgs']
    env = dict(os.environ)
    env['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = args
    log = open(os.path.join(HERE, 'run-v10.log'), 'w')
    p = subprocess.Popen([EXE], cwd=os.path.dirname(EXE), env=env, stdout=log,
                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         creationflags=0x00000008 | 0x00000200, close_fds=True)
    return p.pid


def phase_restart():
    pid = pid_of()
    killed = kill_pid(pid) if pid else True
    time.sleep(1.5)
    new_pid = launch()
    ok = connect_ws(90)
    print('restart', {'old_pid': pid, 'killed': killed, 'new_pid': new_pid, 'cdp': ok})
    global WS
    WS = None
    ok2 = connect_ws(60)
    out('v10_restart.json', {'old_pid': pid, 'new_pid': new_pid, 'killed': killed, 'cdp': ok2})


# ================================================================== PHASE settings-post
def phase_settings_post():
    wait_ready()
    pid = pid_of()
    res = {'pid': pid, 'title': win_title(helmet_hwnd(pid)[0])}
    if state()['boot']:
        key_enter()
        time.sleep(2.5)
    time.sleep(1.0)
    st = state()
    hwnd, win = helmet_hwnd(pid)
    res['A4_collapsed_restored'] = {
        'docked': st['docked'], 'geo': st['geo'], 'lsCollapsed': st['lsCollapsed'],
        'window_rect': win['rect'], 'window_height': win['rect'][3] - win['rect'][1],
        'hud_deck_open': st['deck'], 'chat_open': st['chat'],
        'ok': st['docked'] and st['geo'] == 'lip' and st['lsCollapsed'] == '1'
              and (win['rect'][3] - win['rect'][1]) <= 12,
    }
    res['A4_screenshot'] = shot('v10_restart_lip.png')

    prev = json.load(open(os.path.join(HERE, 'v10_settings.json'), encoding='utf-8'))
    cfg = json.load(open(APP_JSON, encoding='utf-8'))
    res['B1_hours_persisted'] = {
        'lsHours': st['lsHours'], 'pct': st['pctText'], 'island_hours_label': st['hours'],
        'config_hours': None,
        'ok': (json.loads(st['lsHours'] or '{}') == json.loads(prev['B1_hours']['hours_after'] or '{}'))
              and st['pctText'] == prev['B1_hours']['pct_after'],
    }
    ensure_deck()
    js("document.querySelector('[data-nav=\\\"settings\\\"]').click()")
    for _ in range(15):
        if js("!!document.querySelector('.set-block select')"):
            break
        time.sleep(0.4)
    time.sleep(0.6)
    st2 = state()
    res['B2_model_persisted'] = {
        'select_value_after_restart': st2['model'],
        'config_chat_selected_model': cfg.get('chat_selected_model'),
        'ok': st2['model'] == '' and cfg.get('chat_selected_model') == '',
    }
    res['settings_shot_after_restart'] = shot('v10_settings_after_restart.png')

    # --- 还原现场：模型回原值，上下班回原值
    js("""(() => {
      const s = document.querySelector('.set-block select');
      const d = Object.getOwnPropertyDescriptor(s.constructor.prototype, 'value');
      d.set.call(s, %s); s.dispatchEvent(new Event('change', {bubbles: true}));
    })()""" % json.dumps(prev['orig']['model']))
    time.sleep(1.0)
    oh = prev['orig']['hours']
    js("""(() => {
      const b = [...document.querySelectorAll('.set-block')].find(x => /上下班/.test(x.textContent));
      const ins = [...b.querySelectorAll('input')];
      const set = (e, v) => { const d = Object.getOwnPropertyDescriptor(e.constructor.prototype, 'value');
        d.set.call(e, v); e.dispatchEvent(new Event('input', {bubbles: true})); };
      set(ins[0], %s); set(ins[1], %s);
      const btn = [...b.querySelectorAll('button')].find(x => /保存/.test(x.textContent));
      if (btn) btn.click();
    })()""" % (json.dumps(oh['start']), json.dumps(oh['end'])))
    time.sleep(1.2)
    cfg2 = json.load(open(APP_JSON, encoding='utf-8'))
    st3 = state()
    res['restore'] = {'model': cfg2.get('chat_selected_model'), 'hours': st3['lsHours'],
                      'expected': prev['orig']}
    out('v10_settings_restart.json', res)
    print(json.dumps({k: (v.get('ok') if isinstance(v, dict) and 'ok' in v else v)
                      for k, v in res.items()}, ensure_ascii=False, indent=1))


# ================================================================== PHASE hotkeys
def log_hotkey_lines():
    try:
        lines = open(LOG, encoding='utf-8', errors='replace').read().splitlines()
        return [l for l in lines if '事件触发' in l][-12:]
    except Exception as e:  # noqa: BLE001
        return ['log err ' + repr(e)]


def phase_hotkeys():
    wait_ready()
    pid = pid_of()
    res = {'pid': pid, 'title': win_title(helmet_hwnd(pid)[0]), 'cases': {}}
    if state()['boot']:
        key_enter()
        time.sleep(2.5)
    visible_before = [x['title'] for x in windows(pid) if x['visible'] and x['title']]
    # 笔记快照：快捷键不应让隐藏主窗 SPA 顺手建/删笔记
    note_ids = lambda: sorted(n['id'] for n in json.loads(js(
        "(async () => JSON.stringify(await window.__TAURI_INTERNALS__.invoke('list_notes')))()")))
    notes_before = note_ids()

    def reset():
        key_escape()
        time.sleep(1.6)

    def run(name, mods, key, expect, extra=None):
        reset()
        t0 = time.time()
        before_state = state()
        hotkey(mods, key)
        time.sleep(1.3)
        st = state()
        vis = [x['title'] for x in windows(pid) if x['visible'] and x['title']]
        item = {'combo': '+'.join([m.capitalize() for m in mods] + [key]),
                'expect': expect, 'mode': st['mode'], 'panel': st['panel'],
                'deck': st['deck'], 'chat': st['chat'],
                'active': st['active'], 'visible_windows': vis,
                'new_windows': [v for v in vis if v not in visible_before],
                'state_before': {'mode': before_state['mode'], 'docked': before_state['docked']},
                'shot': shot('v10_hotkey_%s.png' % name), 'elapsed': round(time.time() - t0, 2)}
        ok = True
        if expect == 'chat':
            ok = st['mode'] == 'chat' and st['chat']
        elif expect == 'clipboard':
            ok = st['mode'] == 'deck' and st['panel'] == 'clipboard' and st['deck']
        elif expect == 'notes':
            ok = st['mode'] == 'deck' and st['panel'] == 'notes' and st['notes']['list']
        elif expect == 'search':
            ok = st['mode'] == 'deck' and 'quick-search' in (st['active'] or '')
        elif expect == 'toggle':
            ok = st['mode'] == 'idle' and st['docked']
        item['ok'] = ok
        res['cases'][name] = item
        print(('PASS ' if ok else 'FAIL ') + name, json.dumps(item, ensure_ascii=False)[:260], flush=True)

    # 初始：总开关先把 HUD 打开（idle→deck），再关掉
    reset()
    run('toggle_open', ['ctrl', 'shift'], 'space', 'deck_open')
    res['cases']['toggle_open']['ok'] = res['cases']['toggle_open']['mode'] == 'deck'
    # 上面 run 的 expect 'deck_open' 不参与判定，补一次显式 toggle 收起
    hotkey(['ctrl', 'shift'], 'space')
    time.sleep(1.2)
    res['cases']['toggle_close'] = {'mode': state()['mode'], 'docked': state()['docked'],
                                   'ok': state()['mode'] == 'idle'}

    run('chat', ['ctrl', 'shift'], 'k', 'chat')
    run('clipboard', ['ctrl'], '`', 'clipboard')
    run('search', ['ctrl'], 'k', 'search')
    run('notes', ['ctrl', 'shift'], 'n', 'notes')

    res['no_extra_windows'] = {
        'visible_before': visible_before,
        'visible_after': [x['title'] for x in windows(pid) if x['visible'] and x['title']],
        'clipboard_overlay_visible': [x for x in windows(pid)
                                      if '剪贴板历史' in (x['title'] or '') and x['visible']],
        'chat_window_visible': [x for x in windows(pid) if x['title'] == 'AI 对话' and x['visible']],
        'ball': [x for x in windows(pid) if '悬浮球' in (x['title'] or '')],
    }
    res['no_extra_windows']['ok'] = (not res['no_extra_windows']['clipboard_overlay_visible']
                                     and not res['no_extra_windows']['chat_window_visible']
                                     and not res['no_extra_windows']['ball'])
    try:
        notes_after = note_ids()
    except Exception:  # noqa: BLE001
        notes_after = None
    res['notes_untouched'] = {'before': notes_before, 'after': notes_after,
                              'ok': notes_after == notes_before}
    res['log_evidence'] = log_hotkey_lines()
    out('v10_hotkeys.json', res)
    print(json.dumps({k: v['ok'] for k, v in res['cases'].items()}, ensure_ascii=False))
    print('notes_untouched', res['notes_untouched']['ok'], flush=True)


if __name__ == '__main__':
    phase = sys.argv[1] if len(sys.argv) > 1 else 'shell'
    globals()['phase_' + phase.replace('-', '_')]()