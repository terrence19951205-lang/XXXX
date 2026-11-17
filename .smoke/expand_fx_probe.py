"""展开全屏光效：强度测量 + 调参（真窗口、真鼠标、系统截屏）。

用法：
  python expand_fx_probe.py hold now            # 当前 CSS 的峰值强度（定格态）
  python expand_fx_probe.py hold p1|p2|p3       # 注入预设再测
  python expand_fx_probe.py burst [outdir]      # 真动画连拍 + GIF 帧
  python expand_fx_probe.py all                 # 依次测 now/p1/p2/p3 + burst(now)

峰值定格用 `.is-ceremony-hold`（方向稿同款取证态），静态图无时序竞态；
真动画另走 burst，逐帧与展开稳态比对。所有 delta 都是「仪式帧 vs 展开稳态」，
只反映光效本身，不掺 HUD 布局变化。
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verify_v10 as V  # noqa: E402

SCALE_HINT = 'png'

# ---------------------------------------------------------------- 预设
PRESETS = {
    # 当前进库值：白噪 0.5 + 极淡 chroma，无 veil
    'now': '',
    # p1：加一层淡冷色 veil + chroma 提亮到全宽可见
    'p1': """
.fx .veil{position:absolute;inset:0;opacity:0;pointer-events:none;
  background:linear-gradient(180deg,rgba(10,16,28,.20),rgba(6,10,18,.26) 55%,rgba(10,16,28,.18));}
.fx.is-ceremony-hold .veil{opacity:.9}
.fx .chroma{background:linear-gradient(90deg,rgba(255,46,151,.28),rgba(255,46,151,.10) 18%,
  transparent 42%,transparent 58%,rgba(0,229,255,.10) 82%,rgba(0,229,255,.28));}
.fx.is-ceremony-hold .chroma{opacity:.9}
.fx.is-ceremony-hold .grain{opacity:.14}
""",
    # p2：再强一档
    'p2': """
.fx .veil{position:absolute;inset:0;opacity:0;pointer-events:none;
  background:linear-gradient(180deg,rgba(10,16,28,.26),rgba(6,10,18,.34) 55%,rgba(10,16,28,.24));}
.fx.is-ceremony-hold .veil{opacity:1}
.fx .chroma{background:linear-gradient(90deg,rgba(255,46,151,.36),rgba(255,46,151,.14) 20%,
  transparent 44%,transparent 56%,rgba(0,229,255,.14) 80%,rgba(0,229,255,.36));}
.fx.is-ceremony-hold .chroma{opacity:1}
.fx.is-ceremony-hold .grain{opacity:.18}
""",
    # p3：veil 中等 + chroma 拉满，靠中心径向补一点冷光
    'p3': """
.fx .veil{position:absolute;inset:0;opacity:0;pointer-events:none;
  background:
    radial-gradient(ellipse 80% 70% at 50% 45%,rgba(90,150,190,.10),transparent 70%),
    linear-gradient(180deg,rgba(10,16,28,.24),rgba(6,10,18,.32) 55%,rgba(10,16,28,.22));}
.fx.is-ceremony-hold .veil{opacity:1}
.fx .chroma{background:linear-gradient(90deg,rgba(255,46,151,.42),rgba(255,46,151,.16) 20%,
  transparent 44%,transparent 56%,rgba(0,229,255,.16) 80%,rgba(0,229,255,.42));}
.fx.is-ceremony-hold .chroma{opacity:1}
.fx.is-ceremony-hold .grain{opacity:.16}
""",
}


# ---------------------------------------------------------------- 抓屏
def rect_now():
    pid = V.pid_of()
    _h, win = V.helmet_hwnd(pid)
    return win['rect']


def grab(rect):
    import mss
    mon = {'left': rect[0], 'top': rect[1], 'width': rect[2] - rect[0],
           'height': rect[3] - rect[1]}
    with mss.mss() as sct:
        shot = sct.grab(mon)
    a = np.asarray(shot)  # BGRA
    return a[:, :, :3][:, :, ::-1].copy()  # → RGB


def diff_stats(a, b):
    d = np.abs(a.astype(np.int16) - b.astype(np.int16))
    g = d.mean(axis=2)
    h, w = g.shape
    left = g[:, : int(w * 0.18)]
    right = g[:, int(w * 0.82):]
    mid = g[int(h * 0.25): int(h * 0.75), int(w * 0.3): int(w * 0.7)]
    rgb_mean = d.reshape(-1, 3).mean(axis=0)
    return {
        'mean': round(float(g.mean()), 2),
        'p99': round(float(np.percentile(g, 99)), 1),
        'max': int(g.max()),
        'left_mean': round(float(left.mean()), 2),
        'right_mean': round(float(right.mean()), 2),
        'center_mean': round(float(mid.mean()), 2),
        'rgb_mean': [round(float(x), 2) for x in rgb_mean],
    }


# ---------------------------------------------------------------- 状态
def reveal_island():
    """贴顶唇边要「由下往上」靠近才唤出：一步跳到 y=2 有时不触发 pointermove"""
    pid = V.pid_of()
    _h, win = V.helmet_hwnd(pid)
    r = win['rect']
    cx = r[0] + (r[2] - r[0]) / 2
    V.move_to(cx, r[1] + 70)
    for y in (24, 10, 5):
        V.move_to(cx, r[1] + y)
        time.sleep(0.3)
    time.sleep(1.0)
    return V.js('__helmet.geo') == 'band'


def island_visible():
    st = V.js("JSON.stringify({mode:__helmet.mode,geo:__helmet.geo,docked:__helmet.docked})")
    import json as _json
    try:
        d = _json.loads(st) if isinstance(st, str) else st
    except Exception:
        d = {}
    return (not d.get('docked')) and d.get('geo') in ('band', 'full')


def ensure_island_visible():
    """lip/贴顶才唤岛；已是 band/full 且未 docked 则直接可用，不要硬走唇边。"""
    if island_visible():
        return True
    return reveal_island() or island_visible()


def to_expanded_steady():
    """HUD 展开且不在仪式里：连按 Esc 到 idle，必要时唤岛，再点 ▾ 展开"""
    for _ in range(3):
        m = V.js('__helmet.mode')
        if m == 'idle':
            break
        V.key_escape()
        time.sleep(1.6)
    if V.js('__helmet.mode') != 'idle':
        raise RuntimeError('回不到 idle：' + str(V.js('__helmet.mode')))
    if not ensure_island_visible():
        raise RuntimeError('岛未可见：' + str(V.js('JSON.stringify({geo:__helmet.geo,docked:__helmet.docked})')))
    click_css('.island-toggle', 1.4)
    if not V.js("!!document.querySelector('.hud.is-open')"):
        raise RuntimeError('点 ▾ 没展开')


def click_css(sel, settle=0.9):
    pid = V.pid_of()
    _h, win = V.helmet_hwnd(pid)
    rect = win['rect']
    sc = (rect[2] - rect[0]) / max(1, V.js('innerWidth'))
    pt = V.screen_pt(sel)
    if not pt:
        raise RuntimeError('no element ' + sel)
    px, py = V.to_screen(pt, rect, sc)
    V.move_to(px, py)
    time.sleep(0.35)
    V.click_at(px, py)
    time.sleep(settle)
    return {'css': pt, 'screen': [round(px), round(py)]}


def inject(css):
    return V.js("""(() => {
      const fx = document.querySelector('.fx');
      if (!fx) return false;
      let veil = fx.querySelector('.veil');
      if (!veil) { veil = document.createElement('div'); veil.className = 'veil'; fx.appendChild(veil); }
      let st = document.getElementById('fx-probe-style');
      if (!st) { st = document.createElement('style'); st.id = 'fx-probe-style'; document.head.appendChild(st); }
      st.textContent = %s;
      return true;
    })()""" % json.dumps(css))


def hold_on(on=True):
    return V.js("""(() => {
      const fx = document.querySelector('.fx');
      if (!fx) return false;
      fx.classList.toggle('is-ceremony-hold', %s);
      fx.classList.toggle('is-on', true);
      return true;
    })()""" % ('true' if on else 'false'))


def measure_hold(name):
    css = PRESETS.get(name, '')
    inject(css)
    to_expanded_steady()
    hold_on(False)
    time.sleep(0.3)
    rect = rect_now()
    steady = grab(rect)
    hold_on(True)
    time.sleep(0.35)
    peak = grab(rect)
    hold_on(False)
    st = diff_stats(peak, steady)
    st['preset'] = name
    return st, peak, steady


def burst(tag='p1', frames=26, gap=0.03):
    inject(PRESETS.get(tag, ''))
    to_expanded_steady()
    hold_on(False)
    time.sleep(0.4)
    rect = rect_now()
    steady = grab(rect)
    # 收起 → 唇边唤出 → 点 ▾ 展开
    V.key_escape()
    time.sleep(1.9)
    if V.js('__helmet.mode') != 'idle':
        raise RuntimeError('收起失败')
    pid = V.pid_of()
    if not ensure_island_visible():
        raise RuntimeError('岛未可见')
    _h, win = V.helmet_hwnd(pid)
    sc = (win['rect'][2] - win['rect'][0]) / max(1, V.js('innerWidth'))
    pt = V.screen_pt('.island-toggle')
    px, py = V.to_screen(pt, win['rect'], sc)
    V.move_to(px, py)
    time.sleep(0.7)
    V.click_at(px, py)

    shots = []
    t0 = time.time()
    for i in range(frames):
        shots.append((time.time() - t0, grab(rect)))
        time.sleep(gap)
    stats = []
    for i, (ts, img) in enumerate(shots):
        s = diff_stats(img, steady)
        s['i'] = i
        s['t'] = round(ts * 1000)
        stats.append(s)
    outdir = os.path.join(HERE, 'fx_burst')
    os.makedirs(outdir, exist_ok=True)
    from PIL import Image
    for i, (ts, img) in enumerate(shots):
        Image.fromarray(img).save(os.path.join(outdir, f'f{i:02d}_{int(ts*1000):04d}.png'))
    best = max(stats, key=lambda s: s['mean'])
    Image.fromarray(shots[best['i']][1]).save(os.path.join(HERE, 'fx_peak.png'))
    return {'tag': tag, 'steady': os.path.join(HERE, 'fx_steady.png'),
            'frames': len(shots), 'best': best, 'stats': stats,
            'dir': outdir}, steady


def main():
    if not V.connect_ws(30):
        raise SystemExit('CDP 未就绪')
    V.wait_ready(30)
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    res = {}
    if mode in ('hold', 'all'):
        want = [sys.argv[2]] if (mode == 'hold' and len(sys.argv) > 2) else ['now', 'p1', 'p2', 'p3']
        for name in want:
            st, peak, steady = measure_hold(name)
            from PIL import Image
            Image.fromarray(peak).save(os.path.join(HERE, f'fx_hold_{name}.png'))
            Image.fromarray(steady).save(os.path.join(HERE, 'fx_steady.png'))
            res[name] = st
            print('HOLD', name, json.dumps(st, ensure_ascii=False), flush=True)
    if mode in ('burst', 'all'):
        tag = sys.argv[2] if (mode == 'burst' and len(sys.argv) > 2) else 'now'
        b, steady = burst(tag)
        res['burst'] = b
        print('BURST', json.dumps(b['best'], ensure_ascii=False), flush=True)
        print('BURST all', json.dumps(b['stats'], ensure_ascii=False)[:1200], flush=True)
    print(json.dumps(res, ensure_ascii=False)[:4000])


if __name__ == '__main__':
    main()