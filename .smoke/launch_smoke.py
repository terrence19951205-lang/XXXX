"""Launch the smoke exe with browser args taken verbatim from .smoke/tauri.smoke.json.

Keeps WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS byte-identical to the config's
additionalBrowserArgs (constraint: same string in both places). Never touches
the official x-hub (PID 33108).
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cdp  # noqa: E402

EXE = os.path.join(ROOT, 'src-tauri', 'target', 'debug', 'x-hub.exe')
CFG = os.path.join(HERE, 'tauri.smoke.json')
PORT = 9222


def launch(log_name='run-v09.log'):
    cfg = json.load(open(CFG, encoding='utf-8'))
    args = cfg['app']['windows'][0]['additionalBrowserArgs']
    env = dict(os.environ)
    env['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = args
    p = subprocess.Popen([EXE], cwd=os.path.dirname(EXE), env=env,
                         stdout=open(os.path.join(HERE, log_name), 'w'),
                         stderr=subprocess.STDOUT)
    print('launched pid', p.pid)
    print('args|' + args + '|')
    for _ in range(90):
        time.sleep(1)
        try:
            ts = cdp.list_targets(PORT)
            names = [t.get('title') for t in ts]
            if any((n or '') in ('shell-hub', 'Helmet', 'x-hub Helmet') or 'helmet.html' in (n or '') for n in names):
                print('targets:', names)
                return p.pid, True
        except Exception:  # noqa: BLE001
            pass
    try:
        print('targets:', [t.get('title') for t in cdp.list_targets(PORT)])
    except Exception as e:  # noqa: BLE001
        print('cdp fail', e)
    return p.pid, False


if __name__ == '__main__':
    pid, ok = launch(sys.argv[1] if len(sys.argv) > 1 else 'run-v09.log')
    print('READY' if ok else 'NOT_READY', pid)