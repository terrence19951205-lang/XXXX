"""量这一闪光效本身：在页面里临时铺一张深色底（#02040a，同参考稿 --void，
层序在 .fx 之下、面板之上），把「浅色桌面把 screen 混色压成 0」这个干扰去掉，
再系统截屏对比「无仪式」与「仪式卡在 40% 峰值」两帧。测完立即移除，不留状态。

产物：.smoke/fx_layer.json + .smoke/fx_layer/{base,peak,diff_x24}.png
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verify_v10 as V  # noqa: E402
import expand_fx_probe as P  # noqa: E402

OUT = os.path.join(HERE, 'fx_layer')

INJECT = """(() => {
  let d = document.getElementById('fx-probe-dark');
  if (!d) {
    d = document.createElement('div');
    d.id = 'fx-probe-dark';
    d.style.cssText = 'position:fixed;inset:0;z-index:29;background:#02040a;pointer-events:none';
    document.body.appendChild(d);
  }
  const fx = document.querySelector('.fx');
  fx.classList.add('is-on');
  fx.classList.remove('is-ceremony', 'is-flashout');
  for (const el of fx.querySelectorAll('.grain,.chroma')) {
    el.style.animation = 'none'; el.style.opacity = '0';
  }
  return true;
})()"""

PEAK = """(() => {
  const fx = document.querySelector('.fx');
  fx.classList.add('is-ceremony');
  for (const el of fx.querySelectorAll('.grain,.chroma')) {
    el.style.animation = '';
    el.style.animationDelay = '-60ms';
    el.style.animationPlayState = 'paused';
  }
  const c = getComputedStyle(fx.querySelector('.chroma'));
  const g = getComputedStyle(fx.querySelector('.grain'));
  return c.opacity + '|' + g.opacity + '|' + c.animationName + '|' + g.animationName;
})()"""

RESTORE = """(() => {
  const d = document.getElementById('fx-probe-dark');
  if (d) d.remove();
  const fx = document.querySelector('.fx');
  fx.classList.remove('is-ceremony', 'is-flashout');
  for (const el of fx.querySelectorAll('.grain,.chroma')) {
    el.style.animation = ''; el.style.opacity = '';
    el.style.animationDelay = ''; el.style.animationPlayState = '';
  }
  return true;
})()"""


def measure():
    """跑一次峰值测量，返回结果 dict（不改应用状态）。"""
    if not V.connect_ws(30):
        return {'ok': False, 'why': 'cdp'}
    os.makedirs(OUT, exist_ok=True)
    rect = P.rect_now()
    V.js(INJECT)
    time.sleep(0.45)
    base = P.grab(rect)
    Image.fromarray(base).save(os.path.join(OUT, 'base.png'))
    op = V.js(PEAK)
    time.sleep(0.45)
    peak = P.grab(rect)
    Image.fromarray(peak).save(os.path.join(OUT, 'peak.png'))
    V.js(RESTORE)

    d = np.abs(peak.astype(np.int16) - base.astype(np.int16)).max(axis=2)
    diff = np.zeros((*d.shape, 3), np.uint8)
    diff[..., 0] = np.clip(d * 24, 0, 255)
    Image.fromarray(diff).save(os.path.join(OUT, 'diff_x24.png'))
    res = {
        'ok': bool(d.max() >= 2),
        'peak_computed': op,
        'delta_max': int(d.max()),
        'delta_mean': round(float(d.mean()), 4),
        'px_gt1': int((d > 1).sum()),
        'px_gt3': int((d > 3).sum()),
        'frame_px': int(d.size),
        'frame_shape': list(d.shape),
        'note': '深色底 #02040a（同参考稿 --void）下，峰值帧相对无仪式帧的差值；diff_x24.png 为 24 倍放大',
        'artifacts': {k: os.path.join(OUT, v) for k, v in
                      {'base': 'base.png', 'peak': 'peak.png', 'diff_x24': 'diff_x24.png'}.items()},
    }
    print(json.dumps(res, ensure_ascii=False, indent=1))
    json.dump(res, open(os.path.join(HERE, 'fx_layer.json'), 'w'), ensure_ascii=False, indent=1)
    return res


def main():
    res = measure()
    if res.get('why') == 'cdp':
        return 2
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())