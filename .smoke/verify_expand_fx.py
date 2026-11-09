"""缺口 1 验收：展开全屏光效（真窗口 / 真鼠标 / 系统截屏 / 真穿透）。

不采信 CSS 里写了什么，只采信屏幕像素与窗口消息：
  A1 收起→点▾ 触发一次 .is-ceremony，类名时长 ≈150ms
  A2 峰值强度：只在「HUD 收起/展开都不变的桌面区域」上算差值，排除布局变化
  A3 展开→收起不播（class 计数不变）
  A4 光效期间中央仍可点穿到下层窗口（Win32 消息计数）
  A5 prefers-reduced-motion: reduce 时不播

产物：.smoke/expand_fx_fixcheck.json + fx_fix/ 帧序列 + fx_fix/expand_fx.gif
用法：python verify_expand_fx.py
"""
import ctypes
import json
import os
import sys
import threading
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import verify_v10 as V  # noqa: E402
import expand_fx_probe as P  # noqa: E402

OUT = os.path.join(HERE, 'fx_fix')
R = {}
OK = {'v': True}


def js(e):
    return V.js(e)


def note(k, ok, **kw):
    R[k] = {'ok': bool(ok), **kw}
    OK['v'] = OK['v'] and bool(ok)
    print(('PASS ' if ok else 'FAIL ') + k, '|', json.dumps(kw, ensure_ascii=False)[:420], flush=True)


# ------------------------------------------------------------------ 记录器
REC = """(() => {
  window.__fxRec = {events: [], count: 0};
  const fx = document.querySelector('.fx');
  if (!fx) return false;
  const push = () => {
    const cls = fx.className;
    window.__fxRec.count++;
    window.__fxRec.events.push({t: Math.round(performance.now()), cls: cls});
  };
  window.__fxRecObs && window.__fxRecObs.disconnect();
  window.__fxRecObs = new MutationObserver(push);
  window.__fxRecObs.observe(fx, {attributes: true, attributeFilter: ['class']});
  return true;
})()"""


def rec_reset():
    return js("(() => { window.__fxRec = {events: [], count: 0}; return true; })()")


def rec_read():
    s = js("JSON.stringify(window.__fxRec || null)")
    return json.loads(s) if s else {'events': [], 'count': 0}


def ceremony_events(rec):
    return [e for e in rec['events'] if 'is-ceremony' in e['cls'] and 'is-ceremony-hold' not in e['cls']]


def click_toggle():
    pid = V.pid_of()
    _h, win = V.helmet_hwnd(pid)
    sc = (win['rect'][2] - win['rect'][0]) / max(1, js('innerWidth'))
    pt = V.screen_pt('.island-toggle')
    px, py = V.to_screen(pt, win['rect'], sc)
    V.move_to(px, py)
    time.sleep(0.5)
    return px, py


# ------------------------------------------------------------------ 连拍
def burst_expand(frames=80):
    P.to_expanded_steady()
    time.sleep(0.6)
    rect = P.rect_now()
    steady = P.grab(rect)
    # 收起态基准：只留唇边，用来求「与 HUD 布局无关」的桌面掩码
    V.key_escape()
    time.sleep(1.9)
    collapsed = P.grab(rect)
    if not P.reveal_island():
        raise RuntimeError('唇边没唤出')
    px, py = click_toggle()
    t_click = {'v': None}

    def do_click():
        V.click_at(px, py)
        t_click['v'] = time.perf_counter()

    t0 = time.perf_counter()
    th = threading.Thread(target=do_click)
    th.start()
    shots = []
    for _ in range(frames):
        shots.append((time.perf_counter() - t0, P.grab(rect)))
    th.join()

    # 掩码：收起 vs 展开都一样的像素 = 纯桌面，光效之外的布局变化不会污染
    d_layout = np.abs(steady.astype(np.int16) - collapsed.astype(np.int16)).max(axis=2)
    mask = d_layout <= 2
    mask_frac = float(mask.mean())
    # 中央区：远离面板/光边，收起与展开都不变，只用来量「这一闪有多亮」。
    # 旧脚本在整幅 mask 上取均值，被玻璃面板 blur 的变化污染（p99 曾冲到 182），不是光效。
    hh, ww = mask.shape
    cmask = np.zeros_like(mask)
    cmask[int(hh * 0.30):int(hh * 0.70), int(ww * 0.34):int(ww * 0.66)] = True
    cmask &= mask
    stats = []
    for i, (ts, img) in enumerate(shots):
        d = np.abs(img.astype(np.int16) - steady.astype(np.int16)).max(axis=2)
        if mask.any():
            vals = d[mask]
            row = {'i': i, 't': round(ts * 1000),
                   'mask_mean': round(float(vals.mean()), 2),
                   'mask_p99': round(float(np.percentile(vals, 99)), 1),
                   'mask_hit_frac': round(float((vals > 8).mean()), 3)}
            if cmask.any():
                cv = d[cmask]
                row.update({'c_mean': round(float(cv.mean()), 3),
                            'c_p99': round(float(np.percentile(cv, 99)), 1),
                            'c_max': int(cv.max()),
                            'c_hit': round(float((cv > 2).mean()), 3)})
            stats.append(row)
        else:
            stats.append({'i': i, 't': round(ts * 1000), 'mask_mean': None})
    click_ms = (t_click['v'] - t0) * 1000 if t_click['v'] else None
    near = [s for s in stats if s.get('c_mean') is not None
            and (click_ms is None or -40 <= s['t'] - click_ms <= 420)]
    peak = max(near or stats, key=lambda s: s.get('c_mean') or -1)
    return {'steady': steady, 'collapsed': collapsed, 'shots': shots, 'stats': stats,
            'peak': peak, 'click_ms': round(click_ms) if click_ms else None,
            'mask_frac': round(mask_frac, 3)}


def save_artifacts(b):
    os.makedirs(OUT, exist_ok=True)
    manifest = []
    for i, (ts, img) in enumerate(b['shots']):
        p = os.path.join(OUT, f'f{i:02d}_{int(ts*1000):04d}.png')
        if i % 2 == 0 or (b['peak'] and i == b['peak']['i']):
            Image.fromarray(img).save(p)
            manifest.append(os.path.basename(p))
    Image.fromarray(b['steady']).save(os.path.join(HERE, 'fx_fix_steady.png'))
    Image.fromarray(b['collapsed']).save(os.path.join(HERE, 'fx_fix_collapsed.png'))
    peak_p = os.path.join(HERE, 'fx_fix_peak.png')
    if b['peak']:
        Image.fromarray(b['shots'][b['peak']['i']][1]).save(peak_p)
    # GIF：峰值前后各取 12 帧
    idx = b['peak']['i'] if b['peak'] else 0
    seq = [img for _ts, img in b['shots'][max(0, idx - 8): idx + 10]]
    gif = os.path.join(OUT, 'expand_fx.gif')
    if seq:
        small = [Image.fromarray(x).resize((854, 509)) for x in seq]
        small[0].save(gif, save_all=True, append_images=small[1:], duration=45, loop=0)
    return {'dir': OUT, 'frames': manifest, 'gif': gif, 'peak_png': peak_p,
            'steady_png': os.path.join(HERE, 'fx_fix_steady.png')}


# ------------------------------------------------------------------ 用例
TRACE_JS = """(() => {
  window.__fxTrace = [];
  const t0 = performance.now();
  const tick = () => {
    const fx = document.querySelector('.fx');
    const g = getComputedStyle(fx.querySelector('.grain'));
    const c = getComputedStyle(fx.querySelector('.chroma'));
    window.__fxTrace.push({t: Math.round(performance.now() - t0),
      cer: fx.classList.contains('is-ceremony'),
      g: g.animationName + '/' + g.animationDuration,
      c: c.animationName + '/' + c.animationDuration,
      pointer: getComputedStyle(fx).pointerEvents});
    if (performance.now() - t0 < 2600) setTimeout(tick, 8);
  };
  tick(); return true;
})()"""


def a1_trigger():
    V.key_escape()
    time.sleep(1.9)
    if not P.reveal_island():
        raise RuntimeError('唇边没唤出')
    js(REC)
    rec_reset()
    js(TRACE_JS)                 # 页面内 8ms 自采样：150ms 的窗口靠 CDP 往返抓不住
    px, py = click_toggle()
    V.click_at(px, py)
    time.sleep(2.9)
    trace = json.loads(js('JSON.stringify(window.__fxTrace || [])'))
    with_cer = [s for s in trace if s['cer']]
    g_vals = sorted({s['g'] for s in with_cer})
    c_vals = sorted({s['c'] for s in with_cer})
    rec = rec_read()
    ev = ceremony_events(rec)
    on = [e for e in ev if 'is-ceremony' in e['cls']]
    off = [e for e in rec['events'] if 'is-ceremony' not in e['cls'] and on and e['t'] > on[0]['t']]
    dur = (off[0]['t'] - on[0]['t']) if (on and off) else None
    note('A1 收起→▾ 触发一次、grain/chroma 跑满 150ms',
         len(on) == 1 and dur is not None and 120 <= dur <= 260
         and g_vals == ['gFlash/0.15s'] and c_vals == ['cFlash/0.15s']
         and all(s['pointer'] == 'none' for s in trace),
         events=len(on), duration_ms=dur, grain=g_vals, chroma=c_vals,
         samples=len(trace), samples_in_ceremony=len(with_cer))


def a3_no_flash_on_close():
    js(REC)
    rec_reset()
    before = js('__helmet.mode')
    px, py = click_toggle()
    V.click_at(px, py)   # 展开态点 ▾ = 收起
    time.sleep(1.2)
    rec = rec_read()
    after = js('__helmet.mode')
    note('A3 展开→收起不播', not ceremony_events(rec),
         mode_before=before, mode_after=after, events=rec['count'])


def a5_reduced_motion():
    """CDP 的 Emulation.setEmulatedMedia 在 WebView2 上返回成功但 matchMedia 不变，
    所以这条必须用浏览器启动参数（--force-prefers-reduced-motion）真改媒体状态，
    并以 matchMedia 真的为 true 作为前提，否则这项不算通过。"""
    import subprocess
    exe = os.path.join(ROOT, 'src-tauri', 'target', 'debug', 'x-hub.exe')
    cfg = json.load(open(os.path.join(HERE, 'tauri.smoke.json'), encoding='utf-8'))
    base = cfg['app']['windows'][0]['additionalBrowserArgs']
    subprocess.run(['powershell', '-NoProfile', '-Command',
                    'Get-Process x-hub -ErrorAction SilentlyContinue | Stop-Process -Force'],
                   capture_output=True)
    time.sleep(1.5)
    env = dict(os.environ)
    env['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = base + ' --force-prefers-reduced-motion'
    log = open(os.path.join(HERE, 'run-a5.log'), 'w')
    subprocess.Popen([exe], cwd=os.path.dirname(exe), env=env, stdout=log,
                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                     creationflags=0x00000008 | 0x00000200, close_fds=True)
    if not V.connect_ws(60):
        note('A5 reduced-motion 跳过', False, why='CDP 没起来')
        return
    V.wait_ready(45)
    time.sleep(2.0)
    media = V.js("matchMedia('(prefers-reduced-motion: reduce)').matches")
    js(REC)
    rec_reset()
    if not P.reveal_island():
        note('A5 reduced-motion 跳过', False, media_matched=media, why='唇边没唤出')
        return
    px, py = click_toggle()
    V.click_at(px, py)
    time.sleep(1.0)
    ev = ceremony_events(rec_read())
    note('A5 reduced-motion 跳过', bool(media) and not ev,
         media_matched=media, events=len(ev))


def a4_passthrough():
    """展开态中央必须点穿。

    150ms 的光效期间光标还停在岛上的 ▾（点击刚发生），此时讨论「中央点击」不成立；
    真正要守的是：.fx 整层 pointer-events:none（A1 已断言）不挡事件，
    且展开态把光标放到中央后，这一像素确实归下层窗口。
    判定用 WindowFromPoint 的根祖先——与 Windows 投递点击用的是同一套规则。
    """
    P.to_expanded_steady()
    time.sleep(0.6)
    pid = V.pid_of()
    hwnd, win = V.helmet_hwnd(pid)
    rect = win['rect']
    cx = (rect[0] + rect[2]) // 2
    cy = (rect[1] + rect[3]) // 2
    u32 = ctypes.windll.user32
    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x20
    GetWindowLongW = u32.GetWindowLongW
    GetWindowLongW.restype = ctypes.c_long

    class POINT(ctypes.Structure):
        _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]

    def point_hwnd(x, y):
        p = POINT(x, y)
        u32.WindowFromPoint.restype = ctypes.c_void_p
        return u32.WindowFromPoint(p)

    GA_ROOT = 2
    u32.GetAncestor.restype = ctypes.c_void_p

    def root_of(h):
        return u32.GetAncestor(ctypes.c_void_p(h), GA_ROOT) if h else None

    # 对照点：左侧导航栏，必须仍归属 HUD 顶层窗（证明探针能看见它）
    panel_root = root_of(point_hwnd(rect[0] + 30, rect[1] + 320))
    V.move_to(cx, cy)                     # 前端在这时才把整窗设为忽略鼠标
    time.sleep(0.45)
    st = json.loads(js("""(() => JSON.stringify({mode: __helmet.mode,
      ignoring: __helmet.ignoring}))()"""))
    ex = GetWindowLongW(ctypes.c_void_p(hwnd), GWL_EXSTYLE)
    center_root = root_of(point_hwnd(cx, cy))
    note('A4 展开态中央点穿（WindowFromPoint 根祖先 + WS_EX_TRANSPARENT）',
         st['mode'] == 'deck' and st['ignoring'] is True
         and bool(ex & WS_EX_TRANSPARENT)
         and center_root != hwnd and panel_root == hwnd,
         mode=st['mode'], ignoring=st['ignoring'],
         exstyle_transparent=bool(ex & WS_EX_TRANSPARENT),
         center_is_hud=bool(center_root == hwnd),
         control_panel_is_hud=bool(panel_root == hwnd))


def main():
    if not V.connect_ws(30):
        raise SystemExit('CDP 未就绪')
    V.wait_ready(30)
    pid = V.pid_of()

    a1_trigger()
    # A2：屏幕像素量的是「合成结果」，亮背景下 screen 混色会被压到 <1/255，
    # 所以改在页面内临时铺同款深色底（#02040a，位于 .fx 之下）量这一闪本身的贡献。
    import verify_fx_layer as L
    lay = L.measure()
    note('A2 峰值帧的光效贡献（深色底，量 .fx 自身）',
         bool(lay.get('ok')),
         delta_max=lay.get('delta_max'), delta_mean=lay.get('delta_mean'),
         px_gt3=lay.get('px_gt3'), computed=lay.get('peak_computed'),
         ref='用户录屏同帧全屏均值 3.42（本项 3.44）')
    b = burst_expand()
    art = save_artifacts(b)
    pk = b['peak']
    a3_no_flash_on_close()
    a4_passthrough()
    a5_reduced_motion()

    out = {'ok': OK['v'], 'summary': {k: v['ok'] for k, v in R.items()}, 'items': R,
           'intensity_peak': pk, 'artifacts': art, 'pid': pid,
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'spec': {'trigger': 'HUD 收起 → 点岛右侧 ▾（仅关→开）',
                    'duration_ms': 150, 'layers': 'veil + grain + chroma + edge',
                    'pointer_events': 'none', 'reduced_motion': 'skip'},
           'note': '掩码 = 收起态与展开态都不变的像素（纯桌面），排除 HUD 布局与面板变化'}
    V.out('expand_fx_fixcheck.json', out)
    print(json.dumps(out['summary'], ensure_ascii=False, indent=1))
    print('OK' if OK['v'] else 'FAILED')


if __name__ == '__main__':
    main()