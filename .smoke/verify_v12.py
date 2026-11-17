"""v12 验收：提示词嵌聊天（选用 / 切换 / 重启仍在 / 不越界）。

只连 9222 上的 Helmet 页，真鼠标点按钮；临时 `【自测】` 三条提示词经
create_snippet 建、验完删（不碰用户原有条目）；不真的调模型，只看输入框与
发送按钮状态。结果写 .smoke/v12_result.json，截图 v12_*.png（系统截屏）。

用法：python verify_v12.py
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import verify_v10 as V  # noqa: E402  复用 CDP / 真鼠标 / 启动与重启 / 截图

R = {}
OK = {'v': True}


def js(expr):
    return V.js(expr)


def inv(cmd, args=None):
    return js(f"window.__TAURI_INTERNALS__.invoke({json.dumps(cmd)}, {json.dumps(args or {})})")


def note(item, ok, **kw):
    R[item] = {'ok': bool(ok), **kw}
    OK['v'] = OK['v'] and bool(ok)
    print(('PASS ' if ok else 'FAIL ') + item, '|',
          json.dumps(kw, ensure_ascii=False)[:400], flush=True)


# ------------------------------------------------------------------ 坐标与点击
def scale_now():
    pid = V.pid_of()
    _hwnd, win = V.helmet_hwnd(pid)
    return (win['rect'][2] - win['rect'][0]) / max(1, js('innerWidth')), win['rect']


def click_css(sel, settle=0.9):
    """真鼠标点 CSS 元素中心；先用 elementFromPoint 记落点，便于判穿/判挡"""
    sc, rect = scale_now()
    pt = V.screen_pt(sel)
    if not pt:
        return {'ok': False, 'err': 'no such element: ' + sel}
    px, py = V.to_screen(pt, rect, sc)
    V.move_to(px, py)
    time.sleep(0.45)
    hit = js("(() => { const e = document.elementFromPoint(%s, %s);"
             " return e ? (e.tagName + '.' + (e.className || '')) : null; })()"
             % (pt['x'], pt['y']))
    V.click_at(px, py)
    time.sleep(settle)
    return {'ok': True, 'css': pt, 'screen': [round(px), round(py)], 'hit_before': hit}


def sys_shot(name):
    from PIL import ImageGrab
    sc, rect = scale_now()
    p = os.path.join(HERE, name)
    ImageGrab.grab(bbox=(rect[0], rect[1], rect[2], rect[3])).save(p)
    return p


# ------------------------------------------------------------------ 舱内快照
SNAP = """JSON.stringify({
  open: !!document.querySelector('.island-chat'),
  promptBtn: !!document.querySelector('[data-prompt-open]'),
  badge: (document.querySelector('[data-prompt-open] em') || {}).textContent || '',
  pop: !!document.querySelector('[data-prompt-pop]'),
  items: Array.from(document.querySelectorAll('[data-prompt-item]')).map(e => ({
    id: Number(e.dataset.promptItem),
    title: ((e.querySelector('.pi-t') || {}).textContent || '').replace('✓ 已选用', '').trim(),
  })),
  activeItem: (function () {
    const e = document.querySelector('[data-prompt-item].is-on');
    return e ? Number(e.dataset.promptItem) : null;
  })(),
  chip: (function () {
    const e = document.querySelector('[data-prompt-chip]');
    return e ? {id: Number(e.dataset.promptId), text: e.textContent.trim()} : null;
  })(),
  text: (document.querySelector('.composer textarea') || {}).value || '',
  msgs: document.querySelectorAll('.msgs .msg').length,
  ls: localStorage.getItem('rr.hud.chatPromptId'),
  sendDisabled: !!(document.querySelector('.composer .btn.primary') || {}).disabled,
  promptDom: document.querySelectorAll('[data-prompt-open], [data-prompt-item], [data-prompt-chip]').length,
})"""


def snap():
    s = js(SNAP)
    return json.loads(s) if isinstance(s, str) else s


def set_textarea(val):
    return js("""(() => {
      const e = document.querySelector('.composer textarea');
      if (!e) return false;
      e.focus();
      const d = Object.getOwnPropertyDescriptor(e.constructor.prototype, 'value');
      if (d && d.set) d.set.call(e, %s); else e.value = %s;
      e.dispatchEvent(new Event('input', {bubbles: true}));
      return true;
    })()""" % (json.dumps(val), json.dumps(val)))


def reveal_deck():
    """把 HUD 从「贴顶收起」唤回：光标先压到屏幕顶边（岛只露一条唇边时点不到任何控件），
    等 hover 生效再继续。否则后续 click_css 会算到 y<0 的屏外坐标，点了等于没点。"""
    for _ in range(6):
        try:
            st = json.loads(js('JSON.stringify({mode:__helmet.mode, geo:__helmet.geo, docked:__helmet.docked})'))
        except Exception:  # noqa: BLE001
            return False
        if st['docked'] is False and st['mode'] != 'lip':
            return True
        sc, rect = scale_now()
        V.move_to(rect[0] + (rect[2] - rect[0]) / 2, rect[1] + 2)
        time.sleep(0.9)
    return True


def chat_open():
    reveal_deck()
    if js("!!document.querySelector('.island-chat')"):
        return True
    V.hotkey(['ctrl', 'shift'], 'k')
    time.sleep(1.4)
    return bool(js("!!document.querySelector('.island-chat')"))


def wait_boot(timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if js('!!window.__helmet && __helmet.boot === false'):
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)
    return False


# ------------------------------------------------------------------ 用例
SEEDS = [
    ('【自测】摘要提炼', '把下面的内容压成三条要点，每条不超过 20 字：'),
    ('【自测】会议纪要', '按「结论 / 待办 / 风险」整理下面的会议记录，待办要带责任人和时间：'),
    ('【自测】书面润色', '把下面的句子改成书面公文体，去掉口语和感叹号：'),
]


def seed():
    made = []
    for title, content in SEEDS:
        s = inv('create_snippet', {'title': title, 'content': content})
        made.append({'id': int(s['id']), 'title': title, 'content': content})
    return made


def cleanup(ids):
    for i in ids:
        try:
            inv('delete_snippet', {'id': i})
        except Exception as e:  # noqa: BLE001
            print('cleanup fail', i, e, flush=True)
    try:
        js("localStorage.removeItem('rr.hud.chatPromptId')")
    except Exception:  # noqa: BLE001
        pass


def main():
    p = V.pid_of()
    print('pid', p, flush=True)
    if not p:
        raise SystemExit('冒烟进程没起：先 .smoke/launch_smoke.py 或直接跑 exe')
    if not V.connect_ws(60):
        raise SystemExit('CDP 未就绪')
    V.wait_ready(60)
    wait_boot(30)

    # 种子先建（舱还没挂载 → 挂载时 list_snippets 就是三条）
    seeds = seed()
    print('seeded', seeds, flush=True)

    # ---------------------------------------------------------- V12-1 入口与列表
    opened = chat_open()
    s0 = snap()
    clicked = click_css('[data-prompt-open]')
    s1 = snap()
    list_now = inv('list_snippets') or []
    titles = {x['title'] for x in list_now}
    want = {x['title'] for x in seeds}
    note('V12-1 提示词入口与列表',
         opened and s0['promptBtn'] and clicked.get('ok') and s1['pop'] and want <= titles
         and len(s1['items']) == len(list_now),
         chat_open=opened, clicked=clicked, pop=s1['pop'],
         items=len(s1['items']), library=len(list_now), badge=s1['badge'],
         shot=sys_shot('v12_01_prompt_pop.png'))

    # ---------------------------------------------------------- V12-2 选用（不代发）
    a = seeds[0]
    before_msgs = s1['msgs']
    click_css(f"[data-prompt-item=\"{a['id']}\"]")
    s2 = snap()
    note('V12-2 选用一条：内容进输入框、不代发',
         s2['text'] == a['content'] and s2['chip'] and s2['chip']['id'] == a['id']
         and s2['ls'] == str(a['id']) and s2['msgs'] == before_msgs and not s2['pop'],
         text=s2['text'], chip=s2['chip'], ls=s2['ls'],
         msgs_before=before_msgs, msgs_after=s2['msgs'],
         shot=sys_shot('v12_02_prompt_applied.png'))

    # ---------------------------------------------------------- V12-3 切换
    b = seeds[1]
    click_css('[data-prompt-open]')
    click_css(f"[data-prompt-item=\"{b['id']}\"]")
    s3 = snap()
    note('V12-3 切到第二条：整体替换、只留一个选中',
         s3['text'] == b['content'] and a['content'] not in s3['text']
         and s3['chip'] and s3['chip']['id'] == b['id'] and s3['ls'] == str(b['id']),
         text=s3['text'], chip=s3['chip'], ls=s3['ls'],
         old_text_gone=(a['content'] not in s3['text']))

    # ---------------------------------------------------------- V12-4 重启仍在
    old_pid = V.pid_of()
    killed = V.kill_pid(old_pid) if old_pid else False
    time.sleep(2)
    new_pid = V.launch()
    V.WS = None
    cdp_ok = V.connect_ws(90)
    V.wait_ready(60)
    wait_boot(40)
    reopened = chat_open()
    s4 = snap()
    note('V12-4 重启后选用还在（chip + 输入框回填）',
         killed and cdp_ok and reopened and s4['chip'] and s4['chip']['id'] == b['id']
         and s4['text'] == b['content'] and s4['ls'] == str(b['id']),
         old_pid=old_pid, new_pid=new_pid, killed=killed, cdp=cdp_ok, chat=reopened,
         chip=s4['chip'], text=s4['text'], ls=s4['ls'],
         shot=sys_shot('v12_03_after_restart.png'))

    # ---------------------------------------------------------- V12-5 不越界 + 发送链
    closed = js("""(() => {
      const b = Array.from(document.querySelectorAll('.chat-top .btn'))
        .find(e => (e.textContent || '').trim() === '收起');
      if (!b) return false;
      b.click();
      return true;
    })()""")
    time.sleep(1.0)
    V.hotkey(['ctrl', 'shift'], 'space')  # 收起态 → 展开 HUD 壳
    time.sleep(1.4)
    deck = json.loads(js("""JSON.stringify({
      deck: !!document.querySelector('.hud.is-open'),
      mode: __helmet.mode,
      panel: __helmet.panel,
    })"""))
    others = json.loads(js("""JSON.stringify({
      promptDomOutsideChat: document.querySelectorAll('.panel-col [data-prompt-open], .panel-col [data-prompt-item], .rail [data-prompt-open]').length,
      cabin: !!document.querySelector('.island-chat'),
      promptNodesInDeck: document.querySelectorAll('.hud.is-open [data-prompt-open]').length,
    })"""))
    reopened2 = chat_open()
    set_textarea('v12 回归：只验输入链，不发送')
    time.sleep(0.5)
    send_on = not snap()['sendDisabled']
    set_textarea('')
    time.sleep(0.5)
    send_off = snap()['sendDisabled']
    note('V12-5 不扩到待办/侧栏；发送按钮仍按输入启用',
         closed and deck['deck'] and others['promptDomOutsideChat'] == 0
         and others['promptNodesInDeck'] == 0 and not others['cabin']
         and reopened2 and send_on and send_off,
         closed=closed, deck=deck, probe=others, send_enabled=send_on,
         send_disabled_when_empty=send_off)

    # ---------------------------------------------------------- 清理
    cleanup([s['id'] for s in seeds])
    left = inv('list_snippets') or []
    note('V12-C 自测条目已清掉（库里不留痕）',
         not any(x['title'].startswith('【自测】') for x in left),
         remaining=len(left))

    out = {'ok': OK['v'], 'summary': {k: v['ok'] for k, v in R.items()},
           'items': R, 'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'pid': V.pid_of(), 'seeded': seeds,
           'build': 'npx tauri build --debug --no-bundle --config .smoke/tauri.smoke.json',
           'note': '提示词只读提示词百宝箱（snippets）；舱内只做选用/切换/取消，不增删改'}
    V.out('v12_result.json', out)
    print(json.dumps(out['summary'], ensure_ascii=False, indent=1), flush=True)
    print('OK' if OK['v'] else 'FAILED', flush=True)


if __name__ == '__main__':
    main()