"""Helmet POC-1 acceptance run: drives the real window with real mouse input and
reads both Win32 state and in-page DOM state over CDP."""
import json, sys, time, ctypes
sys.path.insert(0, r'C:\Users\wcy\projects\XXXX\.smoke')
import cdp
from win_inspect import find_windows, info, hit, click, move, fg

PORT = 9222
HELMET_PID = int(sys.argv[1]) if len(sys.argv) > 1 else None


def helmet_hwnd():
    for h in find_windows('Helmet'):
        d = info(h)
        if d['class'] == 'Tauri Window' and (HELMET_PID is None or d['pid'] == HELMET_PID):
            return d
    return None


def js(expr):
    t = cdp.pick(PORT, 'Helmet')
    r = cdp.evaluate(t['webSocketDebuggerUrl'], expr)
    res = r.get('result', {})
    if res.get('exceptionDetails'):
        return 'EXC:' + json.dumps(res['exceptionDetails'], ensure_ascii=False)[:200]
    return res.get('result', {}).get('value')


def state():
    v = js("""(()=>{const r=document.querySelector('.helmet-root');
      const b=document.querySelector('.invoke-bar').getBoundingClientRect();
      return JSON.stringify({cls:r.className,ls:localStorage.getItem('rr.hud.collapsed'),
        hud:getComputedStyle(document.querySelector('.hud')).display,
        bar:[Math.round(b.x),Math.round(b.y),Math.round(b.width),Math.round(b.height)],
        dbg:(document.querySelector('.dbg')||{}).textContent})})()""")
    return json.loads(v) if isinstance(v, str) and v.startswith('{') else v


def rec(label, pt=None):
    d = helmet_hwnd()
    out = {'step': label, 'dom': state(),
           'helmet_visible': d['visible'], 'rect': d['rect'],
           'ex_transparent(passthrough)': d['ex_transparent'], 'fg': fg()}
    if pt:
        out['hit'] = hit(*pt)
    print(json.dumps(out, ensure_ascii=False))
    return out


print('== install probes ==')
print(js("""(()=>{window.__hits=[];document.querySelectorAll('.hit').forEach((el,i)=>{
   ['pointerdown','click'].forEach(t=>el.addEventListener(t,()=>window.__hits.push(t+':'+i+':'+el.className)));
 });return 'probes:'+document.querySelectorAll('.hit').length})()"""))

rec('S0 expanded-default')
print('--- S1 top eave ---')
move(853, 55); time.sleep(0.6); rec('S1a cursor on top .hit', (853, 55))
click(853, 55); time.sleep(0.3); print('hits-log', js('JSON.stringify(window.__hits)'))

print('--- S2 back to center ---')
move(853, 509); time.sleep(0.7); rec('S2 center after leaving .hit', (853, 509))

print('--- S3 left eave ---')
move(140, 500); time.sleep(0.7); rec('S3a cursor on left .hit', (140, 500))
click(140, 500); time.sleep(0.3); print('hits-log', js('JSON.stringify(window.__hits)'))

print('--- S3b bottom eave ---')
move(750, 960); time.sleep(0.7); rec('S3b cursor on bottom .hit', (750, 960))
click(750, 960); time.sleep(0.3); print('hits-log', js('JSON.stringify(window.__hits)'))

print('--- S4 click through at center ---')
move(853, 509); time.sleep(0.7)
before = js('JSON.stringify(window.__hits)')
click(853, 509); time.sleep(0.4)
after = js('JSON.stringify(window.__hits)')
print(json.dumps({'hits_before': before, 'hits_after': after, 'fg_after_center_click': fg()}, ensure_ascii=False))

print('--- S5 collapse via strip ---')
move(1615, 30); time.sleep(0.7); rec('S5a cursor on bar', (1615, 30))
click(1615, 30); time.sleep(0.6); rec('S5b after collapse click')

print('--- S6 collapsed center (desktop blocked?) ---')
move(853, 509); time.sleep(0.7); rec('S6 cursor at center while collapsed', (853, 509))
b = js('JSON.stringify(window.__hits)')
click(853, 509); time.sleep(0.4)
print(json.dumps({'hits_before': b, 'hits_after': js('JSON.stringify(window.__hits)'), 'fg': fg()}, ensure_ascii=False))

print('--- S7 re-expand and final state ---')
move(1615, 30); time.sleep(0.6); click(1615, 30); time.sleep(0.5)
rec('S7 after re-expand')
move(853, 509); time.sleep(0.7)
rec('S7b center', (853, 509))