"""Helmet POC-1 六条验收（真窗口 + 真鼠标 + CDP 读 DOM）。

用法: python .smoke/verify_poc1.py
注意: 本进程必须声明 PerMonitorV2，否则 Win32 矩形被 DPI 虚拟化（2560 读成 1707）。
"""
import json, sys, time, ctypes
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

sys.path.insert(0, r'C:\Users\wcy\projects\XXXX\.smoke')
import cdp
from win_inspect import find_windows, info, hit, click, move, fg, u32

PORT = 9222
OUT = []


def js(expr):
    t = cdp.pick(PORT, 'Helmet')
    r = cdp.evaluate(t['webSocketDebuggerUrl'], expr)
    res = r.get('result', {})
    if res.get('exceptionDetails'):
        return 'EXC:' + json.dumps(res['exceptionDetails'], ensure_ascii=False)[:300]
    return res.get('result', {}).get('value')


def helmet():
    for h in find_windows('Helmet'):
        d = info(h)
        if d['class'] == 'Tauri Window':
            return d
    return None


STATE_JS = """(()=>{const root=document.querySelector('.helmet-root');
 const bar=document.querySelector('.invoke-bar');
 if(!root||!bar) return null;
 const b=bar.getBoundingClientRect();
 const hud=document.querySelector('.hud');
 return JSON.stringify({cls:root.className,
   anchored:root.classList.contains('anchored'),
   collapsed:root.classList.contains('collapsed'),
   bar:[Math.round(b.x),Math.round(b.y),Math.round(b.width),Math.round(b.height)],
   barOffset:[bar.offsetWidth,bar.offsetHeight],
   hud:getComputedStyle(hud).display,
   iw:innerWidth,ih:innerHeight,dpr:devicePixelRatio,
   ls:localStorage.getItem('rr.hud.collapsed'),
   dbg:(document.querySelector('.dbg')||{}).textContent||null,
   hits:(window.__hits||[]).slice(-10)})})()"""


def state():
    v = js(STATE_JS)
    if not (isinstance(v, str) and v.startswith('{')):
        return {'raw': v}
    d = json.loads(v)
    h = helmet()
    if h:
        W = h['rect'][2] - h['rect'][0]
        H = h['rect'][3] - h['rect'][1]
        s = (W / d['iw']) if d['iw'] else 1
        d['win'] = {'rect': h['rect'], 'size': [W, H], 'visible': h['visible'],
                    'ex_transparent': h['ex_transparent']}
        d['scale'] = round(s, 4)
        d['win_css'] = [round(W / s), round(H / s)]
    return d


def rec(tag, extra=None):
    d = state()
    row = {'step': tag, 'state': d}
    if extra:
        row.update(extra)
    OUT.append(row)
    print(json.dumps(row, ensure_ascii=False))
    return d


def screen_pt(dom_rect, st, fx=0.5, fy=0.5):
    L, T = st['win']['rect'][0], st['win']['rect'][1]
    s = st['scale']
    return (L + round((dom_rect[0] + dom_rect[2] * fx) * s),
            T + round((dom_rect[1] + dom_rect[3] * fy) * s))


def hit_at(x, y):
    h = hit(x, y)
    hl = helmet()
    return {'pt': [x, y], 'hwnd': h['hwnd'], 'class': h['class'], 'title': h['title'],
            'root': h['root'], 'root_title': h['root_title'], 'root_class': h['root_class'],
            'is_helmet': bool(hl and h['root'] == hl['hwnd'])}


def raise_helmet():
    """把 Helmet 顶到 topmost 队列最前（不激活），确保真鼠标点得到。"""
    h = int(helmet()['hwnd'], 16)
    SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 0x2, 0x1, 0x10
    u32.SetWindowPos.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.HWND,
                                 ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    u32.SetWindowPos(h, ctypes.wintypes.HWND(-1), 0, 0, 0, 0,
                     SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


CX, CY = 1280, 764   # 屏幕中央（工作区 2560x1528）

def wait_ready(timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        v = js("!!(document.querySelector('.helmet-root')&&document.querySelector('.invoke-bar'))")
        if v is True:
            return True
        time.sleep(0.5)
    return False


print('== 0. 清记忆 + 重新挂载（无 rr.hud.collapsed）==')
print(js("(()=>{localStorage.removeItem('rr.hud.collapsed');location.reload();return 'reload'})()"))
print('page ready:', wait_ready())
time.sleep(0.6)
print(js("""(()=>{window.__hits=[];document.addEventListener('pointerdown',e=>{
  const t=e.target.closest?e.target.closest('.hit'):null;
  window.__hits.push((t?t.className:'none')+'@'+Math.round(e.clientX)+','+Math.round(e.clientY));
},true);return 'probes on, ls='+localStorage.getItem('rr.hud.collapsed')})()"""))

print('== 1. helmet_show（无记忆 → 应默认收起）==')
print(js("window.__TAURI_INTERNALS__.invoke('helmet_show').then(()=>'shown')"))
time.sleep(2.5)
s1 = rec('1-shown')

print('== 2. 收起态中央点穿 ==')
raise_helmet()
move(CX, CY); time.sleep(0.7)
h2 = hit_at(CX, CY)
b2 = js('JSON.stringify(window.__hits||[])')
click(CX, CY); time.sleep(0.5)
a2 = js('JSON.stringify(window.__hits||[])')
rec('2-center-collapsed', {'hit': h2, 'hits_before': b2, 'hits_after': a2, 'fg': fg()})

print('== 3. 点唤起条展开 + 展开态中央点穿 ==')
bp = screen_pt(s1['bar'], s1)
print('bar center screen =', bp)
click(*bp); time.sleep(1.6)
s3 = rec('3-expanded', {'bar_screen_pt': bp})
raise_helmet()
move(CX, CY); time.sleep(0.8)
h3 = hit_at(CX, CY)
b3 = js('JSON.stringify(window.__hits||[])')
click(CX, CY); time.sleep(0.5)
a3 = js('JSON.stringify(window.__hits||[])')
rec('3b-center-expanded', {'hit': h3, 'hits_before': b3, 'hits_after': a3, 'fg': fg()})

print('== 4. 展开态边缘 .hit 可点（上檐）==')
top = json.loads(js("(()=>{const r=document.querySelector('.top').getBoundingClientRect();return JSON.stringify([r.x,r.y,r.width,r.height])})()"))
tp = screen_pt(top, s3)
print('top eave css =', top, 'screen =', tp)
move(*tp); time.sleep(0.9)
h4 = hit_at(*tp)
b4 = js('JSON.stringify(window.__hits||[])')
click(*tp); time.sleep(0.6)
a4 = js('JSON.stringify(window.__hits||[])')
rec('4-eave-click', {'pt': tp, 'hit': h4, 'hits_before': b4, 'hits_after': a4, 'fg': fg()})

print('== 5. 再收起（点条）==')
s5 = state()
bp5 = screen_pt(s5['bar'], s5)
print('bar center screen =', bp5)
click(*bp5); time.sleep(1.4)
s5b = rec('5-collapsed-again', {'bar_screen_pt': bp5})
raise_helmet()
print('collapsed win rect =', s5b['win']['rect'],
      ' / bar screen rect =', [s5b['win']['rect'][0], s5b['win']['rect'][1],
                               s5b['win']['rect'][0] + round(s5b['bar'][2] * s5b['scale']),
                               s5b['win']['rect'][1] + round(s5b['bar'][3] * s5b['scale'])])

print('== 6. 收起后只留唤起条 / 桌面可用 ==')
h6 = {'center': hit_at(CX, CY), 'p600': hit_at(600, 600),
      'p2100_1300': hit_at(2100, 1300), 'p1280_40': hit_at(1280, 40)}
b6 = js('JSON.stringify(window.__hits||[])')
click(600, 600); time.sleep(0.6)
a6 = js('JSON.stringify(window.__hits||[])')
rec('6-desktop', {'hit': h6, 'hits_before': b6, 'hits_after': a6, 'fg': fg()})

print('== 6b. 收起态下真实桌面程序可点（主窗 DOM 探针）==')
main_hwnd = info(0x431048)['rect'] if ctypes.windll.user32.IsWindow(0x431048) else None


def js_main(expr):
    cand = [t for t in cdp.targets(PORT) if t.get('type') == 'page' and t.get('url', '').rstrip('/') == 'http://localhost:1420']
    if not cand:
        return 'NO_MAIN_TARGET'
    t = cand[0]
    r = cdp.evaluate(t['webSocketDebuggerUrl'], expr)
    res = r.get('result', {})
    if res.get('exceptionDetails'):
        return 'EXC'
    return res.get('result', {}).get('value')


print('main window rect', main_hwnd)
print(js_main("""(()=>{window.__mainHits=[];document.addEventListener('pointerdown',e=>{
  window.__mainHits.push('pd@'+Math.round(e.clientX)+','+Math.round(e.clientY))},true);return 'main probe on'})()"""))
mx, my = (main_hwnd[0] + main_hwnd[2]) // 2, (main_hwnd[1] + main_hwnd[3]) // 2
print('click main window center', (mx, my), hit_at(mx, my))
click(mx, my)
time.sleep(0.7)
print('main window hits:', js_main('JSON.stringify(window.__mainHits||[])'))
print('fg after main click', fg())
print('helmet hits after:', js('JSON.stringify(window.__hits||[])'))

print('== 7. 截图 ==')
try:
    from PIL import ImageGrab
    im = ImageGrab.grab()
    im.save(r'C:\Users\wcy\projects\XXXX\.smoke\poc1_collapsed.png')
    print('saved .smoke\\poc1_collapsed.png', im.size)
except Exception as e:
    print('screenshot failed', e)

with open(r'C:\Users\wcy\projects\XXXX\.smoke\poc1_result.json', 'w', encoding='utf-8') as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1)
print('WROTE .smoke\\poc1_result.json')