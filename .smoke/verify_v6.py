"""v6 验收：冒烟入口形态 = 仅 Helmet（无悬浮球、无原版主仪表盘可见）。

前置：verify_v5 的 B1–B5 已过；本轮只验入口形态。
只操作 src-tauri/target/debug/x-hub.exe（冒烟构建）对应 PID，不碰官方发行版进程。
结果写 .smoke/v6_result.json。
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

PORT = 9222
EXE = os.path.join(ROOT, 'src-tauri', 'target', 'debug', 'x-hub.exe')
RUN_LOG = os.path.join(HERE, 'run-v6.log')
RESULT = {}
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

VK_CONTROL, VK_SHIFT, VK_SPACE = 0x11, 0x10, 0x20
KEYEVENTF_KEYUP = 0x2


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
    out = []
    ps = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         "Get-CimInstance Win32_Process -Filter \"Name='x-hub.exe'\" | "
         "Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress"],
        capture_output=True, text=True)
    try:
        rows = json.loads(ps.stdout or '[]')
    except Exception:  # noqa: BLE001
        return out
    if isinstance(rows, dict):
        rows = [rows]
    for r in rows:
        p = (r.get('ExecutablePath') or '').replace('\\\\', '\\')
        if p and os.path.normcase(p) == os.path.normcase(EXE):
            out.append(int(r['ProcessId']))
    return out


def cdp_titles():
    try:
        return [t.get('title') or '' for t in cdp.list_targets(PORT)]
    except Exception as e:  # noqa: BLE001
        return ['ERR ' + str(e)]


def log_tail():
    try:
        with open(RUN_LOG, encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception:  # noqa: BLE001
        return ''


def hotkey_toggle():
    """按一次 Ctrl+Shift+Space（烟雾模式下应只唤起 Helmet）"""
    u32.keybd_event(VK_CONTROL, 0, 0, 0)
    u32.keybd_event(VK_SHIFT, 0, 0, 0)
    u32.keybd_event(VK_SPACE, 0, 0, 0)
    time.sleep(0.08)
    u32.keybd_event(VK_SPACE, 0, KEYEVENTF_KEYUP, 0)
    u32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
    u32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


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


def main():
    pids = smoke_pids()
    if len(pids) != 1:
        print('FAIL 烟雾进程不唯一:', pids)
        RESULT['F0'] = {'step': '烟雾进程唯一', 'ok': False, 'pids': pids}
        json.dump(RESULT, open(os.path.join(HERE, 'v6_result.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        return 1
    pid = pids[0]
    created = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         f"(Get-Process -Id {pid}).StartTime.ToString('yyyy-MM-dd HH:mm:ss')"],
        capture_output=True, text=True).stdout.strip()

    log = log_tail()
    before_titles = visible_titles(pid)
    before_cdp = cdp_titles()

    # ---------------- F1 可见窗枚举 ----------------
    ball = [t for t in before_titles if '悬浮球' in t]
    main_dash = [t for t in before_titles if t.strip() == 'shell-hub (helmet smoke)']
    helpers = []
    for d in windows_of(pid):
        if d['title'].strip() == 'x-hub-helmet-smoke-siw':
            helpers.append({
                'title': d['title'], 'class': d['class'], 'size': d['size'],
                'ex_layered': d['ex_layered'], 'ex_transparent': d['ex_transparent'],
                'note': 'WebView2 4×4 分层透明辅助窗（IME/宿主窗口宿主），非用户可见 UI，v5 起一直存在',
            })
    f1 = {
        'step': 'F1 枚举可见窗：无标题「悬浮球」；无原版主仪表盘可见',
        'ok': not ball and not main_dash,
        'visible_titles': before_titles,
        'user_visible_titles': [t for t in before_titles if not t.startswith('x-hub-helmet-smoke-siw')],
        'ball_windows': ball,
        'main_dashboard_visible': main_dash,
        'helper_windows': helpers,
        'all_windows': [{'title': d['title'], 'class': d['class'], 'visible': d['visible']}
                        for d in windows_of(pid) if d['title'].strip()],
    }
    RESULT['F1'] = f1
    print(('PASS ' if f1['ok'] else 'FAIL ') + f1['step'], flush=True)

    # ---------------- F2 可见主 UI = Helmet ----------------
    helmet_visible = [d for d in windows_of(pid)
                      if d['visible'] and d['title'].strip().lower() == 'helmet']
    f2 = {
        'step': 'F2 可见主 UI 为 Helmet / shell-hub (helmet smoke)；CDP 有 Helmet',
        'ok': bool(helmet_visible) and any('Helmet' in t for t in before_cdp),
        'helmet_win': helmet_visible[0] if helmet_visible else None,
        'visible_titles': before_titles,
        'cdp_targets': before_cdp,
        'cdp_helmet': [t for t in before_cdp if 'Helmet' in t],
    }
    RESULT['F2'] = f2
    print(('PASS ' if f2['ok'] else 'FAIL ') + f2['step'], flush=True)

    # ---------------- F3 托盘/热键后仍无悬浮球当主入口 ----------------
    hotkey_toggle()
    time.sleep(2.0)
    after_titles = visible_titles(pid)
    after_log = log_tail()
    tail = after_log[len(log):] if after_log.startswith(log) else after_log
    log_hit = '[smoke] 快捷键/托盘切换' in tail
    ball_after = [t for t in after_titles if '悬浮球' in t]
    main_after = [t for t in after_titles if t.strip() == 'shell-hub (helmet smoke)']
    helmet_after = [d for d in windows_of(pid)
                    if d['visible'] and d['title'].strip().lower() == 'helmet']
    f3 = {
        'step': 'F3 托盘/热键操作后仍不出现悬浮球当主入口',
        'ok': log_hit and not ball_after and not main_after and bool(helmet_after),
        'hotkey': 'Ctrl+Shift+Space',
        'log_line': [l for l in tail.splitlines() if '[smoke]' in l or '快捷键' in l],
        'visible_titles_after': after_titles,
        'ball_after': ball_after,
        'main_after': main_after,
        'helmet_still_visible': bool(helmet_after),
        'code_guards': [
            'floating_ball::init 烟雾下直接 return（不建 floating-ball 窗）',
            'floating_ball::sync_with_main 烟雾下空操作',
            'tray::show_window 烟雾下改调 helmet_window::show',
            'tray::toggle_window 烟雾下只唤起 Helmet（不切显隐/不碰主窗）',
            'tray::toggle_main_window 烟雾下只唤起 Helmet',
        ],
    }
    RESULT['F3'] = f3
    print(('PASS ' if f3['ok'] else 'FAIL ') + f3['step'], flush=True)

    # ---------------- F4 回报材料 ----------------
    icons = sorted(
        os.path.join('src-tauri', 'icons', n)
        for n in os.listdir(os.path.join(ROOT, 'src-tauri', 'icons'))
        if n.startswith('shell-hub'))
    updates_dir = os.path.join(ROOT, 'src-tauri', 'target', 'debug', 'data', 'updates')
    pending = []
    for root_dir, _dirs, files in os.walk(updates_dir):
        for n in files:
            pending.append(os.path.join(root_dir, n))
    cfg_path = os.path.join(ROOT, 'src-tauri', 'target', 'debug', 'data', 'app.json')
    auto_update = None
    try:
        cfg = json.load(open(cfg_path, encoding='utf-8'))
        auto_update = cfg.get('auto_update_enabled')
    except Exception:  # noqa: BLE001
        pass
    exe = file_info(EXE)
    log_all = log_tail()
    icon_check = None
    try:
        from PIL import Image, ImageChops
        ico_png = os.path.join(HERE, 'v6_exe_icon.png')
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
        icon_check = {
            'extracted': ps.stdout.strip(),
            'mean_abs_diff_vs_shell_hub_32': round(sum(sum(p) for p in diff) / (len(diff) * 4), 3),
        }
    except Exception as e:  # noqa: BLE001
        icon_check = {'error': str(e)}
    f4 = {
        'step': 'F4 是否还有悬浮球标题窗 / 烟雾 PID / 主可见标题 / 图标 / exe / updater 未冲掉',
        'ok': True,
        'ball_window_exists': any('悬浮球' in d['title'] for d in windows_of(pid)),
        'ball_created_log': '悬浮球窗口已创建' in log_all,
        'smoke_pid': pid,
        'started': created,
        'now': time.strftime('%Y-%m-%d %H:%M:%S'),
        'visible_titles': visible_titles(pid),
        'exe': EXE,
        'exe_info': exe,
        'icon_paths': icons,
        'exe_icon_check': icon_check,
        'manifest_common_controls6': 'Microsoft.Windows.Common-Controls' in open(EXE, 'rb').read().decode('latin-1'),
        'updater_disabled_log': '冒烟构建（identifier 后缀 -smoke）：跳过待应用更新，不替换 exe' in log_all,
        'pending_updates': pending,
        'auto_update_enabled': auto_update,
    }
    RESULT['F4'] = f4
    print('F4 INFO ' + json.dumps(f4, ensure_ascii=False)[:1200], flush=True)

    with open(os.path.join(HERE, 'v6_result.json'), 'w', encoding='utf-8') as f:
        json.dump(RESULT, f, ensure_ascii=False, indent=1)
    allok = all(v.get('ok') for v in RESULT.values() if isinstance(v, dict))
    print('ALLOK' if allok else 'SOME_FAIL', flush=True)
    return 0 if allok else 2


if __name__ == '__main__':
    sys.exit(main())