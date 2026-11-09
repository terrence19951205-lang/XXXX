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
    scale = js("(__helmet.frame && __helmet.frame.scale) || 1")
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

    # 控件命中区：轨道「启动常用」按钮（每次点击前重取 rect，避免动画期坐标漂移）
    hwnd, win = helmet_hwnd(pid)
    rect = win['rect']
    btn = screen_pt('[data-nav="launch"]')
    bx, by = to_screen(btn, rect, scale)
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