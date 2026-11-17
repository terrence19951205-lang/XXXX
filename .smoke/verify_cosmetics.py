"""验收末次两处源码改动（运行时取证）：
1) debug 角标只在 ?dbg=1 出现，正常界面不留内部状态字样；
2) chat / idle 态全屏扫描层消失（deck 态仍在）。
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verify_v08 as V  # noqa: E402
from win_inspect import click  # noqa: E402

OUT = []


def step(tag, ok, **kv):
    row = {'step': tag, 'ok': bool(ok)}
    row.update(kv)
    OUT.append(row)
    print(json.dumps(row, ensure_ascii=False))


def js(e):
    return V.js(e)


def opacity(sel='.fx .scan'):
    return js(f"(()=>{{const e=document.querySelector({json.dumps(sel)});"
              "return e?getComputedStyle(e).opacity:null})()")


def n_dbg():
    return js("document.querySelectorAll('.dbg').length")


def main():
    js("window.__TAURI_INTERNALS__.invoke('helmet_show')")
    time.sleep(1.2)
    V.wait_ready()
    s = V.st()
    if s.get('mode') == 'idle':
        click(*V.screen_pt(s['evoke'], s))
        time.sleep(1.6)
        s = V.st()
    step('C1-躯干态扫描层仍在', s.get('mode') == 'deck' and float(opacity() or 0) > 0.1,
         mode=s.get('mode'), opacity=opacity(), dbg=n_dbg())
    step('C2-无dbg参数时无角标', n_dbg() == 0, dbg=n_dbg(),
         url=js('location.href'))

    # 点岛 → 对话态
    s = V.st()
    click(*V.screen_pt(s['island'], s))
    time.sleep(1.8)
    s2 = V.st()
    step('C3-对话态扫描层隐藏', s2.get('mode') == 'chat' and float(opacity() or 1) == 0,
         mode=s2.get('mode'), opacity=opacity())

    # Esc → 收起态
    js("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
    time.sleep(1.5)
    s3 = V.st()
    step('C4-收起态扫描层隐藏', s3.get('mode') == 'idle' and float(opacity() or 1) == 0,
         mode=s3.get('mode'), opacity=opacity())

    # 带 ?dbg=1 重载 → 角标出现
    js("(()=>{location.replace(location.pathname+'?dbg=1');return 'go'})()")
    time.sleep(3.5)
    V.wait_ready(timeout=25)
    time.sleep(1.5)
    step('C5-dbg=1时角标出现', n_dbg() == 1, dbg=n_dbg(), url=js('location.href'))

    # 回到无参数 → 角标消失
    js("(()=>{location.replace(location.pathname);return 'back'})()")
    time.sleep(3.5)
    V.wait_ready(timeout=25)
    time.sleep(1.5)
    step('C6-回退后角标消失', n_dbg() == 0, dbg=n_dbg(), url=js('location.href'))

    json.dump(OUT, open(os.path.join(HERE, 'cosmetics_result.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    fails = [r['step'] for r in OUT if not r['ok']]
    print('\n== 汇总 ==', len(OUT) - len(fails), 'pass /', len(fails), 'fail', fails)


if __name__ == '__main__':
    main()