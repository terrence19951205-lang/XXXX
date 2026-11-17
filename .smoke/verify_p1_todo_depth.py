# -*- coding: utf-8 -*-
"""P1-2 + 五条界面修改验收：点岛 + CDP/真屏截图，不用热键。"""
import json, os, sys, time, ctypes, traceback
from pathlib import Path
from datetime import datetime, timedelta
from PIL import ImageGrab

HERE = Path(r"C:\Users\wcy\projects\XXXX\.smoke")
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import verify_v10 as V

OUT = HERE / "p1_todo_depth"
OUT.mkdir(exist_ok=True)
RESULT = HERE / "p1_todo_depth_result.json"
REPORT = HERE / "p1_todo_depth.md"
PREFIX = "【P1-2】"
R = {
    "ok": False,
    "items": {},
    "ui_changes": [],
    "build_count": 1,
    "bundle": False,
    "pushed": False,
    "official": {},
    "git": {},
    "shots": {},
    "ts": None,
}


def js(e, timeout=30):
    return V.js(e, timeout=timeout)


def inv(cmd, args=None):
    raw = js("window.__TAURI_INTERNALS__.invoke(%s, %s)" % (json.dumps(cmd), json.dumps(args or {})))
    if raw is None or raw == "":
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return raw


def hud():
    raw = js("""JSON.stringify({
      mode: __helmet.mode, geo: __helmet.geo, docked: __helmet.docked,
      panel: __helmet.panel, chat: __helmet.chat, deck: __helmet.deck,
      ignoring: __helmet.ignoring, pct: __helmet.pct,
      notes: __helmet.notes, viewport: __helmet.viewport
    })""")
    return json.loads(raw) if isinstance(raw, str) else (raw or {})


def fg():
    pid = V.pid_of()
    _h, win = V.helmet_hwnd(pid)
    if not _h:
        return None, None
    h = int(_h, 16) if isinstance(_h, str) and str(_h).startswith("0x") else int(_h)
    u32 = ctypes.windll.user32
    u32.ShowWindow(ctypes.c_void_p(h), 9)
    u32.SetForegroundWindow(ctypes.c_void_p(h))
    time.sleep(0.4)
    return _h, win


def official_procs():
    raw = __import__("subprocess").run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='x-hub.exe'\" | "
         "Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.strip()
    if not raw:
        return []
    data = json.loads(raw)
    if isinstance(data, dict):
        data = [data]
    return data


def shot(name):
    p = str(OUT / name)
    ImageGrab.grab(all_screens=True).save(p)
    R["shots"][name] = p
    return p


def reveal():
    st = hud()
    if st.get("docked") or st.get("geo") == "lip":
        pid = V.pid_of()
        _h, win = V.helmet_hwnd(pid)
        if win:
            V.move_to((win["rect"][0] + win["rect"][2]) / 2, win["rect"][1] + 2)
            time.sleep(1.1)
        st = hud()
    return st


def click_css(sel, settle=0.9, frac=0.5):
    st = reveal()
    if st.get("docked") or st.get("geo") == "lip":
        return {"ok": False, "err": "still lip, refuse click", "sel": sel}
    pid = V.pid_of()
    _h, win = V.helmet_hwnd(pid)
    pt = V.screen_pt(sel, frac)
    if not pt:
        return {"ok": False, "err": "no such element", "sel": sel}
    px, py = V.to_screen(pt, win["rect"])
    if py < 0 or px < 0:
        return {"ok": False, "err": "negative coords", "screen": [px, py], "sel": sel}
    V.move_to(px, py)
    time.sleep(0.2)
    V.click_at(px, py)
    time.sleep(settle)
    return {"ok": True, "screen": [round(px), round(py)], "sel": sel}


def click_text(sel, text, settle=0.9):
    """Click the first element matching sel whose innerText contains text."""
    idx = js("""(() => {
      const want = %s;
      const els = Array.from(document.querySelectorAll(%s));
      return els.findIndex(e => (e.innerText || '').trim().includes(want));
    })()""" % (json.dumps(text), json.dumps(sel)))
    if idx is None or int(idx) < 0:
        return {"ok": False, "err": "no text match", "sel": sel, "text": text}
    return click_css("%s:nth-of-type(%d)" % (sel, int(idx) + 1), settle=settle)


def set_value(sel, value):
    return js("""(() => {
      const el = document.querySelector(%s);
      if (!el) return false;
      el.focus();
      const proto = el.tagName === 'TEXTAREA'
        ? window.HTMLTextAreaElement.prototype
        : window.HTMLInputElement.prototype;
      const desc = Object.getOwnPropertyDescriptor(proto, 'value');
      if (desc && desc.set) desc.set.call(el, %s);
      else el.value = %s;
      el.dispatchEvent(new Event('input', {bubbles: true}));
      el.dispatchEvent(new Event('change', {bubbles: true}));
      return true;
    })()""" % (json.dumps(sel), json.dumps(value), json.dumps(value)))


def dismiss_modals():
    """关掉残留的待办编辑弹层，避免 modal-mask 吞掉后续点击。"""
    existed = js("!!document.querySelector('.modal-mask, .te-card, .te-close')")
    if not existed:
        return False
    js("""(() => {
      const close = document.querySelector('.te-close');
      if (close) { close.click(); return 'close'; }
      const btns = Array.from(document.querySelectorAll('.te-btn'));
      const cancel = btns.find(e => (e.innerText||'').trim() === '取消');
      if (cancel) { cancel.click(); return 'cancel'; }
      const mask = document.querySelector('.modal-mask');
      if (mask) { mask.click(); return 'mask'; }
      return null;
    })()""")
    time.sleep(0.5)
    return True


def note(name, ok, **extra):
    item = {"ok": bool(ok), **extra}
    R["items"][name] = item
    print(("PASS " if ok else "FAIL ") + name + " | " + json.dumps(item, ensure_ascii=False)[:500])
    return bool(ok)


def rail_info():
    raw = js("""JSON.stringify((() => {
      const navs = Array.from(document.querySelectorAll('.rail .nav-btn'));
      const panel = document.querySelector('.hud.is-open .panel-col');
      const rail = document.querySelector('.rail');
      const pr = panel ? panel.getBoundingClientRect() : null;
      const rr = rail ? rail.getBoundingClientRect() : null;
      const items = navs.map(b => {
        const lab = b.querySelector('.lab');
        const r = lab ? lab.getBoundingClientRect() : b.getBoundingClientRect();
        const text = (lab ? lab.innerText : b.innerText || '').trim();
        const overflowX = lab ? Math.max(0, lab.scrollWidth - lab.clientWidth - 1) : 0;
        const covered = !!(pr && r.right > pr.left + 1 && r.left < pr.right && r.bottom > pr.top && r.top < pr.bottom);
        const ico = (b.querySelector('.ico') || {}).textContent || null;
        return {
          nav: b.getAttribute('data-nav'),
          text, ico,
          overflowX,
          covered,
          visible: !!(lab && r.width > 2 && r.height > 2),
          rect: [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)]
        };
      });
      return {
        rail: rr ? [Math.round(rr.left), Math.round(rr.top), Math.round(rr.right), Math.round(rr.bottom), Math.round(rr.width)] : null,
        panel: pr ? [Math.round(pr.left), Math.round(pr.top), Math.round(pr.right), Math.round(pr.bottom)] : null,
        overlapRailPanel: !!(rr && pr && rr.right > pr.left + 1 && rr.left < pr.right),
        items
      };
    })())""")
    return json.loads(raw) if isinstance(raw, str) else raw


def island_layout():
    raw = js("""JSON.stringify((() => {
      const box = document.querySelector('.island');
      const parts = {
        brand: document.querySelector('.island-brand'),
        cue: document.querySelector('.island-brand .en'),
        pct: document.querySelector('.island-pct'),
        decay: document.querySelector('.island-decay'),
        toggle: document.querySelector('.island-toggle')
      };
      const rec = (e) => {
        if (!e) return null;
        const r = e.getBoundingClientRect();
        return {
          x: r.left, y: r.top, w: r.width, h: r.height,
          right: r.right, bottom: r.bottom,
          text: (e.innerText || '').replace(/\\s+/g, ' ').trim()
        };
      };
      const hit = {};
      for (const [k,e] of Object.entries(parts)) hit[k] = rec(e);
      const ib = rec(box);
      function overlap(a,b) {
        if (!a || !b) return false;
        return a.x < b.right - 1 && a.right - 1 > b.x && a.y < b.bottom - 1 && a.bottom - 1 > b.y;
      }
      function clipped(a) {
        if (!a || !ib) return true;
        return a.x < ib.x - 1 || a.right > ib.right + 1 || a.y < ib.y - 1 || a.bottom > ib.bottom + 1;
      }
      const overlaps = {
        pct_brand: overlap(hit.pct, hit.brand),
        pct_toggle: overlap(hit.pct, hit.toggle),
        brand_toggle: overlap(hit.brand, hit.toggle),
        decay_toggle: overlap(hit.decay, hit.toggle),
      };
      const clips = {pct: clipped(hit.pct), brand: clipped(hit.brand), toggle: clipped(hit.toggle), cue: clipped(hit.cue)};
      return {island: ib, parts: hit, overlaps, clips, chatOpen: !!document.querySelector('.island-chat')};
    })())""")
    return json.loads(raw) if isinstance(raw, str) else raw


def layout_coexist():
    raw = js("""JSON.stringify((() => {
      const pick = (sel) => {
        const e = document.querySelector(sel);
        if (!e) return null;
        const r = e.getBoundingClientRect();
        const s = getComputedStyle(e);
        return {
          sel, w: Math.round(r.width), h: Math.round(r.height),
          x: Math.round(r.left), y: Math.round(r.top), right: Math.round(r.right), bottom: Math.round(r.bottom),
          vis: s.visibility, disp: s.display, opacity: s.opacity
        };
      };
      const rail = pick('.rail');
      const panel = pick('.hud.is-open .panel-col');
      const cabin = pick('.island-chat');
      const collapse = pick('[data-collapse-chat]');
      const composer = pick('.composer textarea');
      const list = pick('.tv-scroll') || pick('.todo-mount') || pick('.notes-host') || pick('.panel-col .work');
      function overlap(a,b) {
        if (!a || !b) return false;
        return a.x < b.right - 1 && a.right - 1 > b.x && a.y < b.bottom - 1 && a.bottom - 1 > b.y;
      }
      return {
        rail, panel, cabin, collapse, composer, list,
        overlaps: {
          cabin_rail: overlap(cabin, rail),
          cabin_composer_panel: overlap(composer, panel),
          collapse_panel: overlap(collapse, panel),
          cabin_list: overlap(cabin, list),
        }
      };
    })())""")
    return json.loads(raw) if isinstance(raw, str) else raw


def center_ignore_point():
    raw = js("""JSON.stringify((() => {
      const dock = document.querySelector('.hud.is-open .dock');
      const island = document.querySelector('.island');
      const vw = innerWidth, vh = innerHeight;
      const dr = dock ? dock.getBoundingClientRect() : {right: 0, bottom: 0};
      const ir = island ? island.getBoundingClientRect() : {right: vw/2, bottom: 60, left: vw/2};
      let x = Math.min(vw - 80, Math.max(dr.right + 48, ir.right + 48, vw * 0.62));
      let y = Math.min(vh - 100, Math.max(ir.bottom + 48, vh * 0.55));
      // if still on a .hit, nudge right/down a bit
      for (let i = 0; i < 8; i++) {
        const el = document.elementFromPoint(x, y);
        const hit = el && el.closest && el.closest('.hit');
        if (!hit) break;
        x = Math.min(vw - 40, x + 60);
        y = Math.min(vh - 40, y + 40);
      }
      const el = document.elementFromPoint(x, y);
      return {x, y, on: el ? (el.tagName + '.' + (el.className||'')).slice(0,80) : null};
    })())""")
    return json.loads(raw) if isinstance(raw, str) else raw


def check_ignoring_at(css_pt, settle=0.5):
    pid = V.pid_of()
    _h, win = V.helmet_hwnd(pid)
    px, py = V.to_screen({"x": css_pt["x"], "y": css_pt["y"]}, win["rect"])
    V.move_to(px, py)
    time.sleep(settle)
    st = hud()
    return {
        "css": [css_pt["x"], css_pt["y"]],
        "screen": [round(px), round(py)],
        "ignoring": st.get("ignoring"),
        "on": css_pt.get("on"),
    }


def list_seed_todos():
    todos = inv("list_todos") or []
    if isinstance(todos, str):
        try:
            todos = json.loads(todos)
        except Exception:
            todos = []
    return [t for t in (todos or []) if str(t.get("title") or "").startswith(PREFIX)]


def cleanup_seeds():
    removed = []
    # delete children first, then parents
    seeds = list_seed_todos()
    kids = [t for t in seeds if t.get("parent_id") is not None]
    parents = [t for t in seeds if t.get("parent_id") is None]
    for t in kids + parents:
        try:
            inv("delete_todo", {"id": t["id"]})
            removed.append({"id": t["id"], "title": t.get("title")})
        except Exception as e:
            removed.append({"id": t.get("id"), "title": t.get("title"), "err": str(e)})
    return removed


def open_hud():
    reveal()
    st = hud()
    if st.get("deck"):
        return True
    c = click_css(".island-toggle", settle=1.3)
    st = hud()
    if st.get("deck"):
        return True
    js("document.querySelector('.island-toggle') && document.querySelector('.island-toggle').click()")
    time.sleep(1.0)
    return bool(hud().get("deck"))


def open_chat():
    reveal()
    st = hud()
    if st.get("chat") and js("!!document.querySelector('.island-chat')"):
        return True
    c = click_css(".island-brand", settle=1.2)
    if js("!!document.querySelector('.island-chat')"):
        return True
    js("document.querySelector('.island-brand') && document.querySelector('.island-brand').click()")
    time.sleep(1.0)
    return bool(js("!!document.querySelector('.island-chat')"))


def write_report():
    items = R["items"]
    def yn(k):
        it = items.get(k)
        if not it:
            return "未测"
        return "通过" if it.get("ok") else "未通过"

    lines = []
    lines.append("# shell-hub P1-2 待办厚度 + 界面修改验收")
    lines.append("")
    lines.append("时间（Asia/Shanghai）：%s" % R.get("ts"))
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    lines.append("- 总结果 `ok`：**%s**（见 `.smoke/p1_todo_depth_result.json`）" % ("通过" if R["ok"] else "未通过"))
    lines.append("- A 左轨功能名常显：%s" % yn("A_rail_names"))
    lines.append("- B 打开面板后左轨名称全文可见：%s" % yn("B_rail_visible_with_panel"))
    lines.append("- C 收起对话 ≠ 收起 HUD：%s" % yn("C_collapse_chat_keeps_hud"))
    lines.append("- D 收起对话后岛面不重叠，再点可开舱：%s" % yn("D_island_compact_no_overlap"))
    lines.append("- E 对话与功能并存、互不吞状态、中央可穿透：%s" % yn("E_coexist"))
    lines.append("- F 子待办 + 每日/每周周期（及日历）：%s" % yn("F_todo_depth"))
    lines.append("")
    lines.append("## 本轮 UI 修改")
    lines.append("")
    for x in R.get("ui_changes") or []:
        lines.append("- %s" % x)
    lines.append("")
    lines.append("## 截图")
    lines.append("")
    for name, path in (R.get("shots") or {}).items():
        lines.append("- `%s` → `%s`" % (name, path))
    lines.append("")
    lines.append("## 分项记录")
    lines.append("")
    for k, v in items.items():
        lines.append("### %s（%s）" % (k, "通过" if v.get("ok") else "未通过"))
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(v, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
    lines.append("## 编译与进程")
    lines.append("")
    lines.append("- 编译次数：%s（`npx tauri build --debug --no-bundle --config .smoke/tauri.smoke.json`，随后 rcedit `.smoke/app.manifest`）" % R.get("build_count"))
    lines.append("- 安装包：%s" % ("有" if R.get("bundle") else "未出"))
    lines.append("- push：%s" % ("有" if R.get("pushed") else "未 push"))
    lines.append("- 原版进程：%s" % json.dumps(R.get("official"), ensure_ascii=False))
    lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", REPORT)


def main():
    R["ts"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " Asia/Shanghai"
    R["ui_changes"] = [
        "左轨取消 01/02/03 等编号主识别，改为常显短功能名：聊天、待办、笔记、剪贴板、便签、倒计时、启动、搜索、设置；轨宽按名称让出，面板从轨右缘铺开。",
        "打开任一功能面板后，左轨名称仍全文可见，不再被卡片压成半截字（名称在轨内常显，不再靠悬停飞出标签）。",
        "对话舱顶部将「收起对话」做成独立控件（data-collapse-chat），不再与「新会话 / 对话」同等权重并列；点它只收舱。",
        "岛右侧 ▾ 仍只管 HUD 壳展收；收起对话后岛回到紧凑态，品牌区第二行改为「点击打开对话」作为会话提示，日衰% 与 ▾ 互不挤压。",
        "对话舱与左侧功能面板可同时开：打开待办/笔记等不再关舱，收舱也不关面板；点左轨「聊天」或点岛是展开/聚焦对话舱。两面同时开时岛/舱自动让到面板右侧，避免挡住输入区和左轨。",
        "待办厚度复用原版 TodoView：可建子待办并勾完（父项未完成时子项状态保留），可设每日/每周周期，完成一轮后到期再出现；侧旁日历可看出哪天有待办、点那天看当天列表。未做第二套仪表盘或布局编辑。",
        "顺手：紧凑岛加宽到 360px，关键元素 flex-shrink:0，避免截图/录屏/齿轮把日衰和 ▾ 挤叠；Esc 分层为先收对话、再收 HUD 壳、最后贴顶。",
    ]
    before = official_procs()
    R["official"]["before"] = before

    if not V.connect_ws(30):
        raise SystemExit("CDP connect failed")
    # wait helmet ready
    t0 = time.time()
    ready = False
    while time.time() - t0 < 30:
        try:
            if js("!!window.__helmet"):
                ready = True
                break
        except Exception:
            pass
        time.sleep(0.5)
    if not ready:
        raise SystemExit("__helmet not ready")
    fg()
    reveal()
    dismiss_modals()

    # ---------- A rail names ----------
    ok_hud = open_hud()
    info_a = rail_info()
    shot("A_rail_names.png")
    names = [i["text"] for i in (info_a or {}).get("items") or []]
    want = ["聊天", "待办", "笔记", "剪贴板", "便签", "倒计时", "启动", "搜索", "设置"]
    has_numbers = any((i.get("ico") or "").strip() in {"01", "02", "03", "04", "05", "06", "07"} or (i.get("text") or "").strip() in {"01", "02", "03"} for i in (info_a or {}).get("items") or [])
    a_ok = (
        ok_hud
        and all(n in names for n in want)
        and not has_numbers
        and all(i.get("visible") and i.get("overflowX", 0) <= 1 for i in (info_a or {}).get("items") or [])
    )
    note("A_rail_names", a_ok, opened=ok_hud, names=names, want=want, has_numbers=has_numbers, rail=info_a)

    # click 笔记 to prove names map to capabilities (also sets up B)
    c_notes = click_css('[data-nav="notes"]', settle=1.4)
    st_notes = hud()
    notes_open = st_notes.get("panel") == "notes" or bool(js("!!document.querySelector('.notes-host')"))
    shot("B_notes_panel_rail.png")
    info_b = rail_info()
    b_items = (info_b or {}).get("items") or []
    b_ok = (
        notes_open
        and all(i.get("visible") and i.get("overflowX", 0) <= 1 and not i.get("covered") for i in b_items)
        and not (info_b or {}).get("overlapRailPanel")
        and all((i.get("text") or "") == (i.get("text") or "").strip() and i.get("text") for i in b_items)
    )
    note("B_rail_visible_with_panel", b_ok, click=c_notes, state=st_notes, rail=info_b, notes_open=notes_open)

    # ---------- C collapse chat ----------
    dismiss_modals()
    ok_chat = open_chat()
    time.sleep(0.4)
    has_btn = bool(js("!!document.querySelector('[data-collapse-chat]')"))
    btn_text = js("(document.querySelector('[data-collapse-chat]')||{}).innerText || ''")
    # peer row should not contain a lone 「收起」 equal-weight button
    peer = js("""JSON.stringify(Array.from(document.querySelectorAll('.chat-top .btn')).map(e => (e.innerText||'').trim()))""")
    shot("C1_chat_collapse_control.png")
    st_before = hud()
    c_collapse = click_css("[data-collapse-chat]", settle=1.2)
    st_after = hud()
    chat_dom = bool(js("!!document.querySelector('.island-chat')"))
    rail_still = bool(js("!!document.querySelector('.hud.is-open .rail')"))
    panel_still = bool(js("!!document.querySelector('.hud.is-open .panel-col')"))
    c_only_cabin = (
        ok_chat and has_btn and "收起对话" in (btn_text or "")
        and not chat_dom and not st_after.get("chat")
        and st_after.get("deck") and rail_still and panel_still
        and st_after.get("panel") == st_before.get("panel")
    )
    # ▾ still collapses HUD
    c_toggle = click_css(".island-toggle", settle=1.3)
    st_hud_off = hud()
    hud_closed = not st_hud_off.get("deck") and not js("!!document.querySelector('.hud.is-open')")
    # reopen hud for later
    open_hud()
    click_css('[data-nav="notes"]', settle=1.0)
    c_ok = c_only_cabin and hud_closed
    note(
        "C_collapse_chat_keeps_hud",
        c_ok,
        opened=ok_chat, has_btn=has_btn, btn_text=btn_text, peer_row=peer,
        click_collapse=c_collapse, before=st_before, after=st_after,
        chat_dom=chat_dom, rail_still=rail_still, panel_still=panel_still,
        click_toggle=c_toggle, after_toggle=st_hud_off, hud_closed=hud_closed,
    )

    # ---------- D compact island ----------
    # chat should already be closed
    if js("!!document.querySelector('.island-chat')"):
        click_css("[data-collapse-chat]", settle=1.0)
    time.sleep(0.4)
    lay = island_layout()
    shot("D1_island_compact.png")
    no_overlap = lay and not any((lay.get("overlaps") or {}).values())
    no_clip = lay and not any((lay.get("clips") or {}).values())
    parts_ok = bool(lay and lay.get("parts", {}).get("pct") and lay["parts"]["pct"].get("text") and lay.get("parts", {}).get("toggle"))
    cue = (lay or {}).get("parts", {}).get("cue") or {}
    reopen = open_chat()
    shot("D2_reopen_chat.png")
    d_ok = no_overlap and no_clip and parts_ok and reopen
    note(
        "D_island_compact_no_overlap",
        d_ok,
        layout=lay, no_overlap=no_overlap, no_clip=no_clip,
        cue=cue, reopen=reopen,
    )

    # ---------- E coexist ----------
    # currently chat open; ensure a panel is open too
    if not hud().get("deck"):
        open_hud()
    c_todo = click_css('[data-nav="todos"]', settle=1.5)
    time.sleep(0.4)
    if not js("!!document.querySelector('.island-chat')"):
        open_chat()
        time.sleep(0.5)
    shot("E1_todo_and_chat.png")
    co1 = layout_coexist()
    st_e1 = hud()
    both1 = bool(st_e1.get("chat") and st_e1.get("deck") and st_e1.get("panel") == "todos"
                 and js("!!document.querySelector('.island-chat')")
                 and js("!!document.querySelector('.todo-mount, .todo-view')"))
    # type a message (do not depend on model success)
    typed = set_value(".composer textarea", "（验收探测，可忽略）")
    send_enabled = js("""(() => {
      const b = document.querySelector('.composer .btn.primary');
      return b ? !b.disabled : false;
    })()""")
    sent = False
    send_err_before = js("(document.querySelector('.chat-err')||{}).innerText || ''")
    if typed and send_enabled:
        click_css(".composer .btn.primary", settle=1.2)
        sent = True
    shot("E2_typed_or_sent.png")
    # open clipboard while chat stays
    c_clip = click_css('[data-nav="clipboard"]', settle=1.3)
    st_clip = hud()
    chat_stayed_clip = bool(st_clip.get("chat") and js("!!document.querySelector('.island-chat')"))
    shot("E3_chat_and_clipboard.png")
    c_launch = click_css('[data-nav="launch"]', settle=1.3)
    st_launch = hud()
    chat_stayed_launch = bool(st_launch.get("chat") and js("!!document.querySelector('.island-chat')"))
    shot("E4_chat_and_launch.png")
    c_search = click_css('[data-nav="search"]', settle=1.0)
    search_focus = js("document.activeElement && document.activeElement.matches('.quick-search input')")
    st_search = hud()
    chat_stayed_search = bool(st_search.get("chat") and js("!!document.querySelector('.island-chat')"))
    # collapse chat, panel remains
    click_css("[data-collapse-chat]", settle=1.1)
    st_c2 = hud()
    panel_after_collapse = bool(st_c2.get("deck") and not st_c2.get("chat"))
    # reopen chat, close HUD, chat remains
    open_chat()
    click_css(".island-toggle", settle=1.2)
    st_c3 = hud()
    chat_after_hud_close = bool(st_c3.get("chat") and not st_c3.get("deck") and js("!!document.querySelector('.island-chat')"))
    # both open again for passthrough
    open_hud()
    click_css('[data-nav="todos"]', settle=1.1)
    if not js("!!document.querySelector('.island-chat')"):
        open_chat()
        time.sleep(0.4)
    pt = center_ignore_point()
    ign_both = check_ignoring_at(pt, settle=0.6)
    shot("E5_both_open_center.png")
    # close both
    if js("!!document.querySelector('[data-collapse-chat]')"):
        click_css("[data-collapse-chat]", settle=0.9)
    if hud().get("deck"):
        click_css(".island-toggle", settle=1.1)
    pt2 = center_ignore_point()
    ign_idle = check_ignoring_at(pt2, settle=0.6)
    shot("E6_idle_passthrough.png")
    e_ok = (
        both1 and chat_stayed_clip and chat_stayed_launch and chat_stayed_search
        and panel_after_collapse and chat_after_hud_close
        and ign_both.get("ignoring") is True
        and ign_idle.get("ignoring") is True
        and typed
    )
    note(
        "E_coexist",
        e_ok,
        both1=both1, coexist=co1, typed=typed, send_enabled=send_enabled, sent=sent,
        chat_stayed_clip=chat_stayed_clip, chat_stayed_launch=chat_stayed_launch,
        chat_stayed_search=chat_stayed_search, search_focus=search_focus,
        panel_after_collapse=panel_after_collapse,
        chat_after_hud_close=chat_after_hud_close,
        ign_both=ign_both, ign_idle=ign_idle,
        clicks={"todo": c_todo, "clip": c_clip, "launch": c_launch, "search": c_search},
    )

    # ---------- F todo depth ----------
    f_ok = False
    f_detail = {}
    try:
        open_hud()
        click_css('[data-nav="todos"]', settle=1.6)
        # close chat so the wide panel is easier to operate (we already proved coexist)
        if js("!!document.querySelector('[data-collapse-chat]')"):
            click_css("[data-collapse-chat]", settle=0.8)
        dismiss_modals()

        # parent + sub via UI
        c_new = click_css(".tv-primary", settle=1.0)
        parent_title = PREFIX + "子待办父项"
        set_value('input.te-input[placeholder="要做什么？"]', parent_title)
        time.sleep(0.2)
        click_css(".te-btn--primary", settle=1.2)
        time.sleep(0.5)
        parent_exists = js("""(() => {
          return Array.from(document.querySelectorAll('.todo-label'))
            .some(e => (e.innerText||'').trim() === %s);
        })()""" % json.dumps(parent_title))
        if not parent_exists and js("!!document.querySelector('.te-card')"):
            # dialog still open: try save again or it never got the title
            set_value('input.te-input[placeholder="要做什么？"]', parent_title)
            time.sleep(0.2)
            click_css(".te-btn--primary", settle=1.2)
            time.sleep(0.4)
            parent_exists = js("""(() => {
              return Array.from(document.querySelectorAll('.todo-label'))
                .some(e => (e.innerText||'').trim() === %s);
            })()""" % json.dumps(parent_title))
        f_detail["create_parent"] = {"click_new": c_new, "title": parent_title, "exists": parent_exists}
        dismiss_modals()
        # click + on that row: find by title
        add_sel = js("""(() => {
          const rows = Array.from(document.querySelectorAll('.todo-row'));
          const row = rows.find(r => (r.querySelector('.todo-label')||{}).innerText === %s);
          if (!row) return null;
          const btn = row.querySelector('.todo-subadd');
          if (!btn) return null;
          btn.setAttribute('data-p12-subadd', '1');
          return '[data-p12-subadd]';
        })()""" % json.dumps(parent_title))
        sub_title = PREFIX + "子项"
        added_sub = False
        if add_sel:
            click_css(add_sel, settle=0.7)
            if js("!!document.querySelector('.todo-sub-input')"):
                set_value(".todo-sub-input", sub_title)
                js("""(() => {
                  const el = document.querySelector('.todo-sub-input');
                  if (!el) return;
                  el.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true, cancelable:true}));
                })()""")
                time.sleep(0.8)
                added_sub = bool(js("""(() => {
                  return Array.from(document.querySelectorAll('.todo-row.sub .todo-label'))
                    .some(e => (e.innerText||'').trim() === %s);
                })()""" % json.dumps(sub_title)))
        shot("F1_parent_and_sub.png")
        # check the sub
        checked = False
        parent_done_before = js("""(() => {
          const rows = Array.from(document.querySelectorAll('.todo-row'));
          const row = rows.find(r => !(r.classList.contains('sub')) && (r.querySelector('.todo-label')||{}).innerText === %s);
          return row ? row.classList.contains('done') : null;
        })()""" % json.dumps(parent_title))
        chk = js("""(() => {
          const rows = Array.from(document.querySelectorAll('.todo-row.sub'));
          const row = rows.find(r => (r.querySelector('.todo-label')||{}).innerText === %s);
          if (!row) return null;
          const b = row.querySelector('.todo-check');
          if (b) b.setAttribute('data-p12-subcheck', '1');
          return b ? '[data-p12-subcheck]' : null;
        })()""" % json.dumps(sub_title))
        if chk:
            click_css(chk, settle=0.9)
            checked = bool(js("""(() => {
              const rows = Array.from(document.querySelectorAll('.todo-row.sub'));
              const row = rows.find(r => (r.querySelector('.todo-label')||{}).innerText === %s);
              return !!(row && (row.classList.contains('done') || (row.querySelector('.todo-check')||{}).classList.contains('checked')));
            })()""" % json.dumps(sub_title)))
        parent_done_after = js("""(() => {
          const rows = Array.from(document.querySelectorAll('.todo-row'));
          const row = rows.find(r => !(r.classList.contains('sub')) && (r.querySelector('.todo-label')||{}).innerText === %s);
          return row ? row.classList.contains('done') : null;
        })()""" % json.dumps(parent_title))
        shot("F2_sub_checked_parent_open.png")
        sub_kept = checked and parent_done_after is False
        f_detail["sub"] = {
            "added": added_sub, "checked": checked,
            "parent_done_before": parent_done_before,
            "parent_done_after": parent_done_after,
            "sub_kept_while_parent_open": sub_kept,
        }

        # daily + weekly via editor
        def wait_dialog(timeout=4):
            t0 = time.time()
            while time.time() - t0 < timeout:
                if js("!!document.querySelector('.te-card')"):
                    return True
                time.sleep(0.2)
            return False

        def create_repeat(title, mode_label, extra_clicks=None):
            dismiss_modals()
            click_css(".tv-primary", settle=0.8)
            if not wait_dialog():
                return {"title": title, "can_save": False, "shown": False, "invalid": "dialog-missing"}
            set_ok = set_value('input.te-input[placeholder="要做什么？"]', title)
            time.sleep(0.2)
            due_ok = js("""(() => {
              const root = document.querySelector('.te-card') || document;
              const btns = Array.from(root.querySelectorAll('.tdt-presets button, .tdt-presets [type=button], button'));
              const b = btns.find(e => (e.innerText||'').trim() === '今天');
              if (b) { b.click(); return true; }
              return false;
            })()""")
            time.sleep(0.25)
            mode_ok = js("""(() => {
              const root = document.querySelector('.te-card') || document;
              const btns = Array.from(root.querySelectorAll('.te-chip'));
              const b = btns.find(e => (e.innerText||'').trim() === %s);
              if (b) { b.click(); return true; }
              return false;
            })()""" % json.dumps(mode_label))
            time.sleep(0.25)
            extra = None
            if extra_clicks:
                extra = extra_clicks()
            time.sleep(0.2)
            can = js("(() => { const b=document.querySelector('.te-btn--primary'); return !!(b && !b.disabled); })()")
            invalid = js("(() => { const el=document.querySelector('.te-card .te-error, .te-card [class*=invalid]'); return el ? (el.innerText||'') : ''; })()")
            title_now = js("(() => { const el=document.querySelector('.te-card input.te-input'); return el ? el.value : null; })()")
            if can:
                click_css(".te-btn--primary", settle=1.2)
            else:
                # 仍尝试点保存，便于截图看禁用态；然后关弹层以免挡住后续
                click_css(".te-btn--primary", settle=0.6)
                dismiss_modals()
            time.sleep(0.35)
            shown = js("""(() => {
              return Array.from(document.querySelectorAll('.todo-label'))
                .some(e => (e.innerText||'').trim() === %s);
            })()""" % json.dumps(title))
            return {"title": title, "set_ok": set_ok, "due_ok": due_ok, "mode_ok": mode_ok,
                    "can_save": can, "shown": shown, "invalid": invalid, "title_now": title_now, "extra": extra}

        daily_title = PREFIX + "每日周期"
        weekly_title = PREFIX + "每周周期"
        # weekly: after clicking 每周, click today's weekday chip if needed
        def pick_today_weekday():
            js("""(() => {
              const map = ['一','二','三','四','五','六','日'];
              const i = (new Date().getDay() + 6) % 7;
              const want = map[i];
              const btns = Array.from(document.querySelectorAll('.te-wd, .te-chips.te-weekdays .te-chip'));
              const b = btns.find(e => (e.innerText||'').trim() === want);
              if (b && !b.classList.contains('on')) b.click();
              return want;
            })()""")

        daily = create_repeat(daily_title, "每天")
        shot("F3_daily_created.png")
        weekly = create_repeat(weekly_title, "每周", pick_today_weekday)
        shot("F4_weekly_created.png")

        # complete daily recurring and see it roll
        before_todos = {t["title"]: t for t in list_seed_todos()}
        daily_before = before_todos.get(daily_title)
        rolled = False
        daily_after = None
        chk_daily = js("""(() => {
          const rows = Array.from(document.querySelectorAll('.todo-row'));
          const row = rows.find(r => !(r.classList.contains('sub')) && (r.querySelector('.todo-label')||{}).innerText === %s);
          if (!row) return null;
          const b = row.querySelector('.todo-check');
          if (b) b.setAttribute('data-p12-dailycheck', '1');
          return b ? '[data-p12-dailycheck]' : null;
        })()""" % json.dumps(daily_title))
        if chk_daily:
            click_css(chk_daily, settle=1.2)
        after_todos = {t["title"]: t for t in list_seed_todos()}
        daily_after = after_todos.get(daily_title)
        if daily_before and daily_after:
            # still present, not permanently done, due moved forward
            rolled = (not daily_after.get("done")) and (
                (daily_after.get("due_at") or 0) > (daily_before.get("due_at") or 0)
                or (daily_after.get("repeat_done_count") or 0) > (daily_before.get("repeat_done_count") or 0)
            )
        # if due was set and complete_todo_recurring happened, due_at should be tomorrow-ish
        shot("F5_daily_rolled.png")

        # calendar: look at cells with chips / data-day
        cal_info = js("""JSON.stringify((() => {
          const cells = Array.from(document.querySelectorAll('.tv-cell[data-day]'));
          const marked = cells.filter(c => c.querySelector('.tv-chip')).map(c => ({
            day: c.getAttribute('data-day'),
            chips: Array.from(c.querySelectorAll('.tv-chip')).map(x => (x.innerText||'').trim()).filter(Boolean)
          }));
          return {cellCount: cells.length, markedCount: marked.length, marked: marked.slice(0, 10)};
        })())""")
        if isinstance(cal_info, str):
            cal_info = json.loads(cal_info)
        # click a marked day (prefer today)
        today = datetime.now().strftime("%Y-%m-%d")
        day_sel = ".tv-cell[data-day='%s']" % today
        if not js("!!document.querySelector(%s)" % json.dumps(day_sel)):
            if cal_info and cal_info.get("marked"):
                day_sel = ".tv-cell[data-day='%s']" % cal_info["marked"][0]["day"]
        clicked_day = False
        if js("!!document.querySelector(%s)" % json.dumps(day_sel)):
            click_css(day_sel, settle=0.9)
            clicked_day = True
        day_list = js("""JSON.stringify((() => {
          const box = document.querySelector('.tv-dayview, .tv-dv, .tv-cal');
          const items = Array.from(document.querySelectorAll('.tv-dv-open, .tv-dayview .todo-row, .tv-cal [class*=dv]')).map(e => (e.innerText||'').trim()).filter(Boolean).slice(0, 12);
          const any = Array.from(document.querySelectorAll('.todo-label, .tv-chip-title, .tv-dv-open')).map(e => (e.innerText||'').trim()).filter(t => t.startsWith(%s));
          return {items: items.slice(0,8), seedsVisible: any};
        })())""" % json.dumps(PREFIX))
        if isinstance(day_list, str):
            day_list = json.loads(day_list)
        shot("F6_calendar_day.png")
        f_detail["daily"] = daily
        f_detail["weekly"] = weekly
        f_detail["rolled"] = {"ok": rolled, "before": daily_before, "after": daily_after}
        f_detail["calendar"] = {"info": cal_info, "clicked": clicked_day, "day_list": day_list, "sel": day_sel}
        f_ok = added_sub and sub_kept and daily.get("shown") and weekly.get("shown") and rolled and (cal_info or {}).get("markedCount", 0) >= 1
    except Exception as e:
        f_detail["exception"] = traceback.format_exc()
        print("F exception", e)
        shot("F_error.png")
    finally:
        removed = cleanup_seeds()
        f_detail["cleaned"] = removed
    note("F_todo_depth", f_ok, **f_detail)

    # finals
    R["official"]["after"] = official_procs()
    off_path = r"C:\Users\wcy\Downloads\x-hub-0.7.2-win-x64\x-hub.exe"
    def off_pid(lst):
        for p in lst or []:
            path = (p.get("ExecutablePath") or "").replace("/", "\\")
            if path.lower() == off_path.lower():
                return int(p["ProcessId"])
        return None
    R["official"]["path"] = off_path
    R["official"]["pid_before"] = off_pid(R["official"]["before"])
    R["official"]["pid_after"] = off_pid(R["official"]["after"])
    R["official"]["untouched"] = (
        R["official"]["pid_before"] == R["official"]["pid_after"]
        and R["official"]["pid_before"] is not None
    )

    keys = ["A_rail_names", "B_rail_visible_with_panel", "C_collapse_chat_keeps_hud",
            "D_island_compact_no_overlap", "E_coexist", "F_todo_depth"]
    R["ok"] = all(R["items"].get(k, {}).get("ok") for k in keys)
    RESULT.write_text(json.dumps(R, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report()
    print("RESULT ok=", R["ok"], "json=", RESULT)
    return 0 if R["ok"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        R["items"]["CRASH"] = {"ok": False, "err": traceback.format_exc()}
        RESULT.write_text(json.dumps(R, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            write_report()
        except Exception:
            pass
        sys.exit(2)
