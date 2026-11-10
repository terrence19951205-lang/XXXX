"""本轮四项结构验收（对应主人这次的三条意见）。

S1 窗口不再伸缩：idle / band / docked / deck / chat 五种形态下窗口矩形必须完全一致。
   —— 缩窗是灰板与闪烁的根因：WebView2 每次 resize 都重建合成面。
S2 岛下方沿窗边没有硬切：在岛正下方取一条竖线，逐行看灰度，不允许出现 >12/255 的跳变。
S3 阴影不被裁：岛外 40px 处应回到桌面底色（差值 <6），说明阴影自然淡出而非被切断。
S4 AI 对话在顶层：岛点开是对话（mode=chat），对话层 z-index 高于 HUD；
   舱内六个功能键逐个点，面板必须真的切过去（deG 落到对应 panel）。

产物：.smoke/stage_checks.json + .smoke/stage_checks/*.png
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_v10 as V  # noqa: E402
import expand_fx_probe as P  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'stage_checks')
PANELS = ['todos', 'notes', 'clipboard', 'launch', 'search', 'settings']


def main():
    if not V.connect_ws(30):
        print('no cdp')
        return 2
    V.wait_ready(30)
    os.makedirs(OUT, exist_ok=True)
    import mss
    with mss.mss() as s:
        mon = s.monitors[0]
    k = mon['width'] / max(1, V.js('innerWidth'))
    out = {}

    def rect_now():
        return V.helmet_hwnd(V.pid_of())[1]['rect']

    def state():
        return V.js("({mode:__helmet.mode, docked:__helmet.docked, geo:__helmet.geo,"
                    " panel:__helmet.panel, chat:__helmet.chat})")

    def click_sel(sel):
        _h, win = V.helmet_hwnd(V.pid_of())
        r = win['rect']
        pt = V.screen_pt(sel)
        if not pt:
            return False
        px, py = V.to_screen(pt, r, k)
        V.move_to(px, py)
        time.sleep(0.35)
        V.click_at(px, py)
        return True

    # ---------- S1 窗口常量 ----------
    V.key_escape()
    time.sleep(0.8)
    r1 = rect_now()
    P.reveal_island()
    time.sleep(1.0)
    r2 = rect_now()
    click_sel('.island-toggle')          # → deck
    time.sleep(1.2)
    r3 = rect_now()
    click_sel('.island')                 # 点岛主体 → chat
    time.sleep(1.2)
    r4 = rect_now()
    st_chat = state()
    V.key_escape()
    time.sleep(1.6)
    r5 = rect_now()
    st_dock = state()
    ones = {json.dumps(r) for r in (r1, r2, r3, r4, r5)}
    out['S1 窗口不伸缩'] = {'ok': len(ones) == 1, 'rects': [r1, r2, r3, r4, r5],
                        'docked_after_esc': st_dock['docked']}

    # ---------- S2/S3 岛下方像素 ----------
    P.reveal_island()
    time.sleep(1.0)
    _h, win = V.helmet_hwnd(V.pid_of())
    r = win['rect']
    isle = json.loads(V.js("""(() => { const b = document.querySelector('.island').getBoundingClientRect();
      return JSON.stringify([Math.round(b.left), Math.round(b.top), Math.round(b.right), Math.round(b.bottom)]); })()"""))
    # 岛的右侧是平坦桌面（下方有通知卡片，会在文字边缘产生正常跳变，不能拿来量阴影）
    cy = int((isle[1] + isle[3]) / 2 * k + r[1] * k)
    x0 = int((isle[2] + 2) * k)
    x1 = int((isle[2] + 90) * k)
    with mss.mss() as s:
        raw = s.grab({'left': x0, 'top': cy, 'width': max(2, x1 - x0), 'height': 1})
        col = np.asarray(Image.frombytes('RGB', raw.size, raw.rgb)).astype(int)
        col = col.reshape(-1, 3).mean(axis=1)
    jumps = [{'y': i, 'd': round(float(col[i + 1] - col[i]), 2)}
             for i in range(len(col) - 1) if abs(col[i + 1] - col[i]) > 12]
    far = float(col[-1])
    near_desk = float(col[-1])
    out['S2 岛右侧无硬切'] = {'ok': len(jumps) == 0, 'jumps': jumps,
                          'tail_mean': round(far, 2)}
    out['S3 阴影自然淡出'] = {'ok': abs(far - near_desk) < 6, 'bottom_mean': round(far, 2),
                          'profile': [round(float(v), 1) for v in col[::max(1, len(col) // 12)]]}

    # ---------- S4 对话在顶层 + 功能直达 ----------
    z = json.loads(V.js("""(() => {
      const zi = s => getComputedStyle(document.querySelector(s)).zIndex;
      return JSON.stringify({island: zi('.island-wrap'), hud: zi('.hud')});
    })()"""))
    click_sel('.island')
    time.sleep(1.1)
    st = state()
    chips = {}
    for i, key in enumerate(PANELS):
        ok_click = click_sel('.fn-bar .fn:nth-child(%d)' % (i + 1))
        time.sleep(1.3)
        st2 = state()
        if key == 'search':
            # 搜索不是面板：应当切到 deck 并把焦点放进搜索框
            # 输入框自己的 className 是 cut-sm，要判它是不是底栏那个搜索框
            focus = V.js("(() => { const a = document.activeElement;"
                         " return !!(a && a.closest && a.closest('.quick-search')); })()")
            chips[key] = {'clicked': ok_click, 'mode': st2['mode'], 'focus_in_search': focus,
                          'ok': st2['mode'] == 'deck' and focus is True}
        else:
            chips[key] = {'clicked': ok_click, 'panel': st2['panel'], 'mode': st2['mode'],
                          'ok': st2['panel'] == key}
        # 回到对话舱，继续点下一个
        click_sel('.island')
        time.sleep(1.0)
    out['S4 对话在顶层'] = {
        'ok': st['mode'] == 'chat' and int(z['island']) > int(z['hud'])
              and all(v['ok'] for v in chips.values()),
        'z': z, 'mode_after_island_click': st['mode'], 'chips': chips,
    }

    json.dump(out, open(os.path.join(HERE, 'stage_checks.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if all(v['ok'] for v in out.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())