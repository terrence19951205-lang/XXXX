"""P0-3 笔记正文验收（真窗口路径）：真鼠标点「新建」→ 真键盘写标题/正文 → DB 读回。

约束：
- 只用 CDP 取几何与状态，不用 CDP 改表单值；
- 打字前必须确认前台窗口就是烟雾头盔窗，否则放弃打字（不向桌面撒键盘）；
- 判定以 list_notes 读回 content 非空且含标记为准。
"""
import ctypes
import ctypes.wintypes as w
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import verify_v08 as V  # noqa: E402  复用 st/screen_pt/js/ipc
from win_inspect import click, info, u32  # noqa: E402

TITLE = '头盔笔记-真键验收'
BODY1 = '这是真键盘写下的正文第一行。'
BODY2 = '第二行：验收用。'

OUT = []


def step(tag, ok, **kv):
    row = {'step': tag, 'ok': bool(ok)}
    row.update(kv)
    OUT.append(row)
    print(json.dumps(row, ensure_ascii=False))


# ---------------------------------------------------------------- real input
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x0002, 0x0004
VK_RETURN, SCAN_RETURN = 0x0D, 0x1C


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', w.WORD), ('wScan', w.WORD), ('dwFlags', w.DWORD),
                ('time', w.DWORD), ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', w.LONG), ('dy', w.LONG), ('mouseData', w.DWORD),
                ('dwFlags', w.DWORD), ('time', w.DWORD),
                ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]


class _I(ctypes.Union):
    # 必须同时容纳 MOUSEINPUT，否则 x64 下 sizeof(INPUT)=32≠40，SendInput 直接返回 0
    _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ('i',)
    _fields_ = [('type', w.DWORD), ('i', _I)]


u32.SendInput.argtypes = [w.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
u32.SendInput.restype = w.UINT
assert ctypes.sizeof(INPUT) == 40, f'INPUT 大小应为 40，实际 {ctypes.sizeof(INPUT)}'


def _send(*events):
    arr = (INPUT * len(events))()
    for i, (vk, scan, flags) in enumerate(events):
        arr[i].type = 1  # INPUT_KEYBOARD
        arr[i].ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=None)
    n = u32.SendInput(len(events), arr, ctypes.sizeof(INPUT))
    if n != len(events):
        raise RuntimeError(f'SendInput 只送达 {n}/{len(events)}，err={ctypes.get_last_error()}')
    return n


def type_text(text):
    for ch in text:
        _send((0, ord(ch), KEYEVENTF_UNICODE), (0, ord(ch), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
        time.sleep(0.012)


def press_enter():
    _send((VK_RETURN, SCAN_RETURN, 0), (VK_RETURN, SCAN_RETURN, KEYEVENTF_KEYUP))
    time.sleep(0.05)


def select_all():
    """Ctrl+A：真键盘全选，覆盖输入框里的默认标题"""
    VK_CTRL, SCAN_CTRL, VK_A, SCAN_A = 0x11, 0x1D, 0x41, 0x1E
    _send((VK_CTRL, SCAN_CTRL, 0), (VK_A, SCAN_A, 0),
          (VK_A, SCAN_A, KEYEVENTF_KEYUP), (VK_CTRL, SCAN_CTRL, KEYEVENTF_KEYUP))
    time.sleep(0.05)


def helmet_hwnd():
    hl = V.helmet_win()
    return int(hl['hwnd'], 16) if hl else 0


def ensure_foreground():
    """把烟雾头盔窗提到前台；失败则返回 False（调用方不得打字）"""
    hl = helmet_hwnd()
    if not hl:
        return False
    cur = u32.GetForegroundWindow()
    if cur == hl:
        return True
    u32.SetForegroundWindow(hl)
    time.sleep(0.4)
    cur = u32.GetForegroundWindow()
    # 允许 WebView 子窗为前台，但根窗必须是我们这顶头盔
    root = u32.GetAncestor(cur, 2) if cur else 0
    return root == hl


def rect_of(sel):
    return json.loads(V.js(
        f"(()=>{{const e=document.querySelector({json.dumps(sel)});"
        "if(!e) return 'null';const b=e.getBoundingClientRect();"
        "return JSON.stringify([b.x,b.y,b.width,b.height])})()") or 'null')


def active():
    return V.js("(()=>{const a=document.activeElement;"
                "return a?(a.tagName+'.'+(a.className||'')+'#'+(a.type||'')):null})()")


def main():
    V.js("window.__TAURI_INTERNALS__.invoke('helmet_show')")
    time.sleep(1.2)
    V.wait_ready()
    s = V.st()
    if s.get('mode') == 'idle':
        click(*V.screen_pt(s['evoke'], s))
        time.sleep(1.6)
        s = V.st()
    if s.get('mode') != 'deck':
        click(*V.screen_pt(s['evoke'], s))
        time.sleep(1.6)
        s = V.st()
    step('N0-躯干态', s.get('mode') == 'deck', mode=s.get('mode'))

    # 真点左轨「02 笔记」
    nav = rect_of(".nav-btn:nth-of-type(2)")
    if not nav:
        navs = json.loads(V.js("""(()=>{const b=[...document.querySelectorAll('.nav-btn')]
          .find(x=>x.textContent.includes('02'));if(!b)return 'null';
          const r=b.getBoundingClientRect();return JSON.stringify([r.x,r.y,r.width,r.height])})()"""))
        nav = navs
    click(*V.screen_pt(nav, V.st()))
    time.sleep(1.8)
    step('N1-笔记面板', V.js("document.querySelector('.helmet-root').dataset.panel") == 'notes',
         panel=V.js("document.querySelector('.helmet-root').dataset.panel"))

    # 真点「新建」
    btn = json.loads(V.js("""(()=>{const b=[...document.querySelectorAll('.work-hd .btn')]
      .find(x=>x.textContent.includes('新建'));if(!b)return 'null';
      const r=b.getBoundingClientRect();return JSON.stringify([r.x,r.y,r.width,r.height])})()""") or 'null')
    if not btn:
        step('N2-新建按钮', False, err='no 新建 button')
        return
    click(*V.screen_pt(btn, V.st()))
    time.sleep(1.8)
    ed = V.js("!!document.querySelector('.note-ed input.title')")
    step('N2-新建按钮', ed is True, editor=ed)

    # 真点标题输入框 → 真键盘
    tr = rect_of('.note-ed input.title')
    click(*V.screen_pt(tr, V.st()))
    time.sleep(0.4)
    fg_ok = ensure_foreground()
    act1 = active()
    if fg_ok:
        select_all()
        type_text(TITLE)
    time.sleep(0.8)
    step('N3-真键标题', fg_ok and TITLE in str(V.js("(document.querySelector('.note-ed input.title')||{}).value") or ''),
         fg=fg_ok, active=act1,
         dom=V.js("(document.querySelector('.note-ed input.title')||{}).value"))

    # 真点正文 → 真键盘两行
    br = rect_of('.note-ed textarea')
    click(*V.screen_pt(br, V.st()))
    time.sleep(0.4)
    fg_ok2 = ensure_foreground()
    act2 = active()
    if fg_ok2:
        type_text(BODY1)
        press_enter()
        type_text(BODY2)
    time.sleep(3.2)
    dom_body = V.js("(document.querySelector('.note-ed textarea')||{}).value") or ''
    status = V.js("(document.querySelector('.note-ed .saved')||{}).textContent")
    step('N4-真键正文', fg_ok2 and BODY1 in dom_body and BODY2 in dom_body,
         fg=fg_ok2, active=act2, dom=dom_body, status=status,
         shot=V.shot('note-real'))

    notes = V.ipc('list_notes')
    hit = [n for n in (notes or []) if n.get('title') == TITLE]
    # list_notes 只有元信息（content 恒为空串），正文必须 get_note 单条回读
    row = V.ipc('get_note', {'noteId': hit[0]['id']}) if hit else None
    body_db = (row or {}).get('content') or ''
    ok3 = bool(row) and BODY1 in body_db and BODY2 in body_db
    step('N5-落库正文非空', ok3, notes=len(notes or []),
         db=({'id': row['id'], 'title': row['title'], 'content': body_db,
              'updated_at': row['updated_at']} if row else None))

    # 再显式点一次「保存」，确认手动保存也不丢正文
    V.js("""(()=>{const b=[...document.querySelectorAll('.note-ed .btn')]
      .find(x=>x.textContent.includes('保存'));if(b) b.click();})()""")
    time.sleep(1.2)
    notes2 = V.ipc('list_notes')
    hit2 = [n for n in (notes2 or []) if n.get('title') == TITLE]
    row2 = V.ipc('get_note', {'noteId': hit2[0]['id']}) if hit2 else None
    body2 = (row2 or {}).get('content') or ''
    step('N6-手动保存不丢', bool(row2) and BODY1 in body2,
         db=({'id': row2['id'], 'content': body2[:60]} if row2 else None))

    json.dump(OUT, open(os.path.join(HERE, 'note_real_result.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    fails = [r['step'] for r in OUT if not r['ok']]
    print('\n== 汇总 ==', len(OUT) - len(fails), 'pass /', len(fails), 'fail', fails)


if __name__ == '__main__':
    main()