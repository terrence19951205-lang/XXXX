"""v11 视觉验收：全面落地方向稿 v1（岛 morph / 材质统一 / 第一人称 HUD / 展开全屏光效 / 笔记三栏）。

只连 9222 上的 Helmet 页；只操作自己的 debug 烟雾进程；不写业务数据
（笔记只在 UI 里打开/关闭，不新建、不保存）。

用法：python verify_v11.py visual
产物：.smoke/v11_visual.json + v11_01_island_compact.png / v11_02_island_chat.png /
      v11_03_notes_list.png / v11_04_notes_editor.png / v11_05_expand_ceremony.png
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verify_v10 as V  # noqa: E402  复用 CDP / 真鼠标 / 窗口枚举 / 截图
from PIL import ImageChops, ImageGrab, ImageStat  # noqa: E402

js = V.js
shot = V.shot
out = V.out
state = V.state


def scale_now():
    pid = V.pid_of()
    hwnd, win = V.helmet_hwnd(pid)
    return (win['rect'][2] - win['rect'][0]) / max(1, js('innerWidth')), win['rect']


def click_css(sel, frac=0.5, settle=0.9):
    """真鼠标点某个 CSS 元素中心（命中前用 elementFromPoint 校验落点）"""
    sc, rect = scale_now()
    pt = V.screen_pt(sel, frac)
    if not pt:
        return {'ok': False, 'err': 'no such element ' + sel}
    px, py = V.to_screen(pt, rect, sc)
    V.move_to(px, py)
    time.sleep(0.5)
    at = js("(() => { const e = document.elementFromPoint(%s, %s); return e ? (e.tagName + '.' + (e.className||'')) : null; })()"
            % (pt['x'], pt['y']))
    V.click_at(px, py)
    time.sleep(settle)
    return {'ok': True, 'css': pt, 'screen': [px, py], 'hit_before': at}


STYLE_JS = """(() => {
  const pick = (sel) => {
    const e = document.querySelector(sel);
    if (!e) return null;
    const s = getComputedStyle(e);
    const r = e.getBoundingClientRect();
    return {
      sel, bgImage: s.backgroundImage, color: s.backgroundColor,
      border: s.borderTopWidth + ' ' + s.borderTopStyle + ' ' + s.borderTopColor,
      radius: s.borderTopLeftRadius, blur: s.backdropFilter || s.webkitBackdropFilter,
      size: [Math.round(r.width), Math.round(r.height)],
      opacity: s.opacity, pointerEvents: s.pointerEvents,
    };
  };
  return JSON.stringify({
    island: pick('.island'),
    chat: pick('.island.is-chat .island-chat'),
    rail: pick('.rail'),
    list: pick('.panel-col.is-notes-list'),
    editor: pick('.panel-col.is-notes-editor'),
    eave: pick('.eave-bot'),
    fx: pick('.fx'),
    grain: pick('.fx .grain'),
    chroma: pick('.fx .chroma'),
    vig: pick('.fx .vig'),
    scan: pick('.fx .scan'),
  });
})()"""


def styles():
    return json.loads(js(STYLE_JS))


def state11():
    """v11：在 v10 state() 基础上补 __helmet.fx（仪式计数/规格）"""
    s = state()
    try:
        s['fx'] = json.loads(js('JSON.stringify(window.__helmet.fx || null)'))
    except Exception:  # noqa: BLE001
        s['fx'] = None
    return s


def screen_shot(name):
    """系统截屏（真屏）：HUD 是透明覆盖层，CDP 抓图没有桌面底，
    blend/alpha 与渲染结果不可比；验收图必须是真屏。"""
    p = os.path.join(HERE, name)
    ImageGrab.grab(all_screens=True).save(p, 'PNG')
    return p


def border_ok(b):
    """1px 青边在 150% DPI 下 used value 会取整成 0.6667px（1 物理像素），按范围判"""
    try:
        w, style, color = b.split(' ', 2)
        wv = float(w.replace('px', ''))
    except Exception:  # noqa: BLE001
        return False
    return style == 'solid' and 0.5 <= wv <= 1.3 and color == 'rgba(0, 229, 255, 0.22)'


def wait_idle_band(timeout=6):
    """确保岛完整显示（贴顶时把光标挪到顶部热区唤出；HUD/对话态先 Esc 收回）"""
    if state()['mode'] != 'idle':
        V.key_escape()
        time.sleep(1.6)
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = state()
        if st['mode'] == 'idle' and not st['docked']:
            return st
        if st['docked']:
            # 顶部热区：屏幕顶部居中
            sc, rect = scale_now()
            V.move_to(rect[0] + (rect[2] - rect[0]) / 2, rect[1] + 2)
            time.sleep(1.0)
        else:
            time.sleep(0.4)
    return state()


def install_fx_recorder():
    js("""(() => {
      const fx = document.querySelector('.fx');
      window.__fxrec = {events: [], frames: [], maxG: 0, maxC: 0, t0: performance.now()};
      if (window.__fxobs) window.__fxobs.disconnect();
      window.__fxobs = new MutationObserver(() => {
        const ev = {t: Math.round(performance.now() - window.__fxrec.t0), cls: fx.className};
        try {
          const g = fx.querySelector('.grain').getAnimations()[0];
          const c = fx.querySelector('.chroma').getAnimations()[0];
          ev.anims = [
            g ? {name: g.animationName, dur: (g.effect.getComputedTiming
                 ? g.effect.getComputedTiming().duration : g.effect.getTiming().duration)} : null,
            c ? {name: c.animationName, dur: (c.effect.getComputedTiming
                 ? c.effect.getComputedTiming().duration : c.effect.getTiming().duration)} : null,
          ];
        } catch (e) { ev.err = String(e); }
        window.__fxrec.events.push(ev);
      });
      window.__fxobs.observe(fx, {attributes: true, attributeFilter: ['class']});
      const t0 = performance.now();
      (function sample() {
        const w = window.__fxrec;
        const g = parseFloat(getComputedStyle(fx.querySelector('.grain')).opacity) || 0;
        const c = parseFloat(getComputedStyle(fx.querySelector('.chroma')).opacity) || 0;
        w.maxG = Math.max(w.maxG, g);
        w.maxC = Math.max(w.maxC, c);
        w.frames.push({t: Math.round(performance.now() - t0), g: g, c: c, fx: fx.className});
        if (performance.now() - t0 < 520) requestAnimationFrame(sample);
      })();
      return true;
    })()""")


def read_fx_recorder():
    return json.loads(js("""(() => {
      const w = window.__fxrec;
      return JSON.stringify({count: w.events.length, events: w.events, maxGrain: w.maxG,
        maxChroma: w.maxC,
        visibleFrames: w.frames.filter(f => f.g > 0 || f.c > 0).length,
        frames: w.frames.filter(f => f.g > 0 || f.c > 0).slice(0, 12), total: w.frames.length});
    })()"""))


def freeze_peak_shot(name):
    """同一条 CSS 动画暂停在 60ms（方向稿 ?state=ceremony 峰值定格同法），拍完即清。
    同时用真屏前后差量量出「全屏可见」：右侧无面板区只有光效能改像素。"""
    base_img = ImageGrab.grab(all_screens=True)
    info = js("""(() => {
      const fx = document.querySelector('.fx');
      fx.classList.add('is-ceremony');
      const g = fx.querySelector('.grain').getAnimations()[0];
      const c = fx.querySelector('.chroma').getAnimations()[0];
      // v13 起 .edge 已删除（源码的 .fx 家族只有 vig/scan/grain/chroma/corners）
      const edgeEl = fx.querySelector('.edge');
      const e = edgeEl ? edgeEl.getAnimations()[0] : null;
      if (g) { g.pause(); g.currentTime = 60; }
      if (c) { c.pause(); c.currentTime = 60; }
      if (e) { e.pause(); e.currentTime = 60; }
      return JSON.stringify({grain: !!g, chroma: !!c, edge: !!e,
        grainOpacity: getComputedStyle(fx.querySelector('.grain')).opacity,
        chromaOpacity: getComputedStyle(fx.querySelector('.chroma')).opacity,
        edgeOpacity: edgeEl ? getComputedStyle(edgeEl).opacity : '0'});
    })()""")
    time.sleep(0.3)
    peak_img = ImageGrab.grab(all_screens=True)
    p = screen_shot(name)
    full = ImageChops.difference(base_img.convert('RGB'), peak_img.convert('RGB'))
    fst = ImageStat.Stat(full)
    BOX_R = (1750, 200, 2500, 1400)
    rd = ImageChops.difference(base_img.convert('RGB').crop(BOX_R), peak_img.convert('RGB').crop(BOX_R))
    rst = ImageStat.Stat(rd)
    info = json.loads(info) if isinstance(info, str) else info
    info['pixel_delta'] = {
        'fullscreen_bbox': list(full.getbbox() or []),
        'fullscreen_mean_rgb': [round(x, 2) for x in fst.mean],
        'fullscreen_max': max(m[1] for m in full.getextrema()),
        'right_area_mean_rgb': [round(x, 2) for x in rst.mean],
        'right_area_max': max(m[1] for m in rd.getextrema()),
    }
    js("""(() => {
      const fx = document.querySelector('.fx');
      fx.querySelectorAll('.grain, .chroma, .edge').forEach(e => e.getAnimations().forEach(a => a.cancel()));
      fx.classList.remove('is-ceremony', 'is-ceremony-hold');
      return fx.className;
    })()""")
    return info, p


# ================================================================== PHASE visual
def phase_visual():
    V.wait_ready()
    pid = V.pid_of()
    hwnd, win = V.helmet_hwnd(pid)
    res = {'pid': pid, 'title': V.win_title(hwnd), 'items': {}}
    if state()['boot']:
        V.key_enter()
        time.sleep(2.6)

    # ---------- V1-a 岛收起态（≈ 01-island-compact） ----------
    st = wait_idle_band()
    if state()['docked']:
        V.key_enter()  # 兜底
        time.sleep(1.2)
    st = state()
    sk = styles()
    res['items']['V1_island_compact'] = {
        'state': {'mode': st['mode'], 'docked': st['docked'], 'geo': st['geo']},
        'island': sk['island'],
        'radius_22': sk['island']['radius'] == '22px',
        'width_ok': 240 <= sk['island']['size'][0] <= 300,
        'material_glass_chat': 'linear-gradient' in sk['island']['bgImage']
                               and 'rgba(28, 36, 48, 0.96)' in sk['island']['bgImage'],
        'blur_18': 'blur(18px)' in sk['island']['blur'],
        'shot': screen_shot('v11_01_island_compact.png'),
    }
    res['items']['V1_island_compact']['ok'] = (
        res['items']['V1_island_compact']['state']['mode'] == 'idle'
        and res['items']['V1_island_compact']['radius_22']
        and res['items']['V1_island_compact']['width_ok']
        and res['items']['V1_island_compact']['material_glass_chat']
        and res['items']['V1_island_compact']['blur_18'])

    # ▾ 只管 HUD 壳：先确认它现在不会开对话（真鼠标点，允许必要时重试）
    attempts = []
    st_togg = None
    for _ in range(3):
        st_before = state11()
        if st_before['docked']:
            sc0, rect0 = scale_now()
            V.move_to(rect0[0] + (rect0[2] - rect0[0]) / 2, rect0[1] + 2)
            time.sleep(1.2)
            continue
        c = click_css('.island-toggle', settle=1.5)
        st_togg = state11()
        attempts.append({'click': c, 'mode_before': st_before['mode'],
                         'docked_before': st_before['docked'],
                         'mode_after': st_togg['mode'], 'hit_before': c.get('hit_before')})
        if st_togg['mode'] == 'deck':
            break
        time.sleep(0.5)
    if st_togg is None:
        st_togg = state11()
    res['items']['V1_toggle_is_hud_only'] = {
        'mode_before': attempts[0]['mode_before'] if attempts else None,
        'mode_after': st_togg['mode'],
        'deck': st_togg['deck'], 'chat': st_togg['chat'],
        'ceremony_count': (st_togg.get('fx') or {}).get('ceremony'),
        'attempts': attempts,
        'ok': st_togg['mode'] == 'deck' and st_togg['deck'] and not st_togg['chat'],
    }

    # ---------- V4 展开全屏光效（收起态 → ▾ 展开） ----------
    # 先收到贴顶，再从唇边唤出点 ▾
    V.key_escape()
    time.sleep(1.9)
    st_lip = state()
    reveal = None
    sc, rect = scale_now()
    V.move_to(rect[0] + (rect[2] - rect[0]) / 2, rect[1] + 2)
    time.sleep(1.2)
    st_rev = state()
    hwnd_r, win_r = V.helmet_hwnd(pid)
    rect = win_r['rect']
    sc = (rect[2] - rect[0]) / max(1, js('innerWidth'))
    # 先把光标放到 ▾ 上，再装记录器，再点：520ms 采样窗必须盖住 150ms 闪光
    btn_pt = V.screen_pt('.island-toggle')
    bpx, bpy = V.to_screen(btn_pt, rect, sc)
    V.move_to(bpx, bpy)
    time.sleep(0.7)
    install_fx_recorder()
    fx_before = (state11().get('fx') or {}).get('ceremony') or 0
    V.click_at(bpx, bpy)
    time.sleep(0.05)
    time.sleep(0.75)
    rec = read_fx_recorder()
    st_after = state11()
    btn = {'screen': [bpx, bpy], 'css': btn_pt}
    on_event = [e for e in rec['events'] if 'is-ceremony' in e['cls']]
    off_event = [e for e in rec['events'] if 'is-ceremony' not in e['cls'] and e['t'] > (on_event[0]['t'] if on_event else 0)]
    dur = (off_event[0]['t'] - on_event[0]['t']) if (on_event and off_event) else None
    anim_ok = bool(on_event and on_event[0].get('anims') and
                   all(a and a.get('dur') == 150 for a in on_event[0]['anims'] if a))
    peak_info, peak_shot = freeze_peak_shot('v11_05_expand_ceremony.png')
    time.sleep(0.4)
    # 收起 → 快捷键展开也要有光效（同一路）
    V.key_escape()
    time.sleep(1.9)
    sc, rect = scale_now()
    V.move_to(rect[0] + (rect[2] - rect[0]) / 2, rect[1] + 2)
    time.sleep(1.0)
    install_fx_recorder()
    before_hk = (state11().get('fx') or {}).get('ceremony') or 0
    V.hotkey(['ctrl', 'shift'], 'space')
    time.sleep(0.8)
    rec_hk = read_fx_recorder()
    after_hk = (state11().get('fx') or {}).get('ceremony') or 0
    res['items']['V4_expand_fx'] = {
        'flow': 'HUD 收起(Esc→唇边) → 顶部唤出 → 点岛右侧 ▾ 展开',
        'state_before': {'mode': st_lip['mode'], 'docked': st_lip['docked']},
        'revealed': {'docked': st_rev['docked'], 'geo': st_rev['geo']},
        'click': btn,
        'state_after': {'mode': st_after['mode'], 'deck': st_after['deck']},
        'ceremony_counter': {'before': fx_before, 'after': (st_after.get('fx') or {}).get('ceremony')},
        'mutations': rec['events'],
        'class_on_ms': on_event[0]['t'] if on_event else None,
        'class_off_ms': off_event[0]['t'] if off_event else None,
        'flash_ms_measured': dur,
        'animations': on_event[0].get('anims') if on_event else None,
        'animation_150ms': anim_ok,
        'max_grain_opacity': rec['maxGrain'],
        'max_chroma_opacity': rec['maxChroma'],
        'visible_frames': rec['visibleFrames'],
        'visible_frames_sample': rec['frames'],
        'fx_pointer_events': peak_info and styles()['fx']['pointerEvents'],
        'peak_pixel_delta': peak_info.get('pixel_delta') if isinstance(peak_info, dict) else None,
        'peak_shot': peak_shot,
        'peak_shot_note': '同一条 CSS 动画暂停在 60ms 的峰值定格（对照 05-expand-ceremony.png）；非另造效果',
        'hotkey_expand': {
            'combo': 'Ctrl+Shift+Space（收起态→展开）',
            'counter_before': before_hk, 'counter_after': after_hk,
            'mutations': rec_hk['events'], 'max_grain_opacity': rec_hk['maxGrain'],
            'max_chroma_opacity': rec_hk['maxChroma'],
            'ok': after_hk > before_hk and any('is-ceremony' in e['cls'] for e in rec_hk['events']),
        },
    }
    it = res['items']['V4_expand_fx']
    it['ok'] = bool(on_event and anim_ok and dur and 130 <= dur <= 400
                    and rec['maxGrain'] > 0 and rec['maxChroma'] > 0
                    and it['state_after']['deck'] and it['hotkey_expand']['ok']
                    and it['fx_pointer_events'] == 'none')

    # ---------- V1-b 点岛 → 对话舱（≈ 02-island-chat） ----------
    click_css('.island-brand', settle=1.5)
    st_chat = state()
    skc = styles()
    res['items']['V1_island_chat'] = {
        'state': {'mode': st_chat['mode'], 'chat': st_chat['chat'], 'deck': st_chat['deck']},
        'island': skc['island'],
        'width_420': 400 <= skc['island']['size'][0] <= 440,
        'radius_26': skc['island']['radius'] == '26px',
        'cabin_present': skc['chat'] is not None,
        'shot': screen_shot('v11_02_island_chat.png'),
    }
    res['items']['V1_island_chat']['ok'] = (
        st_chat['mode'] == 'chat' and st_chat['chat']
        and res['items']['V1_island_chat']['width_420']
        and res['items']['V1_island_chat']['radius_26']
        and res['items']['V1_island_chat']['cabin_present'])

    # Esc 关对话
    V.key_escape()
    time.sleep(1.4)
    st_esc = state()
    res['items']['V1_esc_closes_chat'] = {
        'mode': st_esc['mode'], 'chat': st_esc['chat'], 'docked': st_esc['docked'],
        'ok': st_esc['mode'] == 'idle' and not st_esc['chat'],
    }

    # ---------- V2 材质统一 ----------
    V.key_escape()  # 唇边态
    time.sleep(1.3)
    sc, rect = scale_now()
    V.move_to(rect[0] + (rect[2] - rect[0]) / 2, rect[1] + 2)
    time.sleep(1.0)
    if state()['mode'] != 'deck':                    # 开 HUD
        click_css('.island-toggle', settle=1.7)
    # 笔记栏可能带着上一轮的开关态：点一次没开就再补一次
    for _ in range(3):
        if state()['notes']['list']:
            break
        click_css('[data-nav="notes"]', settle=1.5)
    # 03 要是「只有中栏列表」：上一轮遗留的右栏编辑先收掉
    if state()['notes']['editor']:
        click_css('.panel-col.is-notes-editor .icon-btn', settle=1.3)
    st_list = state()
    sk2 = styles()
    res['items']['V2_notes_list'] = {
        'state': {'mode': st_list['mode'], 'panel': st_list['panel'], 'notes': st_list['notes']},
        'list': sk2['list'], 'shot': screen_shot('v11_03_notes_list.png'),
    }
    # 点第一条笔记 → 右栏编辑
    row = js("(() => { const r = document.querySelector('.note-row'); return r ? r.textContent.slice(0,24) : null; })()")
    for _ in range(3):
        if state()['notes']['editor']:
            break
        if not row:
            break
        click_css('.note-row', settle=1.6)
    st_ed = state()
    sk3 = styles()
    res['items']['V2_notes_editor'] = {
        'row': row,
        'state': {'notes': st_ed['notes'], 'editor': sk3['editor'] is not None},
        'editor': sk3['editor'], 'shot': screen_shot('v11_04_notes_editor.png'),
    }
    sk4 = styles()
    mat = {}
    for k in ('rail', 'list', 'editor', 'eave'):
        s = sk4[k]
        mat[k] = s and {
            'glass_chat': 'linear-gradient' in s['bgImage'] and 'rgba(28, 36, 48, 0.96)' in s['bgImage'],
            'border': s['border'], 'radius': s['radius'], 'blur': s['blur'], 'size': s['size'],
        }
    res['items']['V2_material_unified'] = {
        'surfaces': mat,
        'island_compact': sk['island'],
        'island_chat': skc['island'],
        'expect': '--glass-chat 全表面；青边 1px rgba(0,229,255,0.22)；面板圆角 12px；blur(18px)',
    }
    ok_mat = all(v and v['glass_chat'] and border_ok(v['border'])
                 and v['radius'] == '12px' and 'blur(18px)' in v['blur'] for v in mat.values())
    it2 = res['items']['V2_material_unified']
    it2['ok'] = bool(ok_mat and res['items']['V2_notes_list']['state']['notes']['list']
                     and res['items']['V2_notes_editor']['state']['notes']['editor'])
    res['items']['V2_notes_list']['ok'] = bool(res['items']['V2_notes_list']['state']['notes']['list'])
    res['items']['V2_notes_editor']['ok'] = bool(res['items']['V2_notes_editor']['state']['notes']['editor'])

    # ---------- V3 第一人称 HUD：中央穿透 + 克制装饰 ----------
    backdrop = V.start_backdrop()
    if not backdrop:
        time.sleep(0.8)
        backdrop = V.start_backdrop()
    base_hits = V.backdrop_hits()
    probe = js("""(() => {
      const cw = innerWidth, ch = innerHeight;
      const cands = [[cw*0.55, ch*0.5], [cw*0.5, ch*0.55], [cw*0.6, ch*0.45]];
      for (const [x,y] of cands) {
        const el = document.elementFromPoint(x, y);
        const hit = el && el.closest && el.closest('.hit');
        if (!hit) return {x, y, tag: el ? el.tagName : null, cls: el ? (el.className||'') : ''};
      }
      return null;
    })()""")
    sc, rect = scale_now()
    px, py = V.to_screen(probe, rect, sc) if probe else (rect[0] + 500, rect[1] + 300)
    V.move_to(px, py)
    time.sleep(0.8)
    ign = state()['ignoring']
    wfp_before = V.hit_at(px, py)
    V.click_at(px, py)
    time.sleep(0.5)
    hits_after = V.backdrop_hits()
    V.close_backdrop()

    deco = json.loads(js("""(() => {
      const q = (s) => document.querySelector(s);
      const g = (s) => { const e = q(s); if (!e) return null; const c = getComputedStyle(e);
        return {opacity: c.opacity, bg: (c.backgroundImage||c.backgroundColor||'').slice(0,120)}; };
      return JSON.stringify({
        vig: g('.fx .vig'), scan: g('.fx .scan'),
        ascii: [...document.querySelectorAll('.ascii-bg')].map(e => ({cls: e.className,
          size: getComputedStyle(e).fontSize, opacity: getComputedStyle(e).opacity})),
        pet: !!q('[class*=pet], [class*=mascot], [class*=bento]'),
        fold: [...document.querySelectorAll('.fx .corners i')].filter(e => getComputedStyle(e).display !== 'none')
                .map(e => e.className),
      });
    })()"""))
    res['items']['V3_first_person_hud'] = {
        'probe': probe, 'ignoring_before_click': ign,
        'backdrop': backdrop,
        'window_from_point': wfp_before,
        'backdrop_hits_before': base_hits, 'backdrop_hits_after': hits_after,
        # 结构证据兜底：命中点不是 .hit、整窗 ignoring、且该点归属的窗口不是 Helmet
        'passthrough_ok': hits_after > base_hits or (
            ign is True and (wfp_before or {}).get('root_title') != 'Helmet'),
        'decor': deco,
        'no_pet_no_bento': not deco['pet'],
        'ascii_micro_only': all(float(a['opacity']) <= 0.35 and float(a['size'].replace('px', '')) <= 8
                                for a in deco['ascii']),
        'corner_ticks_right_only': all(c in ('tr', 'br') for c in deco['fold']),
        'ok': (hits_after > base_hits or (ign is True and (wfp_before or {}).get('root_title') != 'Helmet')) and not deco['pet']
              and all(float(a['opacity']) <= 0.35 for a in deco['ascii'])
              and all(c in ('tr', 'br') for c in deco['fold']),
    }

    # 收尾：回 idle
    V.key_escape()
    time.sleep(1.6)
    res['final'] = {'state': state(), 'shot': screen_shot('v11_final_idle.png')}

    fx = res['items']['V4_expand_fx']
    res['expand_fx'] = {
        'trigger': 'HUD 已收起（Esc→唇边）→ 顶部唤出 → 点岛右侧 ▾；快捷键 Ctrl+Shift+Space 同路',
        'rule': 'Vue watch(deckOpen) 由 false→true 时 playExpandCeremony()（flush:post，避免被重渲染冲掉类名）',
        'css': '.fx.is-ceremony → grain(gFlash 150ms) + chroma(cFlash 150ms) + edge(eFlash 150ms)',
        'flash_ms': 150,
        'class_on_ms': fx['class_on_ms'],
        'class_off_ms': fx['class_off_ms'],
        'flash_ms_measured': fx['flash_ms_measured'],
        'animations': fx['animations'],
        'max_grain_opacity': fx['max_grain_opacity'],
        'max_chroma_opacity': fx['max_chroma_opacity'],
        'peak_pixel_delta': fx.get('peak_pixel_delta'),
        'counter_before_after': fx['ceremony_counter'],
        'hotkey_path': fx['hotkey_expand'],
        'pointer_events': fx['fx_pointer_events'],
        'screens': {'peak_still': fx['peak_shot'],
                    'burst_gif': os.path.join(HERE, 'v11_expand_ceremony.gif'),
                    'burst_frame': os.path.join(HERE, 'v11_05b_expand_flash_frame.png')},
        'note': ('grain/chroma/edge 走自带 alpha 的普通叠加：透明 WebView 里 '
                 'mix-blend-mode 没有"底"可混，实测肉眼看不见，故去掉 blend。'),
        'ok': fx['ok'],
    }

    items = res['items']
    res['ok'] = all(v.get('ok') for v in items.values())
    res['summary'] = {k: bool(v.get('ok')) for k, v in items.items()}
    out('v11_visual.json', res)
    print(json.dumps(res['summary'], ensure_ascii=False, indent=1))
    print('OK' if res['ok'] else 'FAIL', flush=True)


if __name__ == '__main__':
    phase = sys.argv[1] if len(sys.argv) > 1 else 'visual'
    globals()['phase_' + phase.replace('-', '_')]()