"""光效本体连拍（HUD 常驻，避免窗口展开把画面全换掉造成混淆）：
手动加同一个 .is-ceremony 类（与 ▾ 展开时 watcher 调的是同一段动画），
72ms 连拍 → 与静止基线作差，量全屏 grain/chroma/edge 的真实像素变化 + 出 GIF。
用户级触发（收起态点 ▾）由 verify_v11 的 mutation 时间线 + 计数器单独取证。"""
import sys
import time

from PIL import ImageChops, ImageGrab, ImageStat

sys.path.insert(0, '.smoke')
import verify_v10 as V

V.wait_ready()
if V.state()['mode'] != 'deck':
    V.js("document.querySelector('.island-toggle').click()")
    time.sleep(2.2)
V.move_to(40, 400)
time.sleep(1.0)
print('mode', V.state()['mode'])

base = ImageGrab.grab(all_screens=True)
V.js("document.querySelector('.fx').classList.add('is-ceremony')")
t0 = time.time()
frames = []
for _ in range(8):
    frames.append((round((time.time() - t0) * 1000), ImageGrab.grab(all_screens=True)))

BOX_R = (1750, 200, 2500, 1400)
BOX_L = (0, 200, 300, 1400)


def rstat(a, b, box):
    d = ImageChops.difference(a.convert('RGB').crop(box), b.convert('RGB').crop(box))
    st = ImageStat.Stat(d)
    return [round(x, 2) for x in st.mean], max(m[1] for m in d.getextrema())


stats = []
for t, im in frames:
    r, rx = rstat(base, im, BOX_R)
    l, lx = rstat(base, im, BOX_L)
    stats.append({'ms': t, 'right_mean': r, 'right_max': rx, 'left_mean': l, 'left_max': lx})
print('stats', stats)
print('cls', V.js("document.querySelector('.fx').className"))

w, h = frames[0][1].size
small = [im.resize((1280, int(h * 1280 / w)), 1) for _, im in frames]
gif = V.HERE + '\\v11_expand_ceremony.gif'
small[0].save(gif, save_all=True, append_images=small[1:], duration=72, loop=0)
print('gif', gif)
best = max(range(len(stats)), key=lambda i: stats[i]['right_mean'][0])
frames[best][1].save(V.HERE + '\\v11_05b_expand_flash_frame.png')
print('best', best, stats[best], 'times', [s['ms'] for s in stats])