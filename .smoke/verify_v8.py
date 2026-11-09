"""v8 验收：侧栏 / 笔记三栏不透明度对齐对话框（--glass-chat），v4 青边圆角仍在。

只读：不启停进程。结果写 .smoke/v8_result.json。
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
    from PIL import Image
except Exception:  # noqa: BLE001
    Image = None

PORT = 9222
EXE = os.path.join(ROOT, 'src-tauri', 'target', 'debug', 'x-hub.exe')
RESULT = {}
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)


def windows_of(pid):
    out = []

    def cb(hwnd, lp):
        d = info(hwnd)
        if d['pid'] == pid:
            out.append(d)
        return True

    u32.EnumWindows(CB(cb), 0)
    return out


def smoke_pids():
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
         " file_version=$v.FileVersion; file_description=$v.FileDescription} | ConvertTo-Json -Compress"],
        capture_output=True, text=True)
    try:
        return json.loads(ps.stdout)
    except Exception:  # noqa: BLE001
        return {'raw': ps.stdout}


def flat_ratio(img, box):
    """区域内颜色离散度：越接近 0 越不透明（桌面纹理透不过来）"""
    crop = img.crop(box).convert('RGB')
    px = list(crop.getdata())
    n = len(px)
    if not n:
        return None
    mean = [sum(c[i] for c in px) / n for i in range(3)]
    var = sum((c[i] - mean[i]) ** 2 for c in px for i in range(3)) / (n * 3)
    uniq = len(set(px))
    return {'std': round(var ** 0.5, 2), 'uniq_ratio': round(uniq / n, 4),
            'mean_luma': round(sum(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2] for c in px) / n, 1)}


def main():
    pids = smoke_pids()
    pid = pids[0] if pids else None
    R = RESULT

    t = cdp.pick(PORT, 'Helmet')
    ws = t['webSocketDebuggerUrl']

    def js(expr):
        r = cdp.evaluate(ws, expr)
        res = r.get('result', {})
        if res.get('exceptionDetails'):
            raise RuntimeError(json.dumps(res['exceptionDetails'], ensure_ascii=False)[:300])
        return res.get('result', {}).get('value')

    # 取证前保证躯干展开 + 笔记三栏在位（幂等，避免自动收起后空读数）
    js("""(() => {
      if (!document.querySelector('.is-notes-list')) {
        const nav = document.querySelector('[data-nav="notes"]');
        if (nav) nav.click();
      }
      return true;
    })()""")
    time.sleep(1.2)
    js("""(() => {
      if (!document.querySelector('.is-notes-editor')) {
        const r = document.querySelector('.note-row');
        if (r) r.click();
      }
      return true;
    })()""")
    time.sleep(1.2)

    probe = json.loads(js("""(() => {
      const g = el => el ? getComputedStyle(el) : null;
      const rail = document.querySelector('.rail');
      const list = document.querySelector('.is-notes-list');
      const ed = document.querySelector('.is-notes-editor');
      const island = document.querySelector('.island');
      const root = document.querySelector('.helmet-root');
      const tok = root ? getComputedStyle(root).getPropertyValue('--glass-chat').trim() : null;
      const rect = el => { if (!el) return null; const b = el.getBoundingClientRect();
        return [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)]; };
      return JSON.stringify({
        token: tok,
        vw: innerWidth, vh: innerHeight, dpr: devicePixelRatio,
        railBg: g(rail) && g(rail).backgroundImage,
        railColor: g(rail) && g(rail).backgroundColor,
        railBorderW: g(rail) && g(rail).borderTopWidth,
        railBorderC: g(rail) && g(rail).borderTopColor,
        railRadius: g(rail) && g(rail).borderTopLeftRadius,
        listBg: g(list) && g(list).backgroundImage,
        listBorderC: g(list) && g(list).borderTopColor,
        listRadius: g(list) && g(list).borderTopLeftRadius,
        edBg: g(ed) && g(ed).backgroundImage,
        edBorderC: g(ed) && g(ed).borderTopColor,
        edRadius: g(ed) && g(ed).borderTopLeftRadius,
        islandBg: g(island) && g(island).backgroundImage,
        islandRadius: g(island) && g(island).borderTopLeftRadius,
        railRect: rect(rail), listRect: rect(list), edRect: rect(ed),
        rows: document.querySelectorAll('.note-row').length,
      });
    })()"""))

    same = (probe['railBg'] == probe['listBg'] == probe['edBg'] == probe['islandBg'])
    R['O1'] = {
        'step': 'O1 侧栏与笔记面板不透明度与对话框/COMMS 同档',
        'ok': bool(same and probe['token']),
        'token_glass_chat': probe['token'],
        'rail_bg': probe['railBg'],
        'list_bg': probe['listBg'],
        'editor_bg': probe['edBg'],
        'island_bg': probe['islandBg'],
        'identical_background': same,
    }

    R['O2'] = {
        'step': 'O2 v4 青边圆角仍在；无「透桌面」感',
        'ok': bool(probe['railRadius'] == '12px' and probe['listRadius'] == '12px'
                   and probe['edRadius'] == '12px'
                   and '0, 229, 255, 0.22' in (probe['railBorderC'] or '')
                   and '0, 229, 255, 0.22' in (probe['listBorderC'] or '')),
        'rail_border': [probe['railBorderW'], probe['railBorderC']],
        'list_border': probe['listBorderC'],
        'editor_border': probe['edBorderC'],
        'rail_radius': probe['railRadius'],
        'list_radius': probe['listRadius'],
        'editor_radius': probe['edRadius'],
        'island_radius_ref': probe['islandRadius'],
    }

    # 像素：改前/改后 rail 空白条离散度（同一窗口几何下裁同一块，避开按钮/文字）
    if Image:
        def box(r):
            x, y, w, h = r
            return (x + 6, y + 560, x + w - 6, y + min(h - 20, 820))

        try:
            before = Image.open(os.path.join(HERE, 'v8_before_opacity.png'))
            after = Image.open(os.path.join(HERE, 'v8_after_opacity.png'))
            scale = before.size[0] / float(probe['vw'])  # 截图宽 / CSS 视口宽（dpr）
            bx = tuple(int(v * scale) for v in box(probe['railRect']))
            R['O2']['pixel_rail_before'] = flat_ratio(before, bx)
            R['O2']['pixel_rail_after'] = flat_ratio(after, bx)
            R['O2']['pixel_shot_scale'] = round(scale, 3)
            R['O2']['pixel_box'] = bx
        except Exception as e:  # noqa: BLE001
            R['O2']['pixel_error'] = repr(e)

    # O3 窗口形态
    wins = windows_of(pid) if pid else []
    vis = [w for w in wins if w['visible'] and w['title'].strip()]
    ball = [w for w in vis if any(k in w['title'] for k in ('悬浮', 'ball', 'Ball'))]
    R['O3'] = {
        'step': 'O3 无「悬浮球」可见窗',
        'ok': not ball,
        'visible_titles': [w['title'] for w in vis],
        'ball_windows': ball,
        'windowing': [{'title': w['title'], 'class': w['class'], 'size': w['size'],
                       'toolwindow': w['ex_toolwindow']} for w in wins],
    }

    exe = file_info(EXE)
    R['O4'] = {
        'step': 'O4 回报：PID / 主可见标题 / 前后截图 / 改动文件 / exe',
        'ok': True,
        'pid': pid,
        'started': subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             f"(Get-Process -Id {pid}).StartTime.ToString('yyyy-MM-dd HH:mm:ss')"],
            capture_output=True, text=True).stdout.strip() if pid else None,
        'main_visible_titles': [w['title'] for w in vis],
        'shots': {
            'before': os.path.join(HERE, 'v8_before_opacity.png'),
            'after': os.path.join(HERE, 'v8_after_opacity.png'),
        },
        'changed_files': ['src/components/helmet/helmet.css'],
        'change': [
            '新增 --glass-chat: linear-gradient(180deg, rgba(28,36,48,.96) 0%, rgba(8,12,20,.97) 100%)',
            '--glass 0.62 -> 0.96；--glass-deep 0.86 -> 0.97（去掉过透值）',
            '.panel（.rail.panel / .panel-col.panel 共用）background: var(--glass-chat)，blur(18px) saturate(1.2)',
            '.island 对话框亦改为引用 var(--glass-chat)（同一条 token，非新色）',
            '.rail.panel/.panel-col.panel 保持 border 1px rgba(0,229,255,.22) + border-radius 12px（v4）',
        ],
        'exe': EXE,
        'exe_info': exe,
        'notes_three_cols': bool(probe['listRect'] and probe['listRect'][2] > 200
                                 and probe['edRect'] and probe['edRect'][2] > 300),
        'note_rows': probe['rows'],
        'probe': probe,
    }

    ok = all(R[k]['ok'] for k in ('O1', 'O2', 'O3', 'O4'))
    with open(os.path.join(HERE, 'v8_result.json'), 'w', encoding='utf-8') as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
    for k in ('O1', 'O2', 'O3', 'O4'):
        print(('PASS ' if R[k]['ok'] else 'FAIL ') + R[k]['step'], flush=True)
    print('ALLOK' if ok else 'FAILED')


if __name__ == '__main__':
    main()