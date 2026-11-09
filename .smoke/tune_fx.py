"""在透明窗里试光效参数：CDP 注入候选 CSS → 真屏截图对比。
mix-blend-mode 在透明 WebView 上没有底可混 ⇒ 全屏光效肉眼看不见；
改用自带 alpha 的覆盖层（grain 白噪 + chroma 品红/青 + 屏幕内缘 edge glow）。"""
import json
import sys
import time

from PIL import ImageGrab

sys.path.insert(0, '.smoke')
import verify_v10 as V

V.wait_ready()
if V.state()['mode'] != 'deck':
    V.js("document.querySelector('.island-toggle').click()")
    time.sleep(2.0)


def grab(name):
    p = V.HERE + '\\' + name
    ImageGrab.grab(all_screens=True).save(p, 'PNG')
    return p


def inject(css):
    expr = """(() => {
      document.getElementById('fx-test-style')?.remove();
      document.querySelector('.edge-test')?.remove();
      const st = document.createElement('style');
      st.id = 'fx-test-style';
      st.textContent = %s;
      document.head.appendChild(st);
      const e = document.createElement('div');
      e.className = 'edge-test';
      document.querySelector('.fx').appendChild(e);
      return true;
    })()""" % json.dumps(css)
    return V.js(expr)


def peak(shot_name):
    info = V.js("""(() => {
      const fx = document.querySelector('.fx');
      fx.classList.add('is-ceremony');
      const g = fx.querySelector('.grain').getAnimations()[0];
      const c = fx.querySelector('.chroma').getAnimations()[0];
      const e = fx.querySelector('.edge-test');
      if (g) { g.pause(); g.currentTime = 60; }
      if (c) { c.pause(); c.currentTime = 60; }
      if (e) { e.getAnimations().forEach(a => { a.pause(); a.currentTime = 60; }); }
      return JSON.stringify({'grain': g && getComputedStyle(fx.querySelector('.grain')).opacity,
        'chroma': c && getComputedStyle(fx.querySelector('.chroma')).opacity});
    })()""")
    time.sleep(0.3)
    p = grab(shot_name)
    V.js("""(() => {
      const fx = document.querySelector('.fx');
      fx.querySelectorAll('.grain, .chroma, .edge-test').forEach(e => e.getAnimations().forEach(a => a.cancel()));
      fx.classList.remove('is-ceremony');
      return fx.className;
    })()""")
    time.sleep(0.3)
    return info, p


CSS_A = """
.fx .grain{mix-blend-mode:normal!important;opacity:0}
.fx .chroma{mix-blend-mode:normal!important;
  background:linear-gradient(90deg,rgba(255,46,151,.10),rgba(255,46,151,.02) 28%,transparent 45%,transparent 55%,rgba(0,229,255,.02) 72%,rgba(0,229,255,.10))!important}
@keyframes gF2{0%{opacity:0}40%{opacity:.045}100%{opacity:0}}
@keyframes cF2{0%{opacity:0}40%{opacity:.8}100%{opacity:0}}
.fx.is-ceremony .grain{animation:gF2 150ms ease both!important}
.fx.is-ceremony .chroma{animation:cF2 150ms ease both!important}
.edge-test{position:absolute;inset:0;pointer-events:none;opacity:0;
  box-shadow:inset 0 0 90px rgba(0,229,255,.12)}
.fx.is-ceremony .edge-test{animation:eF2 150ms ease both}
@keyframes eF2{0%{opacity:0}35%{opacity:1}100%{opacity:0}}
"""

CSS_B = """
.fx .grain{mix-blend-mode:normal!important;opacity:0}
.fx .chroma{mix-blend-mode:normal!important;
  background:linear-gradient(90deg,rgba(255,46,151,.18),rgba(255,46,151,.03) 30%,transparent 45%,transparent 55%,rgba(0,229,255,.03) 70%,rgba(0,229,255,.18))!important}
@keyframes gF2{0%{opacity:0}40%{opacity:.07}100%{opacity:0}}
@keyframes cF2{0%{opacity:0}40%{opacity:.85}100%{opacity:0}}
.fx.is-ceremony .grain{animation:gF2 150ms ease both!important}
.fx.is-ceremony .chroma{animation:cF2 150ms ease both!important}
.edge-test{position:absolute;inset:0;pointer-events:none;opacity:0;
  box-shadow:inset 0 0 120px rgba(0,229,255,.2)}
.fx.is-ceremony .edge-test{animation:eF2 150ms ease both}
@keyframes eF2{0%{opacity:0}35%{opacity:1}100%{opacity:0}}
"""

for tag, css in (('A', CSS_A), ('B', CSS_B)):
    inject(css)
    print(tag, peak('shot_fx_%s.png' % tag))