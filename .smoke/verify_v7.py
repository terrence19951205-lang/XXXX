"""v7 验收：三栏笔记可点（左→中列表→右编辑）+ 侧栏 P0 入口 + 入口形态不回退。

只操作 src-tauri/target/debug/x-hub.exe（冒烟构建）对应 PID，
不碰官方发行版进程，也绝不 taskkill /IM x-hub.exe。
结果写 .smoke/v7_result.json。
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import time

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import cdp  # noqa: E402
from win_inspect import info, u32  # noqa: E402

try:
    from websockets.sync.client import connect
except Exception:  # noqa: BLE001
    connect = None

PORT = 9222
EXE = os.path.join(ROOT, 'src-tauri', 'target', 'debug', 'x-hub.exe')
RESULT = {}
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)


# ---------------------------------------------------------------- 进程 / 窗口

def windows_of(pid):
    out = []

    def cb(hwnd, lp):
        d = info(hwnd)
        if d['pid'] == pid:
            out.append(d)
        return True

    u32.EnumWindows(CB(cb), 0)
    return out


def visible_titles(pid):
    return [d['title'] for d in windows_of(pid) if d['visible'] and d['title'].strip()]


def smoke_pids():
    """只认 target\\debug\\x-hub.exe 这一个路径的进程"""
    ps = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         "Get-CimInstance Win32_Process -Filter \"Name='x-hub.exe'\" | "
         "Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress"],
        capture_output=True, text=True)
    try:
        rows = json.loads(ps.stdout or '[]')
    except Exception:  # noqa: BLE001
        return []
    if isinstance(rows, dict):
        rows = [rows]
    return [int(r['ProcessId']) for r in rows
            if r.get('ExecutablePath') and
            os.path.normcase(r['ExecutablePath']) == os.path.normcase(EXE)]


def file_info(path):
    ps = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         f"$p='{path}'; $f=Get-Item $p; $v=[System.Diagnostics.FileVersionInfo]::GetVersionInfo($p);"
         " [pscustomobject]@{bytes=$f.Length; mtime=$f.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss');"
         " file_version=$v.FileVersion; product_version=$v.ProductVersion;"
         " file_description=$v.FileDescription; product_name=$v.ProductName} | ConvertTo-Json -Compress"],
        capture_output=True, text=True)
    try:
        return json.loads(ps.stdout)
    except Exception:  # noqa: BLE001
        return {'raw': ps.stdout, 'err': ps.stderr}


# ---------------------------------------------------------------- CDP

class Page:
    def __init__(self):
        self.t = cdp.pick(PORT, 'Helmet')
        self.ws = self.t['webSocketDebuggerUrl']
        self.mid = 0

    def _rpc(self, method, params=None, wait_ms=30000):
        self.mid += 1
        mid = self.mid
        with connect(self.ws, max_size=64 * 1024 * 1024,
                     open_timeout=15, close_timeout=5) as ws:
            ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
            while True:
                if json.loads(ws.recv()).get('id') == 1:
                    break
            ws.send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
            end = time.time() + wait_ms / 1000
            while time.time() < end:
                msg = json.loads(ws.recv())
                if msg.get('id') == mid:
                    return msg
        raise TimeoutError(method)

    def js(self, expr):
        r = self._rpc('Runtime.evaluate', {
            'expression': expr, 'awaitPromise': True, 'returnByValue': True,
            'allowUnsafeEvalBlockedByCSP': True, 'userGesture': True})
        res = r.get('result', {})
        if res.get('exceptionDetails'):
            raise RuntimeError(json.dumps(res['exceptionDetails'], ensure_ascii=False)[:400])
        return res.get('result', {}).get('value')

    def shot(self, name):
        r = self._rpc('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
        data = r.get('result', {}).get('data')
        if not data:
            return None
        import base64
        p = os.path.join(HERE, name)
        with open(p, 'wb') as f:
            f.write(base64.b64decode(data))
        return p


STATE_JS = """(() => {
  const h = window.__helmet || {};
  const list = document.querySelector('.is-notes-list');
  const ed = document.querySelector('.is-notes-editor');
  const row = document.querySelector('.note-row');
  const lr = list ? list.getBoundingClientRect() : null;
  const er = ed ? ed.getBoundingClientRect() : null;
  return JSON.stringify({
    mode: h.mode, geo: h.geo, docked: h.docked, notes: h.notes || null,
    listCol: !!(list && lr && lr.width > 1), editorCol: !!(ed && er && er.width > 1),
    listRect: lr ? [Math.round(lr.width), Math.round(lr.height)] : null,
    editorRect: er ? [Math.round(er.width), Math.round(er.height)] : null,
    rows: document.querySelectorAll('.note-row').length,
    firstRow: row ? row.querySelector('.t').textContent.trim() : null,
    editorTitle: (document.querySelector('.is-notes-editor input.title') || {}).value ?? null,
    editorBodyLen: ((document.querySelector('.is-notes-editor textarea') || {}).value || '').length,
    editorMeta: (document.querySelector('.is-notes-editor .meta-line') || {}).textContent ?? null,
    listTitle: (document.querySelector('.is-notes-list .work-hd .title') || {}).textContent ?? null,
    navs: [...document.querySelectorAll('[data-nav]')].map(e => ({k: e.dataset.nav, t: e.title})),
  });
})()"""


def state(p):
    return json.loads(p.js(STATE_JS))


def click(p, sel):
    ok = p.js(f"(() => {{ const e=document.querySelector({json.dumps(sel)}); if(!e) return false; e.click(); return true; }})()")
    time.sleep(0.9)
    return ok


def main():
    pids = smoke_pids()
    if len(pids) != 1:
        print('FAIL 冒烟进程不唯一:', pids, flush=True)
        RESULT['N0'] = {'step': '烟雾进程唯一', 'ok': False, 'pids': pids}
        with open(os.path.join(HERE, 'v7_result.json'), 'w', encoding='utf-8') as f:
            json.dump(RESULT, f, ensure_ascii=False, indent=1)
        return 1
    pid = pids[0]
    created = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         f"(Get-Process -Id {pid}).StartTime.ToString('yyyy-MM-dd HH:mm:ss')"],
        capture_output=True, text=True).stdout.strip()

    p = Page()
    s0 = state(p)
    RESULT['N0'] = {'step': 'CDP 连上 Helmet 页', 'ok': True, 'target': p.t['title'],
                    'url': p.t['url'], 'initial': s0}

    # ---------------- N2 侧栏 P0 入口 ----------------
    want = {'todos': '待办', 'notes': '笔记', 'chat': '聊天 / AI', 'clipboard': '剪贴板',
            'launch': '启动常用工具', 'search': '搜索', 'settings': '设置'}
    got = {n['k']: n['t'] for n in s0['navs']}
    missing = [f'{k}({v})' for k, v in want.items() if k not in got]
    n2 = {
        'step': 'N2 侧栏可见 P0 入口（待办/笔记/聊天/剪贴板/启动常用/搜索；设置可进）',
        'ok': not missing,
        'nav_expected': want,
        'nav_found': got,
        'missing': missing,
    }
    # 设置可进：点开设置面板，能读到「上下班 · 日衰口径」
    click(p, '[data-nav="settings"]')
    s_set = state(p)
    RESULT['N2_state'] = {'ok': True, 'step': 'N2 补记：设置入口点开后的 panel/mode',
                          'panel': s_set.get('panel'), 'mode': s_set.get('mode')}
    set_txt = p.js("""(() => {
      const ws = [...document.querySelectorAll('.panel-col .work')];
      const w = ws.find(x => { const t = x.querySelector('.work-hd .title'); return t && t.textContent.includes('设置'); });
      return w ? w.textContent.replace(/\\s+/g, ' ').trim().slice(0, 200) : null;
    })()""")
    n2['settings_opens'] = bool(set_txt and '设置' in set_txt)
    n2['settings_text'] = set_txt
    n2['ok'] = n2['ok'] and n2['settings_opens']
    RESULT['N2'] = n2
    print(('PASS ' if n2['ok'] else 'FAIL ') + n2['step'], flush=True)
    p.shot('v7_settings.png')

    # ---------------- N1 三栏：左 → 中列表 → 右编辑 ----------------
    n1 = {'step': 'N1 笔记三栏可点：左→中列表→右编辑；新建/切换可用'}

    # 1) 左栏点笔记 → 中栏列表
    click(p, '[data-nav="notes"]')
    s1 = state(p)
    n1['after_nav_notes'] = s1
    n1['list_opens'] = bool(s1['listCol'] and s1['rows'] > 0 and (s1['listRect'] or [0])[0] > 200)
    p.shot('v7_notes_list.png')

    # 2) 点中栏条目 → 右栏编辑
    first_title = s1['firstRow']
    click(p, '.note-row')
    s2 = state(p)
    n1['after_row_click'] = s2
    n1['editor_opens'] = bool(
        s2['editorCol'] and (s2['editorRect'] or [0])[0] > 300
        and s2['editorTitle'] is not None and s2['listCol'])
    n1['editor_shows_clicked_row'] = (s2['editorTitle'] == first_title)
    n1['three_cols_visible'] = bool(s2['listCol'] and s2['editorCol'])
    p.shot('v7_notes_editor.png')

    # 3) 新建
    rows_before = s2['rows']
    click(p, '.is-notes-list .hd-acts .btn.primary')
    s3 = state(p)
    n1['after_new'] = s3
    n1['new_works'] = bool(s3['rows'] == rows_before + 1 and s3['editorCol']
                           and (s3['editorTitle'] or '') == '未命名笔记')
    new_id = (s3.get('notes') or {}).get('active')

    # 4) 切换到另一条（不是新建那条）
    other = p.js("""(() => {
      const rows=[...document.querySelectorAll('.note-row')];
      const cur=document.querySelector('.is-notes-editor input.title').value;
      const t=rows.find(r=>r.querySelector('.t').textContent.trim()!==cur);
      if(!t) return null; t.click(); return t.querySelector('.t').textContent.trim();
    })()""")
    time.sleep(0.9)
    s4 = state(p)
    n1['after_switch'] = s4
    n1['switch_target'] = other
    n1['switch_works'] = bool(other and s4['editorTitle'] == other
                              and (s4.get('notes') or {}).get('active') != new_id)

    # 5) 分层收起：中栏 ✕ 收掉两层，再点笔记只开中栏
    click(p, '.is-notes-list .hd-acts .icon-btn')
    s5 = state(p)
    n1['after_close_list'] = {k: s5[k] for k in ('listCol', 'editorCol', 'notes', 'mode')}
    click(p, '[data-nav="notes"]')
    s6 = state(p)
    n1['after_reopen'] = {k: s6[k] for k in ('listCol', 'editorCol')}
    n1['layered_collapse_works'] = bool(
        (not s5['listCol'] and not s5['editorCol']) and s6['listCol'] and not s6['editorCol'])

    # 6) 删掉新建的空笔记（移入回收站），把库还原干净
    p.js("""(() => {
      const rows=[...document.querySelectorAll('.note-row')];
      const t=rows.find(r=>r.querySelector('.t').textContent.trim()==='未命名笔记');
      if(t) t.click(); return !!t;
    })()""")
    time.sleep(0.9)
    clicked_danger = click(p, '.is-notes-editor .bar .btn.danger')
    s7 = state(p)
    n1['delete_junk'] = {'clicked': bool(clicked_danger), 'rows': s7['rows'],
                         'editorCol': s7['editorCol']}
    # 顺手把这条验收用空笔记从回收站彻底清掉（只针对刚建的那一条 id，不动别人的回收站）
    if new_id:
        purged = p.js(f"""(() => {{
          try {{ window.__TAURI_INTERNALS__.invoke('purge_note', {{ id: {int(new_id)} }}); return true }}
          catch (e) {{ return String(e) }}
        }})()""")
        n1['delete_junk']['purged_id'] = new_id
        n1['delete_junk']['purge_result'] = purged

    # 7) 收尾：留三栏可见（列表 + 编辑）
    click(p, '.note-row')
    s8 = state(p)
    n1['final'] = {k: s8[k] for k in ('mode', 'geo', 'listCol', 'editorCol', 'rows', 'editorTitle')}
    p.shot('v7_final_visible.png')

    n1['ok'] = all(bool(n1.get(k)) for k in
                   ('list_opens', 'editor_opens', 'editor_shows_clicked_row',
                    'three_cols_visible', 'new_works', 'switch_works',
                    'layered_collapse_works'))
    RESULT['N1'] = n1
    print(('PASS ' if n1['ok'] else 'FAIL ') + n1['step'], flush=True)

    # ---------------- N3 入口形态不回退 ----------------
    time.sleep(1.0)
    titles = visible_titles(pid)
    ball = [t for t in titles if '悬浮球' in t]
    main_dash = [t for t in titles if t.strip() == 'shell-hub (helmet smoke)']
    helpers = [{'title': d['title'], 'class': d['class'], 'size': d['size'],
                'note': 'single-instance 事件目标窗（WS_EX_TOOLWINDOW|LAYERED|TRANSPARENT），非用户可见 UI'}
               for d in windows_of(pid) if d['title'].strip() == 'x-hub-helmet-smoke-siw']
    user_visible = [t for t in titles if not t.startswith('x-hub-helmet-smoke-siw')]
    n3 = {
        'step': 'N3 无「悬浮球」可见窗；无原版主仪表盘当主入口',
        'ok': not ball and not main_dash and bool(user_visible),
        'visible_titles': titles,
        'user_visible_titles': user_visible,
        'ball_windows': ball,
        'main_dashboard_visible': main_dash,
        'helper_windows': helpers,
        'all_windows': [{'title': d['title'], 'class': d['class'], 'visible': d['visible']}
                        for d in windows_of(pid) if d['title'].strip()],
    }
    RESULT['N3'] = n3
    print(('PASS ' if n3['ok'] else 'FAIL ') + n3['step'], flush=True)

    # ---------------- N4 回报材料 ----------------
    icons = sorted(os.path.join('src-tauri', 'icons', n)
                   for n in os.listdir(os.path.join(ROOT, 'src-tauri', 'icons'))
                   if n.startswith('shell-hub'))
    updates_dir = os.path.join(ROOT, 'src-tauri', 'target', 'debug', 'data', 'updates')
    pending = [os.path.join(r, n) for r, _d, fs in os.walk(updates_dir) for n in fs]
    auto_update = None
    try:
        cfg = json.load(open(os.path.join(ROOT, 'src-tauri', 'target', 'debug', 'data', 'app.json'),
                             encoding='utf-8'))
        auto_update = cfg.get('auto_update_enabled')
    except Exception:  # noqa: BLE001
        pass
    icon_check = None
    try:
        from PIL import Image, ImageChops
        ico_png = os.path.join(HERE, 'v7_exe_icon.png')
        ps = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "Add-Type -AssemblyName System.Drawing;"
             f" $i=[System.Drawing.Icon]::ExtractAssociatedIcon('{EXE}');"
             f" $b=$i.ToBitmap(); $b.Save('{ico_png}',[System.Drawing.Imaging.ImageFormat]::Png);"
             " Write-Output ($b.Width.ToString()+'x'+$b.Height.ToString())"],
            capture_output=True, text=True)
        a = Image.open(ico_png).convert('RGBA').resize((32, 32))
        b = Image.open(os.path.join(ROOT, 'src-tauri', 'icons', 'shell-hub-32.png')).convert('RGBA')
        diff = list(ImageChops.difference(a, b).getdata())
        icon_check = {'extracted': ps.stdout.strip(),
                      'mean_abs_diff_vs_shell_hub_32': round(sum(sum(p) for p in diff) / (len(diff) * 4), 3)}
    except Exception as e:  # noqa: BLE001
        icon_check = {'error': str(e)}

    log_path = os.path.join(ROOT, 'src-tauri', 'target', 'debug', 'data', 'logs', 'x-hub.log')
    log_all = ''
    try:
        log_all = open(log_path, encoding='utf-8', errors='replace').read()
    except Exception:  # noqa: BLE001
        pass
    exe_bytes = open(EXE, 'rb').read()
    n4 = {
        'step': 'N4 回报：PID / 主可见标题 / 有无悬浮球 / 笔记三栏是否可点 / 图标路径 / exe 大小 mtime',
        'ok': True,
        'smoke_pid': pid,
        'started': created,
        'now': time.strftime('%Y-%m-%d %H:%M:%S'),
        'main_visible_title': user_visible,
        'ball_window_exists': bool(ball),
        'notes_three_cols_clickable': RESULT['N1']['ok'],
        'icon_paths': icons,
        'exe': EXE,
        'exe_info': file_info(EXE),
        'exe_icon_check': icon_check,
        'manifest_common_controls6': b'Microsoft.Windows.Common-Controls' in exe_bytes,
        'updater_disabled_log': '冒烟构建（identifier 后缀 -smoke）：跳过待应用更新，不替换 exe' in log_all,
        'pending_updates': pending,
        'auto_update_enabled': auto_update,
        'shots': ['v7_settings.png', 'v7_notes_list.png', 'v7_notes_editor.png', 'v7_final_visible.png'],
    }
    RESULT['N4'] = n4
    print('N4 INFO ' + json.dumps({k: n4[k] for k in
                                   ('smoke_pid', 'main_visible_title', 'ball_window_exists',
                                    'notes_three_cols_clickable', 'exe_info')},
                                  ensure_ascii=False), flush=True)

    with open(os.path.join(HERE, 'v7_result.json'), 'w', encoding='utf-8') as f:
        json.dump(RESULT, f, ensure_ascii=False, indent=1)
    allok = all(v.get('ok') for v in RESULT.values() if isinstance(v, dict))
    print('ALLOK' if allok else 'SOME_FAIL', flush=True)
    return 0 if allok else 2


if __name__ == '__main__':
    sys.exit(main())