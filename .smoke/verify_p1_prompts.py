# -*- coding: utf-8 -*-
"""P1: prompts live in the chat cabin — select / switch / persist; no sidebar chest."""
import json, os, sys, time, ctypes
from pathlib import Path
from PIL import ImageGrab

HERE = Path(r"C:\Users\wcy\projects\XXXX\.smoke")
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import verify_v10 as V

OUT = HERE / "p1_prompts"
OUT.mkdir(exist_ok=True)
R = {"items": {}, "ok": False}
SEED_A = {"title": "【P1】摘要提炼", "content": "把下面的内容压成三条要点，每条不超过 20 字："}
SEED_B = {"title": "【P1】会议纪要", "content": "按「结论 / 待办 / 风险」整理下面的会议记录："}


def js(e):
    return V.js(e)


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
    return json.loads(js("JSON.stringify({mode:__helmet.mode,geo:__helmet.geo,docked:__helmet.docked,panel:__helmet.panel})"))


def fg():
    pid = V.pid_of()
    _h, win = V.helmet_hwnd(pid)
    h = int(_h, 16) if isinstance(_h, str) and str(_h).startswith("0x") else int(_h)
    u32 = ctypes.windll.user32
    u32.ShowWindow(ctypes.c_void_p(h), 9)
    u32.SetForegroundWindow(ctypes.c_void_p(h))
    time.sleep(0.35)
    return _h, win


def shot(name):
    p = str(OUT / name)
    ImageGrab.grab(all_screens=True).save(p)
    return p


def click_css(sel, settle=0.8):
    pid = V.pid_of()
    _h, win = V.helmet_hwnd(pid)
    pt = V.screen_pt(sel)
    if not pt:
        js("var el=document.querySelector(%s); if(el) el.click()" % json.dumps(sel))
        time.sleep(settle)
        return {"ok": False, "fallback": "js", "sel": sel}
    px, py = V.to_screen(pt, win["rect"])
    if py < 0 or px < 0:
        return {"ok": False, "err": "negative coords", "screen": [px, py], "sel": sel}
    V.move_to(px, py)
    time.sleep(0.25)
    V.click_at(px, py)
    time.sleep(settle)
    return {"ok": True, "screen": [round(px), round(py)], "sel": sel}


def reveal_if_needed():
    st = hud()
    if st.get("docked") or st.get("geo") == "lip":
        _h, win = V.helmet_hwnd(V.pid_of())
        V.move_to((win["rect"][0] + win["rect"][2]) / 2, win["rect"][1] + 2)
        time.sleep(1.0)
        st = hud()
    return st


def open_chat():
    reveal_if_needed()
    if js("!!document.querySelector('.island-chat')"):
        return True
    if js("__helmet.mode") == "idle":
        c = click_css(".island", 1.0)
        if not js("!!document.querySelector('.island-chat')"):
            js("var el=document.querySelector('.island'); if(el) el.click()")
            time.sleep(1.0)
    else:
        # already deck/chat: click island body
        c = click_css(".island", 1.0)
        if js("__helmet.mode") != "chat":
            js("var el=document.querySelector('.island'); if(el) el.click()")
            time.sleep(1.0)
    return bool(js("!!document.querySelector('.island-chat')"))


def snap():
    return json.loads(js("""JSON.stringify((() => {
      const ta = document.querySelector('.composer textarea');
      const chip = document.querySelector('[data-prompt-chip]');
      const pop = document.querySelector('[data-prompt-pop]');
      const items = Array.from(document.querySelectorAll('[data-prompt-item]')).map(e => ({
        id: e.getAttribute('data-prompt-item'),
        on: e.classList.contains('is-on'),
        text: (e.querySelector('.pi-t') ? e.querySelector('.pi-t').innerText : e.innerText || '').trim()
      }));
      const navs = Array.from(document.querySelectorAll('[data-nav]')).map(e => ({
        nav: e.getAttribute('data-nav'),
        title: (e.getAttribute('title') || e.innerText || '').trim()
      }));
      const ls = localStorage.getItem('rr.hud.chatPromptId');
      return {
        mode: window.__helmet && __helmet.mode,
        hasChat: !!document.querySelector('.island-chat'),
        promptBtn: !!document.querySelector('[data-prompt-open]'),
        promptBtnText: (document.querySelector('[data-prompt-open]') || {}).innerText || '',
        pop: !!pop,
        text: ta ? ta.value : '',
        chip: chip ? {id: chip.getAttribute('data-prompt-id'), text: (chip.innerText||'').trim()} : null,
        items,
        navs,
        ls,
        titles: document.title
      };
    })())"""))


def note(name, ok, **extra):
    item = {"ok": bool(ok), **extra}
    R["items"][name] = item
    print(("PASS " if ok else "FAIL ") + name + " | " + json.dumps(item, ensure_ascii=False)[:400])
    return ok


def cleanup_seeds():
    left = inv("list_snippets") or []
    if isinstance(left, str):
        try:
            left = json.loads(left)
        except Exception:
            left = []
    removed = []
    for x in left or []:
        if str(x.get("title") or "").startswith("【P1】"):
            inv("delete_snippet", {"id": x["id"]})
            removed.append(x["id"])
    return removed


def ensure_seeds():
    cleanup_seeds()
    a = inv("create_snippet", dict(SEED_A))
    b = inv("create_snippet", dict(SEED_B))
    if isinstance(a, str):
        a = json.loads(a)
    if isinstance(b, str):
        b = json.loads(b)
    return a, b


def boot_connect(timeout=90):
    if not V.connect_ws(timeout):
        return False
    if not V.wait_ready(timeout):
        return False
    t0 = time.time()
    while time.time() - t0 < 40:
        try:
            if js("!!window.__helmet && __helmet.boot === false"):
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main():
    if not boot_connect():
        raise SystemExit("cdp not ready")
    pid = V.pid_of()
    print("pid", pid, "pre", hud())
    fg()
    if not open_chat():
        note("P1-1 对话舱内能看到并选用已有提示词", False, err="chat not open", hud=hud())
        (HERE / "p1_prompts_result.json").write_text(json.dumps(R, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    a, b = ensure_seeds()
    print("seeds", a, b)
    # 上一轮残留在输入框里的正文会让 applyPrompt 走「保留手写、前置提示词」分支，
    # 把选用断言打成假红。测选用/切换前先清输入和选中态。
    js("""(() => {
      const e = document.querySelector('.composer textarea');
      if (e) {
        const d = Object.getOwnPropertyDescriptor(e.constructor.prototype, 'value');
        if (d && d.set) d.set.call(e, ''); else e.value = '';
        e.dispatchEvent(new Event('input', {bubbles: true}));
      }
      localStorage.removeItem('rr.hud.chatPromptId');
      return true;
    })()""")
    js("var x=document.querySelector('[data-prompt-clear]'); if(x) x.click()")
    time.sleep(0.3)

    # refresh list by toggling pop
    if js("!!document.querySelector('[data-prompt-pop]')"):
        click_css("[data-prompt-open]", 0.4)
    c_open = click_css("[data-prompt-open]", 0.9)
    s1 = snap()
    shot1 = shot("01_list_in_chat.png")
    # must see both seeds in the in-cabin pop, not via float
    ids = {str(x["id"]) for x in s1.get("items") or []}
    ok1 = (
        s1.get("hasChat")
        and s1.get("promptBtn")
        and s1.get("pop")
        and str(a["id"]) in ids
        and str(b["id"]) in ids
        and not any("百宝箱" in (n.get("nav") or "") + (n.get("title") or "") for n in s1.get("navs") or [])
    )
    note(
        "P1-1 对话舱内能看到并选用已有提示词",
        ok1,
        click=c_open,
        promptBtn=s1.get("promptBtnText"),
        items=s1.get("items"),
        hasChat=s1.get("hasChat"),
        pop=s1.get("pop"),
        shot=shot1,
    )

    # select A
    c_a = click_css('[data-prompt-item="%s"]' % a["id"], 0.9)
    s2 = snap()
    shot2 = shot("02_selected_a.png")
    chip_ok_a = bool(s2.get("chip") and str(a["id"]) in str(s2["chip"].get("id") or "") and SEED_A["title"] in (s2["chip"].get("text") or ""))
    text_ok_a = (s2.get("text") or "").strip() == SEED_A["content"]
    # reopen pop to see is-on
    click_css("[data-prompt-open]", 0.7)
    s2b = snap()
    on_ids = [it["id"] for it in s2b.get("items") or [] if it.get("on")]
    marked = any("已选用" in (it.get("text") or "") and str(it["id"]) == str(a["id"]) for it in s2b.get("items") or [])
    shot2b = shot("02b_selected_mark.png")
    ok2 = chip_ok_a and text_ok_a and on_ids == [str(a["id"])] and marked
    note(
        "P1-2 选用一条：输入框回填、chip 显示选中",
        ok2,
        click=c_a,
        chip=s2.get("chip"),
        text=s2.get("text"),
        ls=s2.get("ls"),
        on_ids=on_ids,
        marked=marked,
        shot=shot2,
        shot_mark=shot2b,
    )

    # switch to B
    c_b = click_css('[data-prompt-item="%s"]' % b["id"], 0.9)
    s3 = snap()
    shot3 = shot("03_switched_b.png")
    click_css("[data-prompt-open]", 0.7)
    s3b = snap()
    on_ids_b = [it["id"] for it in s3b.get("items") or [] if it.get("on")]
    marked_b = any("已选用" in (it.get("text") or "") and str(it["id"]) == str(b["id"]) for it in s3b.get("items") or [])
    marked_a_still = any("已选用" in (it.get("text") or "") and str(it["id"]) == str(a["id"]) for it in s3b.get("items") or [])
    chip_ok_b = bool(s3.get("chip") and str(b["id"]) in str(s3["chip"].get("id") or "") and SEED_B["title"] in (s3["chip"].get("text") or ""))
    text_ok_b = (s3.get("text") or "").strip() == SEED_B["content"]
    ok3 = chip_ok_b and text_ok_b and on_ids_b == [str(b["id"])] and marked_b and not marked_a_still
    shot3b = shot("03b_switch_mark.png")
    note(
        "P1-3 切换到另一条：只保留一个选中态",
        ok3,
        click=c_b,
        chip=s3.get("chip"),
        text=s3.get("text"),
        ls=s3.get("ls"),
        on_ids=on_ids_b,
        marked_b=marked_b,
        marked_a_still=marked_a_still,
        shot=shot3,
        shot_mark=shot3b,
    )

    # persist: kill repo only, relaunch, open chat by click (no hotkey)
    old_pid = V.pid_of()
    killed = V.kill_pid(old_pid) if old_pid else False
    time.sleep(2)
    new_pid = V.launch()
    V.WS = None
    time.sleep(2)
    cdp_ok = boot_connect()
    print("restart", old_pid, "->", new_pid, "killed", killed, "cdp", cdp_ok)
    fg()
    opened = open_chat()
    s4 = snap()
    shot4 = shot("04_after_restart.png")
    ok4 = (
        killed
        and cdp_ok
        and opened
        and (s4.get("text") or "").strip() == SEED_B["content"]
        and s4.get("chip")
        and SEED_B["title"] in (s4["chip"].get("text") or "")
        and str(s4.get("ls") or "") == str(b["id"])
    )
    note(
        "P1-4 杀掉仓库进程再拉起后选中项仍在",
        ok4,
        old_pid=old_pid,
        new_pid=new_pid,
        killed=killed,
        cdp=cdp_ok,
        opened=opened,
        chip=s4.get("chip"),
        text=s4.get("text"),
        ls=s4.get("ls"),
        hud=hud(),
        shot=shot4,
    )

    # no sidebar treasure chest: open deck via a chip or nav, inspect rail
    # close pop if open, go to a panel through function bar or just read navs from current chat
    navs = s4.get("navs") or snap().get("navs") or []
    # also probe after expanding deck if we can click a fn-bar button without leaving evidence broken
    # read nav even in chat mode — rail exists in hud
    forbidden = []
    for n in navs:
        blob = (n.get("nav") or "") + " " + (n.get("title") or "")
        if any(k in blob for k in ("百宝箱", "prompt", "prompts", "snippets", "提示词")):
            forbidden.append(n)
    # extra DOM probe
    extra = js("""JSON.stringify({
      railPrompt: document.querySelectorAll('.rail [data-prompt-open], .rail [data-nav=\"prompts\"], .rail [data-nav=\"prompt\"]').length,
      panelPromptOpen: document.querySelectorAll('.panel-col [data-prompt-open]').length,
      navLabels: Array.from(document.querySelectorAll('.rail [data-nav], .nav-btn')).map(e => (e.getAttribute('data-nav')||'') + ':' + (e.getAttribute('title')||e.innerText||'').replace(/\\s+/g,' ').trim())
    })""")
    try:
        extra = json.loads(extra) if isinstance(extra, str) else extra
    except Exception:
        extra = {"raw": extra}
    shot5 = shot("05_no_sidebar_chest.png")
    ok5 = (not forbidden) and int((extra or {}).get("railPrompt") or 0) == 0
    note(
        "P1-5 不出现新的侧栏百宝箱入口",
        ok5,
        navs=navs,
        forbidden=forbidden,
        extra=extra,
        shot=shot5,
    )

    removed = cleanup_seeds()
    titles = None
    try:
        import cdp
        titles = [t.get("title") for t in cdp.list_targets(9222)]
    except Exception as e:
        titles = {"error": str(e)}
    xhub_titles = [t for t in (titles or []) if isinstance(t, str) and "x-hub" in t.lower()]
    R["titles_after"] = titles
    R["xhub_titles"] = xhub_titles
    R["cleaned"] = removed
    R["pid"] = V.pid_of()
    R["ok"] = all(v.get("ok") for v in R["items"].values()) and len(R["items"]) >= 5
    (HERE / "p1_prompts_result.json").write_text(json.dumps(R, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RESULT", json.dumps({"ok": R["ok"], "summary": {k: v["ok"] for k, v in R["items"].items()}, "xhub_titles": xhub_titles}, ensure_ascii=False))
    return 0 if R["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())