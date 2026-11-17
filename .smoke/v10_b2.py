"""B2 专项：设置里的聊天模型 → 落盘 → 杀进程重启 → 仍在（随后还原）。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verify_v10 as V  # noqa: E402

OUT = os.path.join(HERE, 'v10_settings_restart.json')
R = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}


def open_settings(tag):
    V.wait_ready()
    for attempt in range(6):
        st = V.state()
        if st['panel'] == 'settings' and V.js("!!document.querySelector('.set-block select')"):
            print(tag, 'settings ready on attempt', attempt, flush=True)
            return True
        if st['mode'] != 'deck':
            V.js("document.querySelector('[data-nav=\\\"todos\\\"]').click()")
            time.sleep(1.2)
        V.js("document.querySelector('[data-nav=\\\"settings\\\"]').click()")
        for _ in range(20):
            time.sleep(0.3)
            if V.state()['panel'] == 'settings' and V.js("!!document.querySelector('.set-block select')"):
                print(tag, 'settings ready (inner) attempt', attempt, flush=True)
                return True
        print(tag, 'retry; state=', json.dumps(V.state(), ensure_ascii=False)[:220], flush=True)
    return False


def set_model(val):
    return V.js("""(() => {
      const s = document.querySelector('.set-block select');
      if (!s) return 'no-select';
      const d = Object.getOwnPropertyDescriptor(s.constructor.prototype, 'value');
      d.set.call(s, %s); s.dispatchEvent(new Event('change', {bubbles: true}));
      return s.value;
    })()""" % json.dumps(val))


def cfg_model():
    c = json.load(open(V.APP_JSON, encoding='utf-8'))
    return c.get('chat_selected_model')


pid = V.pid_of()
print('pid', pid, flush=True)
ok_open = open_settings('pre')
before = {'select': V.state()['model'], 'config': cfg_model()}
set_model('')
time.sleep(1.5)
after = {'select': V.state()['model'], 'config': cfg_model()}
print('write', json.dumps({'before': before, 'after': after}, ensure_ascii=False), flush=True)
V.out('v10_b2_write.json', {'ok_open': ok_open, 'before': before, 'after_set_empty': after})

# 重启
V.phase_restart()
time.sleep(2)
V.WS = None
V.wait_ready(90)
if V.state()['boot']:
    V.key_enter()
    time.sleep(2.5)
time.sleep(1.0)
ok_open2 = open_settings('post')
st = V.state()
after_restart = {'select': st['model'], 'config': cfg_model(), 'mode': st['mode'],
                 'panel': st['panel'], 'ok_open': ok_open2}
print('after_restart', json.dumps(after_restart, ensure_ascii=False), flush=True)
V.out('v10_b2_after_restart.json', after_restart)
V.shot('v10_settings_after_restart.png')

# 还原
set_model(before['select'] or '本地模拟')
time.sleep(1.2)
restored = {'select': V.state()['model'], 'config': cfg_model()}
print('restored', json.dumps(restored, ensure_ascii=False), flush=True)

R['B2_model_persisted'] = {
    'select_before': before['select'],
    'config_before': before['config'],
    'config_after_set_empty': after['config'],
    'select_after_restart': after_restart['select'],
    'config_after_restart': after_restart['config'],
    'ok': (after['config'] == '' and after_restart['select'] == ''
           and after_restart['config'] == ''),
    'restored': restored,
}
json.dump(R, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('B2 OK' if R['B2_model_persisted']['ok'] else 'B2 FAIL', flush=True)