"""速达面板的「功能」验收：不是看面板能不能打开，而是看能不能真的增删。

流程：进 deck → 打开速达 → 点「＋ 新增」→ 填名称/目标 → 添加 →
      列表里出现、后端 list_resources 里也在 → 删（两次确认）→ 列表与后端都没有。
清场：无论如何最后都把自测条目删掉。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_v10 as V  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = '【自测】速达功能'
TARGET = 'C:/Windows/System32/notepad.exe'


def click_sel(sel, settle=0.6):
    r = V.helmet_hwnd(V.pid_of())[1]['rect']
    pt = V.screen_pt(sel)
    if not pt:
        return False
    px, py = V.to_screen(pt, r)
    V.move_to(px, py)
    time.sleep(0.3)
    V.click_at(px, py)
    time.sleep(settle)
    return True


def set_input(sel, value):
    return V.js("""(() => {
      const e = document.querySelector(%s);
      if (!e) return false;
      e.value = %s;
      e.dispatchEvent(new Event('input', { bubbles: true }));
      return true;
    })()""" % (json.dumps(sel), json.dumps(value)))


def list_names():
    return json.loads(V.js(
        "JSON.stringify((window.__names = null) || [])"
    )) if False else None


def api_names():
    return json.loads(V.js("""(async () => {
      const r = await window.__TAURI_INTERNALS__.invoke('list_resources');
      return JSON.stringify(r.map(x => x.name));
    })()"""))


def main():
    if not V.connect_ws(30):
        print('no cdp')
        return 2
    V.wait_ready(30)
    out = {'steps': []}

    def step(name, ok, **kw):
        out['steps'].append({'name': name, 'ok': bool(ok), **kw})

    # 清场：先删掉可能残留的同名条目
    for _ in range(3):
        names = api_names() if 'list_resources' else []
        if NAME not in names:
            break
        V.js("""(async () => {
          const r = await window.__TAURI_INTERNALS__.invoke('list_resources');
          for (const x of r) if (x.name === %s)
            await window.__TAURI_INTERNALS__.invoke('delete_resource', { id: x.id });
        })()""" % json.dumps(NAME))
        time.sleep(0.4)

    # 1) 进 deck 的速达面板
    if V.js('__helmet.mode') != 'deck':
        click_sel('.island-toggle', 1.4)
    if V.js('__helmet.panel') != 'launch':
        click_sel('[data-nav="launch"]', 1.2)
    step('进入速达面板', V.js('__helmet.panel') == 'launch')

    # 2) 点「＋ 新增」
    opened = click_sel('.work-hd .btn', 0.5)
    has_form = V.js("!!document.querySelector('.res-form')")
    step('点「＋ 新增」出表单', opened and has_form, has_form=has_form)

    # 3) 填表
    set_input('.res-form input[placeholder="名称"]', NAME)
    set_input('.res-form > input.field', TARGET)
    ok_name = V.js("""(() => { const e = document.querySelector('.res-form input[placeholder="名称"]');
      return e && e.value === %s; })()""" % json.dumps(NAME))
    ok_target = V.js("""(() => { const e = document.querySelector('.res-form input[placeholder*="路径"], .res-form input[placeholder^="https"]');
      return e && e.value === %s; })()""" % json.dumps(TARGET))
    step('表单可填', ok_name and ok_target, name_filled=ok_name, target_filled=ok_target)

    # 4) 添加
    click_sel('.res-form .btn.primary', 1.0)
    names = api_names()
    step('后端已落库', NAME in names, count=len(names))
    in_list = V.js("document.body.innerText.includes(%s)" % json.dumps(NAME))
    step('列表里能看到', bool(in_list))

    # 5) 删除（两次确认）
    rect = V.helmet_hwnd(V.pid_of())[1]['rect']
    rowc = V.js("""(() => {
      const rows = [...document.querySelectorAll('.res-row')];
      const r = rows.find(x => x.innerText.includes(%s));
      if (!r) return null;
      const b = r.getBoundingClientRect();
      return JSON.stringify({x: b.left + b.width/2, y: b.top + b.height/2});
    })()""" % json.dumps(NAME))
    if rowc:
        pt = json.loads(rowc)
        px, py = V.to_screen(pt, rect)
        V.move_to(px, py)        # 先 hover，动作条 display:none → flex 才有可点面积
        time.sleep(0.5)
    row = V.js("""(() => {
      const rows = [...document.querySelectorAll('.res-row')];
      const r = rows.find(x => x.innerText.includes(%s));
      if (!r) return null;
      const b = r.querySelector('.mini.danger').getBoundingClientRect();
      if (!b.width) return null;
      return JSON.stringify({x: b.left + b.width/2, y: b.top + b.height/2});
    })()""" % json.dumps(NAME))
    if row:
        pt = json.loads(row)
        px, py = V.to_screen(pt, rect)
        V.click_at(px, py)       # 第一次：变「确认删」
        time.sleep(0.5)
        V.click_at(px, py)       # 第二次：真删
        time.sleep(0.8)
        names2 = api_names()
        step('两次确认后真删掉', NAME not in names2, remain=len(names2))
    else:
        step('两次确认后真删掉', False, why='kept row not found')

    out['ok'] = all(s['ok'] for s in out['steps'])
    json.dump(out, open(os.path.join(HERE, 'launch_func.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())