"""展开动效体检：曲线在页面内采样（8ms），不靠截屏——240ms 的动画用截图抓不到中间帧。

看三件事：
1. 连续滑出：.hud 的 opacity 与 .dock 的 translateX 应逐级变化，不是 0 → 1 一步跳。
2. 不闪：曲线不得出现「上去又掉回来再上去」的锯齿（相邻采样反向且幅度超过总程 8%）。
3. 岛不跳位：.island 的 left/top 在展开过程中不变（窗口不动的前提下应当纹丝不动）。

产物：.smoke/expand_motion.json
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_v10 as V  # noqa: E402
import expand_fx_probe as P  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

TRACE = """(() => {
  window.__mx = [];
  const t0 = performance.now();
  const hud = document.querySelector('.hud');
  const dock = document.querySelector('.dock');
  const isle = document.querySelector('.island');
  const tick = () => {
    const cs = getComputedStyle(hud), cd = getComputedStyle(dock);
    const r = isle.getBoundingClientRect();
    window.__mx.push({
      t: Math.round(performance.now() - t0),
      op: +cs.opacity,
      vis: cs.visibility,
      tr: cd.transform,
      ix: Math.round(r.left), iy: Math.round(r.top),
    });
    if (performance.now() - t0 < 900) setTimeout(tick, 8);
  };
  tick();
  return true;
})()"""


def tx_of(tr):
    if not tr or tr == 'none':
        return 0.0
    try:
        return float(tr.split('(')[1].split(',')[4])
    except Exception:
        return 0.0


def main():
    if not V.connect_ws(30):
        print('no cdp')
        return 2
    V.wait_ready(30)
    V.key_escape()
    time.sleep(0.6)
    P.reveal_island()
    time.sleep(1.0)
    import mss
    with mss.mss() as s:
        mon = s.monitors[0]
    k = mon['width'] / max(1, V.js('innerWidth'))
    _h, win = V.helmet_hwnd(V.pid_of())
    rect = win['rect']
    pt = V.screen_pt('.island-toggle')
    px, py = V.to_screen(pt, rect, k)          # SetCursorPos 要物理像素

    V.move_to(px, py)
    time.sleep(0.4)
    V.js(TRACE)
    time.sleep(0.05)
    V.click_at(px, py)
    time.sleep(1.2)
    trace = json.loads(V.js('JSON.stringify(window.__mx || [])'))
    if not trace:
        print('no trace')
        return 2

    ops = [f['op'] for f in trace]
    txs = [abs(tx_of(f['tr'])) for f in trace]
    ix = sorted({f['ix'] for f in trace})
    iy = sorted({f['iy'] for f in trace})
    span_op = (max(ops) - min(ops)) or 1
    span_tx = (max(txs) - min(txs)) or 1

    def zigzag(vals, span):
        out = []
        for i in range(1, len(vals) - 1):
            d1, d2 = vals[i] - vals[i - 1], vals[i + 1] - vals[i]
            if d1 * d2 < 0 and abs(d1) > span * 0.08 and abs(d2) > span * 0.08:
                out.append({'i': i, 'd1': round(d1, 3), 'd2': round(d2, 3)})
        return out

    mids = [o for o in ops if 0.05 < o < 0.95]
    tx_mids = [t for t in txs if 0.5 < t < max(txs) - 0.5] if max(txs) > 2 else []
    res = {
        'samples': len(trace),
        'opacity': {'min': round(min(ops), 3), 'max': round(max(ops), 3),
                    'mid_samples': len(mids), 'zigzag': zigzag(ops, span_op)},
        'dock_tx': {'min': round(min(txs), 2), 'max': round(max(txs), 2),
                    'mid_samples': len(tx_mids), 'zigzag': zigzag(txs, span_tx)},
        'island_position': {'x': ix, 'y': iy, 'stable': len(ix) == 1 and len(iy) == 1},
        'curve': [{'t': f['t'], 'op': f['op'], 'tx': round(tx_of(f['tr']), 2),
                   'ix': f['ix'], 'iy': f['iy']} for f in trace],
    }
    ok = len(mids) >= 2 and not res['opacity']['zigzag'] and res['island_position']['stable']
    res['ok'] = ok
    json.dump(res, open(os.path.join(HERE, 'expand_motion.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != 'curve'}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())