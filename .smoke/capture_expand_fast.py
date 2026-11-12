# -*- coding: utf-8 -*-
import json, os, sys, time, subprocess, ctypes
from ctypes import wintypes
from pathlib import Path

HERE = Path(r'.smoke')
sys.path.insert(0, str(HERE))
import verify_v10 as V
import expand_fx_probe as P

FFMPEG = r'C:\Users\wcy\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0-full_build\bin\ffmpeg.exe'
OUT = HERE / 'fx_fast'
OUT.mkdir(exist_ok=True)
MP4 = OUT / 'expand_ceremony.mp4'
LOG = OUT / 'ffmpeg.log'
FRAMES = OUT / 'frames'
if FRAMES.exists():
    for f in FRAMES.glob('*.png'):
        f.unlink()
else:
    FRAMES.mkdir()

R = {}


def js(e):
    return V.js(e)


def hud():
    return json.loads(js('JSON.stringify({mode:__helmet.mode,geo:__helmet.geo,docked:__helmet.docked,panel:__helmet.panel,ignoring:__helmet.ignoring})'))


def main():
    if not V.connect_ws(20):
        raise SystemExit('no cdp')
    V.wait_ready(20)
    pid = V.pid_of()
    print('pid', pid, 'pre', hud())

    for _ in range(4):
        if js('__helmet.mode') == 'idle':
            break
        V.key_escape()
        time.sleep(1.0)
    if js('__helmet.mode') != 'idle':
        raise RuntimeError('not idle ' + str(hud()))
    if not P.ensure_island_visible():
        raise RuntimeError('island not visible ' + str(hud()))
    print('idle', hud())

    pe = js("getComputedStyle(document.querySelector('.fx')).pointerEvents")
    R['fx_pointer_events'] = pe

    # precompute click point while idle
    _h, win = V.helmet_hwnd(pid)
    sc = (win['rect'][2] - win['rect'][0]) / max(1, js('innerWidth'))
    pt = V.screen_pt('.island-toggle')
    px, py = V.to_screen(pt, win['rect'], sc)
    V.move_to(px, py)
    time.sleep(0.3)
    print('armed click', px, py)

    V.js("""(() => {
      window.__fxRec = {events: [], count: 0};
      const fx = document.querySelector('.fx');
      const push = () => { window.__fxRec.count++; window.__fxRec.events.push({t: Math.round(performance.now()), cls: fx.className}); };
      window.__fxRecObs && window.__fxRecObs.disconnect();
      window.__fxRecObs = new MutationObserver(push);
      window.__fxRecObs.observe(fx, {attributes: true, attributeFilter: ['class']});
      return true;
    })()""")

    with open(LOG, 'wb') as flog:
        rec = subprocess.Popen([
            FFMPEG, '-y', '-f', 'gdigrab', '-framerate', '60', '-draw_mouse', '1',
            '-i', 'desktop', '-t', '3', '-c:v', 'libx264', '-preset', 'ultrafast',
            '-crf', '18', '-pix_fmt', 'yuv420p', str(MP4)
        ], stdout=flog, stderr=subprocess.STDOUT)
        t0 = time.perf_counter()
        time.sleep(0.55)
        V.click_at(px, py)
        t_click = time.perf_counter() - t0
        print('clicked at t=', round(t_click, 3), 'state', hud())
        rec.wait(timeout=12)
    print('ffmpeg exit', rec.returncode, 'mp4', MP4.stat().st_size if MP4.exists() else 0)
    rec_data = json.loads(js('JSON.stringify(window.__fxRec || {})') or '{}')
    R['fx_rec'] = rec_data
    R['click'] = {'screen': [round(px), round(py)], 't_s': round(t_click, 3)}
    print('fx_rec', rec_data)

    extlog = OUT / 'extract.log'
    with open(extlog, 'wb') as flog:
        rc = subprocess.call([
            FFMPEG, '-y', '-i', str(MP4), '-vf', 'fps=60',
            str(FRAMES / 'f%04d.png')
        ], stdout=flog, stderr=subprocess.STDOUT)
    frames = sorted(FRAMES.glob('f*.png'))
    print('extract', rc, 'n=', len(frames))

    # passthrough on the right document area and geometric center
    time.sleep(0.6)
    _h, win = V.helmet_hwnd(pid)
    rect = win['rect']
    tx = int(rect[0] + (rect[2]-rect[0]) * 0.78)
    ty = int(rect[1] + (rect[3]-rect[1]) * 0.55)
    cx = (rect[0] + rect[2]) // 2
    cy = (rect[1] + rect[3]) // 2
    u32 = ctypes.windll.user32
    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x20

    class POINT(ctypes.Structure):
        _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]

    def point_hwnd(x, y):
        p = POINT(x, y)
        u32.WindowFromPoint.restype = ctypes.c_void_p
        return u32.WindowFromPoint(p)

    u32.GetAncestor.restype = ctypes.c_void_p

    def root_of(h):
        return u32.GetAncestor(ctypes.c_void_p(h), 2) if h else None

    V.move_to(tx, ty)
    time.sleep(0.5)
    st_r = json.loads(js('JSON.stringify({mode:__helmet.mode, ignoring:__helmet.ignoring})'))
    ex_r = u32.GetWindowLongW(ctypes.c_void_p(_h), GWL_EXSTYLE)
    right_root = root_of(point_hwnd(tx, ty))
    V.move_to(cx, cy)
    time.sleep(0.45)
    st_c = json.loads(js('JSON.stringify({mode:__helmet.mode, ignoring:__helmet.ignoring})'))
    ex_c = u32.GetWindowLongW(ctypes.c_void_p(_h), GWL_EXSTYLE)
    center_root = root_of(point_hwnd(cx, cy))
    panel_root = root_of(point_hwnd(rect[0] + 30, rect[1] + 320))
    pe2 = js("getComputedStyle(document.querySelector('.fx')).pointerEvents")
    R['passthrough'] = {
        'right': {'xy': [tx, ty], 'ignoring': st_r.get('ignoring'),
                  'is_hud': bool(right_root == _h),
                  'ex_transparent': bool(ex_r & WS_EX_TRANSPARENT)},
        'center': {'xy': [cx, cy], 'ignoring': st_c.get('ignoring'),
                   'is_hud': bool(center_root == _h),
                   'ex_transparent': bool(ex_c & WS_EX_TRANSPARENT)},
        'panel_is_hud': bool(panel_root == _h),
        'mode': st_r.get('mode'),
        'fx_pointer_events': pe2,
    }
    print('passthrough', json.dumps(R['passthrough'], ensure_ascii=False))

    R['pid'] = pid
    R['mp4'] = str(MP4.resolve())
    R['frames_dir'] = str(FRAMES.resolve())
    R['n_frames'] = len(frames)
    (HERE / 'fx_fast_result.json').write_text(json.dumps(R, ensure_ascii=False, indent=2), encoding='utf-8')
    print('WROTE fx_fast_result.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())