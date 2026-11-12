# -*- coding: utf-8 -*-
"""Float dark-align HUD: open todo/prompt floats, assert data-theme=dark, side-by-side shot."""
import json, os, sys, time
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import verify_v10 as V
import expand_fx_probe as P
import cdp

OUT = Path(HERE) / 'float_dark'
OUT.mkdir(exist_ok=True)
R = {}

TODO_NEEDLE = '\u5f85\u529e'       # 待办
PROMPT_NEEDLE = '\u63d0\u793a\u8bcd'  # 提示词


def js(e):
    return V.js(e)


def inv(cmd, args=None):
    return js('window.__TAURI_INTERNALS__.invoke(%s, %s)' % (json.dumps(cmd), json.dumps(args or {})))


def click_css(sel, settle=0.9):
    pid = V.pid_of()
    _h, win = V.helmet_hwnd(pid)
    rect = win['rect']
    sc = (rect[2] - rect[0]) / max(1, js('innerWidth'))
    pt = V.screen_pt(sel)
    if not pt:
        return {'ok': False, 'err': 'no such element: ' + sel}
    px, py = V.to_screen(pt, rect, sc)
    if py < 0 or px < 0:
        return {'ok': False, 'err': 'negative coords %s,%s' % (px, py), 'css': pt}
    V.move_to(px, py)
    time.sleep(0.35)
    V.click_at(px, py)
    time.sleep(settle)
    return {'ok': True, 'screen': [round(px), round(py)]}


def eval_target(needle, expr):
    t = cdp.pick(9222, needle)
    res = cdp.evaluate(t['webSocketDebuggerUrl'], expr)
    r = res.get('result', {})
    if r.get('exceptionDetails'):
        return {'error': r['exceptionDetails'], 'title': t.get('title')}
    return {'value': r.get('result', {}).get('value'), 'title': t.get('title'), 'url': t.get('url')}


def sys_grab(name, bbox=None):
    from PIL import ImageGrab
    p = str(OUT / name)
    ImageGrab.grab(bbox=bbox, all_screens=True).save(p)
    return p


def parse_theme(v):
    if not v or 'error' in v:
        return v
    val = v.get('value')
    try:
        parsed = json.loads(val) if isinstance(val, str) else val
    except Exception:
        parsed = val
    out = dict(v)
    out['parsed'] = parsed
    return out


def is_dark(block):
    parsed = (block or {}).get('parsed') or {}
    return parsed.get('theme') == 'dark'


def hud_state():
    return json.loads(js('JSON.stringify({mode:__helmet.mode,panel:__helmet.panel,geo:__helmet.geo,docked:__helmet.docked})'))


def ensure_hud_open():
    """If already expanded or geo=full/band and not docked, just click the toggle when idle.
    Only reveal from the lip when docked/lip. Never force a lip path on an already-open HUD."""
    st0 = hud_state()
    print('pre', st0)
    R['pre'] = st0
    if st0.get('docked') or st0.get('geo') == 'lip':
        if not P.reveal_island():
            raise RuntimeError('lip reveal failed: ' + str(js('__helmet.geo')))
        time.sleep(0.4)
    if js('__helmet.mode') == 'idle':
        c = click_css('.island-toggle', 1.2)
        R['click_toggle'] = c
        if js('__helmet.mode') == 'idle':
            js("var el=document.querySelector('.island-toggle'); if(el) el.click()")
            time.sleep(1.0)
    st1 = hud_state()
    print('opened', st1)
    R['opened'] = st1
    return st1


def main():
    if not V.connect_ws(30):
        raise SystemExit('CDP not ready')
    V.wait_ready(30)
    pid = V.pid_of()
    print('pid', pid)

    cfg_before = js('window.__TAURI_INTERNALS__.invoke("get_ui_config")')
    try:
        theme_before = json.loads(cfg_before) if isinstance(cfg_before, str) else cfg_before
    except Exception:
        theme_before = cfg_before
    theme_mode_before = theme_before.get('theme_mode') if isinstance(theme_before, dict) else theme_before
    print('theme_mode before', theme_mode_before)

    ensure_hud_open()

    nav = click_css('[data-nav="todos"]', 1.0)
    R['click_nav_todos'] = nav
    if not nav.get('ok'):
        js("var el=document.querySelector('[data-nav=todos]'); if(el) el.click()")
        time.sleep(1.0)
    print('state after todos', hud_state())

    c1 = click_css('.todo-float', 1.2)
    R['click_todo_float'] = c1
    if not c1.get('ok'):
        print('click todo failed, invoke fallback', c1)
        inv('toggle_todo_float')
        time.sleep(1.2)
        R['todo_invoke_fallback'] = True

    js("var el=document.querySelector('.island'); if(el) el.click()")
    time.sleep(0.8)
    if js('__helmet.mode') != 'chat':
        c_island = click_css('.island', 0.8)
        R['click_island'] = c_island
    time.sleep(0.6)
    c_prompt_open = click_css('[data-prompt-open]', 0.8)
    R['click_prompt_open'] = c_prompt_open
    if not c_prompt_open.get('ok'):
        js("var el=document.querySelector('[data-prompt-open]'); if(el) el.click()")
        time.sleep(0.8)
    c2 = click_css('[data-prompt-float]', 1.2)
    R['click_prompt_float'] = c2
    if not c2.get('ok'):
        print('click prompt float failed, invoke fallback', c2)
        inv('toggle_prompt_float')
        time.sleep(1.2)
        R['prompt_invoke_fallback'] = True

    time.sleep(1.0)
    titles = [t.get('title') for t in cdp.list_targets(9222)]
    R['targets'] = titles
    print('targets', titles)

    theme_expr = (
        "JSON.stringify({theme: document.documentElement.dataset.theme || '',"
        "bg: getComputedStyle((document.querySelector('.tf-root')||document.querySelector('.pf-root')||document.body)).backgroundColor,"
        "color: getComputedStyle((document.querySelector('.tf-root')||document.querySelector('.pf-root')||document.body)).color,"
        "title: document.title})"
    )
    try:
        todo_theme = parse_theme(eval_target(TODO_NEEDLE, theme_expr))
    except Exception as e:
        todo_theme = {'error': str(e)}
    try:
        prompt_theme = parse_theme(eval_target(PROMPT_NEEDLE, theme_expr))
    except Exception as e:
        prompt_theme = {'error': str(e)}
    R['todo_theme'] = todo_theme
    R['prompt_theme'] = prompt_theme
    print('TODO', todo_theme)
    print('PROMPT', prompt_theme)

    cfg_after = js('window.__TAURI_INTERNALS__.invoke("get_ui_config")')
    try:
        after = json.loads(cfg_after) if isinstance(cfg_after, str) else cfg_after
    except Exception:
        after = cfg_after
    theme_mode_after = after.get('theme_mode') if isinstance(after, dict) else after
    R['theme_mode_before'] = theme_mode_before
    R['theme_mode_after'] = theme_mode_after
    print('theme_mode after', theme_mode_after)

    side = sys_grab('hud_and_floats_side_by_side.png')
    R['side_by_side'] = side

    pid = V.pid_of()
    wins = V.windows(pid)
    cleaned = []
    for w in (wins if isinstance(wins, list) else []):
        if isinstance(w, dict):
            cleaned.append({'title': w.get('title'), 'rect': w.get('rect')})
        else:
            cleaned.append(str(w))
    R['windows'] = cleaned
    print('windows', cleaned[:15])

    todo_ok = is_dark(todo_theme)
    prompt_ok = is_dark(prompt_theme)
    persist_ok = theme_mode_before == theme_mode_after
    R['ok'] = bool(todo_ok and prompt_ok and persist_ok)
    R['todo_dark'] = todo_ok
    R['prompt_dark'] = prompt_ok
    R['persist_unchanged'] = persist_ok

    outp = Path(HERE) / 'float_dark_result.json'
    outp.write_text(json.dumps(R, ensure_ascii=False, indent=2), encoding='utf-8')
    keys = ('ok', 'todo_dark', 'prompt_dark', 'persist_unchanged', 'side_by_side',
            'theme_mode_before', 'theme_mode_after')
    print('RESULT', json.dumps({k: R[k] for k in keys}, ensure_ascii=False))
    return 0 if R['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())