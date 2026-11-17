"""A5 复测：用 WebView2 原生开关强制 prefers-reduced-motion: reduce，再看展开是否还播仪式。

（CDP 的 Emulation.setEmulatedMedia 在 WebView2 上返回成功但 matchMedia 不变，
  所以这里改用浏览器启动参数，确认 media 真的为 true 再判定。）
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import verify_v10 as V  # noqa: E402
import verify_expand_fx as X  # noqa: E402
import expand_fx_probe as P  # noqa: E402

EXE = os.path.join(ROOT, 'src-tauri', 'target', 'debug', 'x-hub.exe')
CFG = json.load(open(os.path.join(HERE, 'tauri.smoke.json'), encoding='utf-8'))
BASE = CFG['app']['windows'][0]['additionalBrowserArgs']


def kill():
    subprocess.run(['powershell', '-NoProfile', '-Command',
                    'Get-Process x-hub -ErrorAction SilentlyContinue | Stop-Process -Force'],
                   capture_output=True)


def launch(args):
    env = dict(os.environ)
    env['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = args
    log = open(os.path.join(HERE, 'run-a5.log'), 'w')
    p = subprocess.Popen([EXE], cwd=os.path.dirname(EXE), env=env, stdout=log,
                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         creationflags=0x00000008 | 0x00000200, close_fds=True)
    return p.pid


def main():
    kill()
    time.sleep(1.5)
    pid = launch(BASE + ' --force-prefers-reduced-motion')
    if not V.connect_ws(60):
        print(json.dumps({'ok': False, 'why': 'cdp'}, ensure_ascii=False))
        return 2
    V.wait_ready(45)
    time.sleep(2.0)
    media = V.js("matchMedia('(prefers-reduced-motion: reduce)').matches")
    V.js(X.REC)
    X.rec_reset()
    if not P.reveal_island():
        print(json.dumps({'ok': False, 'why': '唇边没唤出', 'media': media}, ensure_ascii=False))
        return 3
    px, py = X.click_toggle()
    V.click_at(px, py)
    time.sleep(1.0)
    rec = X.rec_read()
    ev = X.ceremony_events(rec)
    anim = json.loads(V.js("""(() => { const fx=document.querySelector('.fx');
      const g=getComputedStyle(fx.querySelector('.grain'));
      return JSON.stringify({mode: __helmet.mode, ceremony: fx.classList.contains('is-ceremony'),
        grainAnim: g.animationName, grainDur: g.animationDuration}); })()"""))
    out = {'ok': bool(media) and not ev, 'media_matched': media,
           'events': len(ev), 'anim': anim, 'pid': pid}
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())