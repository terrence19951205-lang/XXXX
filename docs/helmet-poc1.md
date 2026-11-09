# Helmet POC-1 · 旁路座舱壳

旁路全屏透明窗，**不替换**现有仪表盘 / 浮窗。基于 `v0.9.7` 分支 `feat/helmet-shell`。

## 如何开窗

启动应用后 Helmet 窗已预创建并隐藏。从任意可 invoke 的上下文调用：

```ts
import { invoke } from '@tauri-apps/api/core'

await invoke('helmet_show')    // 铺满主屏 work area 并显示
await invoke('helmet_hide')    // 隐藏
await invoke('helmet_toggle')  // 返回是否可见 boolean
```

DevTools / 临时调试也可在主窗控制台直接 `invoke('helmet_toggle')`。

本 POC **未**挂托盘菜单或全局快捷键，避免改动既有入口。

## 命令 API

| 命令 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `helmet_show` | — | `()` | 定位到主屏 work area → emit `helmet-shown` → show |
| `helmet_hide` | — | `()` | 关穿透 → hide → emit `helmet-hidden` |
| `helmet_toggle` | — | `bool` | 显隐切换；`true` = 当前可见 |
| `helmet_set_ignore_cursor_events` | `{ ignore: bool }` | `()` | 整窗点击穿透 |
| `helmet_cursor_local` | —（当前窗） | `Option<(f64,f64)>` | 光标相对窗客户区的逻辑坐标；窗外 `null`（Windows） |

窗口 label：`helmet`（已登记 `capabilities/default.json`）。

事件（emit 到 `helmet`）：

- `helmet-shown` — 载荷 `{ x, y, width, height }`（主屏 work area 物理 px）
- `helmet-hidden`

## 前端行为

- 入口：`helmet.html` → `src/light/helmet.ts` → `HelmetShell.vue`
- 默认 **collapsed**；`localStorage['rr.hud.collapsed']`（`1`/`0`）记忆；无键则收起
- 收起只留 ≤48px 唤起条（右上）
- 展开：上 / 左 / 下切角灰盒占位；**无右栏**；grain / 色差默认不渲染
- 根与装饰 `pointer-events: none`；`.hit` 可点
- 展开时默认开穿透；80ms 轮询 `helmet_cursor_local`，光标在 `.hit` 上则关穿透

## 窗口矩形：收起缩到条，展开还原工作区

收起不是"关掉穿透后留一条能点的缝"，而是**把窗口本身缩到唤起条矩形**
（`getCurrentWindow().setPosition/setSize`，底层即 `SetWindowPos`）：

| 状态 | 窗口（物理 px，2560×1528 工作区 / 150% 缩放） | 说明 |
|------|--------------------------------------------|------|
| 收起 | `(2305,18)-(2539,72)` = 234×54（CSS 156×36） | 与展开态条原位逐像素重合，可点区域就是那条 |
| 展开 | `(0,0)-(2560,1528)` | 主屏 work area（后端 `helmet_show` 铺满） |

实现要点（`HelmetShell.vue`）：

- 换算倍率 `s = 本窗物理 inner.width / documentElement.clientWidth`，全用本窗自身尺寸，
  **不依赖 `helmet-shown` 载荷**（事件可能早于前端挂载而丢失）
- 收缩前把窗口矩形记进 `expandedRect`，展开时原样还原；无记录才退回载荷/`helmet_show`
- 收起态加 `anchored` 类，条改成 `top:0; right:0` 贴满小窗；此时隐藏 `.dbg` 角标
- 收起态 `WS_EX_TRANSPARENT` 必须为 **false**（否则条自己点不到）；小窗之外没有窗口，
  所以中央/桌面天然可点
- `ignoring` 初值必须是 `null` 而不是 `false`——否则首次 `setIgnore(false)` 被短路，
  原生残留的穿透位清不掉，条会点不动（实机踩过）

## 本地验证（本轮可不跑 Win）

1. 确认分支：`git checkout feat/helmet-shell && git merge-base --is-ancestor v0.9.7 HEAD`
2. 常规前端依赖就绪后：`npm run tauri dev`（或项目惯用脚本）
3. 主窗控制台：`await invoke('helmet_show')`
4. 验收：
   - 默认收起，仅右上唤起条
   - 点条 / Esc 展开；中央区域鼠标应落到下层窗口
   - 移到上/左/下灰盒可点；移出后恢复穿透
   - 再收起后只留唤起条

实机六条取证脚本：`.smoke/verify_poc1.py`（真窗口 + 真鼠标 + CDP 读 DOM，进程需
`SetProcessDpiAwarenessContext(PerMonitorV2)`，否则 Win32 矩形被 DPI 虚拟化）。

## 已知限制

- **单窗动态穿透**：穿透开启后 WebView 收不到 `pointerenter`；POC 用系统光标轮询兜底。Windows 实机仍需验证 DPI / 多屏 / 任务栏避让下的命中精度与切换延迟。
- 收起/展开用前端 `core:window:allow-set-size` / `allow-set-position` 驱动（`helmet` 已在
  `capabilities/default.json` 授权），Rust 侧窗逻辑未改，故无需重新链接。
- 条尺寸按内容量测（当前 156×36 CSS），改文案会改宽度，收缩矩形自动跟随。
- `helmet_cursor_local` 目前仅 Windows 实现；其它平台返回 `null`，依赖 `mouseenter`/`mouseleave` 兜底（穿透开时同样可能失效）。
- 未接托盘 / 快捷键 / 主窗入口；未改仪表盘路由。
- HUD 为占位灰盒，非像素级还原 `reality-raid-hud-v05.html`。

## 关键文件

- `src-tauri/src/helmet_window.rs`
- `src-tauri/src/lib.rs`（mod / init / commands）
- `src-tauri/capabilities/default.json`（`helmet` + ignore-cursor 权限）
- `helmet.html` / `src/light/helmet.ts` / `src/components/HelmetShell.vue`
- `vite.config.ts`（多页入口 `helmet`）
- `docs/helmet-poc1.md`

## v4 收口：侧栏两端 / 工作面板边框 / 产品名 shell-hub

对照 `.refs/reality-raid-hud-v08-ascii-explore-v4.html` 与截图 `.refs/hud-v4-01-sidebar.png`：

- **侧栏两端**：取消 `.cut` 折线切角（`clip-path: none`、`svg.edge` 隐藏、`::before/::after`
  端饰清空），改 `1px solid rgba(0,229,255,.22)` + `border-radius: 12px` + inset 高光 + 轻阴影
- **角标**：`.fx .corners` 只去掉靠侧栏两端（`.tl`/`.bl`）与左侧 tick/brace，右上/右下保留
- **工作面板**：笔记/待办/剪贴板/速达共用 `.panel-col.panel` 这一层外壳，直接换成与侧栏同款
  圆角细边（不复制第二套壳）；下檐 `.eave-bot`、灵动岛、对话舱、glance 的切角不动
- **笔记内容裁切（实测修掉）**：`.notes-split` 的 `1fr` 轨道隐含最小宽度 = 标题输入框
  min-content（≈210px），整块被顶出面板右边界 15px 后由 `overflow:hidden` 裁掉。改
  `grid-template-columns: 104px minmax(0, 1fr)` + `.note-ed { min-width: 0 }` +
  `input.title { width:100%; min-width:0 }` 后，20 个内容节点全部落在面板内
- **产品名**：界面标题、岛上品牌（`shell-hub` / `SHELL-HUB`）、开场卡标题、aria-label、
  按钮提示、面板说明统一 `shell-hub`；仓库路径 / 进程名 / `%APPDATA%\x-hub` / smoke
  identifier 不动。HUD 窗 Rust 侧 `.title("Helmet")` 是内部 label（`skip_taskbar` +
  无边框，从不显示，冒烟脚本按它找窗），本块不改
- **验收**：`.smoke/verify_v4.py` R1–R8（真窗口 + 真鼠标 + CDP），实测 8/8 通过；
  截图 `.smoke/v4_sidebar.png`（侧栏+笔记）、`.smoke/v4_deck_v4.png`（展开态）、
  `.smoke/v4_chat.png`（对话舱）、`.smoke/v4_boot2.png`（开场卡）

## v5 开场照抄探索稿 · 图标 · updater 闸门

对照 `.refs/reality-raid-hud-v08-ascii-explore-v3.html`（开屏 + 岛）与
`.refs/shell-hub-icons/`（图标）。上一轮的"开屏"是自己画的字符雨 + 水线 + 气泡，
和探索稿不是一回事，本轮整块换掉。

- **引擎搬原件**：`src/components/helmet/ascii-sharks.js` 从探索稿第 1152 行**原样**拷入
  （上游 ascii-sharks, MIT：鱼群 boids + 鲨鱼捕食 + 字符栅格化），只在末尾补一行 ESM 导出，
  代码未改一个字符；类型声明 `ascii-sharks.d.ts` 只声明用到的 `OceanEngine`。
- **开场**：`HelmetBoot.vue` 逐条对齐 v3 的 `startBoot/endBoot` ——
  `new AsciiSharks.OceanEngine(canvas, [classic 1, mako .86, hammerhead .78, thresher .7])`、
  5.6s（`prefers-reduced-motion` 1.6s，只画静止剪影）、进度条 `width 0→100%` 线性过渡、
  标题 420ms 后 `is-ready` 淡入、`Enter/Esc/空格` 与「跳过」按钮可跳、
  结束 `destroy()` 卸引擎与全部 window 监听 → `.is-out` 淡出 500ms → 组件卸载（桌面不留 rAF）。
  旧的开场 CSS（`.boot/.boot-card/.boot-cap/...`）与自绘鲨鱼帧、水线、气泡全部删除，
  改用 v3 的 `.rra-boot` 家族；取证口 `window.__helmetBoot` 暴露 `engine/engineClass/sharkKinds/frames/ink/tornDown`。
- **图标**：`bundle.icon` 改指 `icons/shell-hub-{32,48,128,256,1024}.png` + `shell-hub-icon.icns/ico`。
  tauri-build 取列表里第一个 `.ico` 同时嵌入 exe 资源与 `default_window_icon`（窗口/托盘图标），
  实测 exe 图标与 `shell-hub-32.png` 逐像素均差 0.1，与官方 `32x32.png` 均差 115.3。
- **updater 闸门**：`updater::updater_disabled()`，identifier 以 `-smoke` 结尾的冒烟构建
  既不自动检查、也不执行 `apply_pending_update`。原因见 updater.rs 注释——调试 exe 有独立数据根，
  那份配置默认开着自动检查，上一轮就这样被官方 v0.9.8 就地自替换，验证对象整个换了人。
  正式构建行为不变；冒烟数据根同时置 `auto_update_enabled=false` 并清空 `data/updates/`。
- **岛尺寸回缩（本轮实测修掉）**：`measureIsland()` 在窗口已缩到唇边时会量到被裁切的
  `offsetWidth`，唇边随之 428 → 276 → … 越缩越窄，顶部热区最终消失（B2 一开始就挂在这）。
  现在「比视口还宽」和「小于 180px」的读数一律丢弃，唇边稳定 428×10 CSS。
  另外 `captureFrame()` 只接受 ≥640×400 CSS 的满屏基准（小窗尺寸曾被误记成基准，
  deck 就再也顶不满）；`applyLip/applyBand` 在 280ms 动画后再确认一次「还在 idle」才动窗口。
- **不要双路改窗**：`expandToWorkArea()` 里 setSize 不达标时**不要**再 `invoke('helmet_show')`——
  后端也会 setSize，两路同时改窗会卡在中间尺寸（实测把窗口缩成 276×3，前端 viewport 只剩 74×2），
  岛的热区随之消失。基准错误的下次 `helmet-shown` 会自愈。
- **构建工具链**：GNU 目标下 tauri-build 要用 `windres`/`ar`（本机原先没有，已放到
  `~/.local/bin`），并给 windres 备了 `gcc.cmd`（转 `gcc_preprocess.py`）当恒等预处理器——
  `resource.rc` 没有 `#include`，直通即可。构建后仍需 `rcedit --application-manifest
  .smoke/app.manifest` 补 Common-Controls 6 / PerMonitorV2（build.rs 的清单嵌入只走 MSVC）。
- **验收**：`.smoke/verify_v5.py` B1–B5，结果 `.smoke/v5_result.json`；截图
  `.smoke/v5_boot.png` / `v5_boot2.png`（开屏）、`v5_revealed.png`（岛展开）、`v5_deck.png`（躯干）、
  `v5_sidebar.png`（侧栏+笔记）、`v5_chat.png`（对话舱）。

## v6 冒烟入口形态：只留 Helmet（去悬浮球 / 去原版主仪表盘）

用户反馈打开冒烟包还能看到「x-hub/悬浮球」。B1–B5 已过，本轮只改入口形态，判定口径与
updater 冒烟闸门同一条：`identifier` 以 `-smoke` 结尾（`lib::is_smoke_build`，
`updater::updater_disabled` 改为复用它）。正式包（`x-hub`）行为不变。

- **不建悬浮球**：`floating_ball::init` 在烟雾构建直接 return，`floating-ball` 窗连隐藏常驻
  都不创建；`sync_with_main` 同样空操作。没有窗口就没有托盘/热键/右键菜单任何唤出路径。
- **不显示原版主仪表盘**：Rust 启动期在 `restore_window_state` 之后调 `tray::hide_window`
  （自维护 `MAIN_WINDOW_VISIBLE` 一并置 false）；前端 `main.ts` 另经 `get_smoke_mode`
  命令同口径 gate，主窗页面自己也不 `show()`/`setFocus()`。仅 Helmet + chat/clipboard/notice
  等隐藏常驻窗存在。
- **托盘/热键改为 Helmet**：`tray::show_window` 烟雾下走 `helmet_window::show`；
  `toggle_window` 只唤起 Helmet（不切显隐，避免把主 UI 关掉）；`toggle_main_window`
  兜底同样只唤起 Helmet；`hide_window` 只收主窗、明示不动 Helmet。
- **验收**：`.smoke/verify_v6.py`，结果 `.smoke/v6_result.json`。F1 可见窗无「悬浮球」、
  主仪表盘不可见（另有一个 WebView2 4×4 分层透明辅助窗 `*-siw`，非 UI，v5 起就存在）；
  F2 可见主 UI 为 Helmet、CDP 有 Helmet；F3 按 Ctrl+Shift+Space 后仍无悬浮球/主仪表盘，
  日志留 `[smoke] 快捷键/托盘切换…`；F4 悬浮球窗与创建日志均无、updater 未冲掉
  （`auto_update_enabled=false`、`data/updates/` 空）、exe 图标仍与 `shell-hub-32.png` 一致。
- **本轮不动**：侧栏功能清单、原版 x-hub 侧栏入口、笔记三栏交互、shell-hub 名与图标、
  开屏 ASCII 鲨鱼、v3 岛交互、v4 侧栏圆角细边。

## v7 笔记三栏可点 · 侧栏 P0 入口（N0–N4）

- **笔记三栏真点**：左功能栏点「笔记」→ 中栏列表 → 点条目开右栏编辑；新建 / 切换可用；
  三栏并存，收起分两层（先收右栏、再收中栏）。
- **侧栏入口**：待办 / 笔记 / 聊天-AI / 剪贴板 / 启动常用工具 / 搜索 / 设置七项均可点，
  面板在 HUD 内展开，不弹原版浮窗。
- **入口形态不回退**：可见窗只有 `Helmet`（另有 WebView2 帮助窗 `*-siw`，非 UI），
  无「悬浮球」、无原版主仪表盘。
- **验收**：`.smoke/verify_v7.py` → `.smoke/v7_result.json`（N0–N4 全 `ok`）。

## v8 不透明度对齐对话舱（O1–O4）

- 侧栏 rail、笔记 list、editor 背景统一 `--glass-chat`
  （`linear-gradient(180deg, rgba(28,36,48,.96) 0%, rgba(8,12,20,.97) 100%)`），
  与岛对话舱同档，不再是半透明"雾感"。
- v4 的青边圆角保留：`1px solid rgba(0,229,255,.22)`（150% 缩放下 computed 0.667px）、
  `border-radius: 12px`；无宠物、无 Bento。
- **验收**：`.smoke/verify_v8.py`（只读，不启停进程）→ `.smoke/v8_result.json`；
  截图 `v8_before_opacity.png` / `v8_after_opacity.png`。

## v9 P0 六项真点（T1–T6）

全部只连 9222 上的 Helmet 页、真鼠标点击，走既有 tauri 命令，**不新增数据表**：

| 项 | 内容 | 结果 |
|---|---|---|
| T1 待办 | 新增 / 改标题 / 勾完成 / 落盘 | ok |
| T2 聊天 AI | 多会话 + 可选模型 + 真实回复（非字幕） | ok |
| T3 剪贴板 | 侧栏可点、点选取用 | ok |
| T4 启动常用 | 调起应用后自动回穿透 | ok |
| T5 搜索 | 一处搜待办 + 笔记，点击直达 | ok |
| T6 日衰 | 岛显示剩余工时%，上下班时间可配 | ok |

- **验收**：`.smoke/verify_v9.py` → `.smoke/v9_result.json`，每项截图 `v9_<item>.png`。

## v10 壳收尾 · 设置持久化 · 快捷键（A/B/C）

- **A 壳**：A1 中央真穿透且控件可点（真鼠标点击落到下层窗）；A2 收起只剩唇边、
  顶部唤出热区仍在；A3 边距不吃点击；A5 Esc 收起；A6 无悬浮球、无第二入口。
- **B 设置**：B1 上下班时间生效且重启仍在；B2 聊天模型选择重启仍在；A4 收起态重启还原。
- **C 快捷键 → HUD 内面板**：`Ctrl+Shift+Space` 开/收、`Ctrl+Shift+K` 聊天、
  `` Ctrl+` `` 剪贴板、`Ctrl+K` 搜索、`Ctrl+Shift+N` 笔记。
  按下后可见窗仍只有 `Helmet` + `*-siw`——剪贴板浮层、对话独立窗、悬浮球窗口枚举均为 0；
  笔记数据前后一致（1–9 条未动）。
- **验收**：`.smoke/verify_v10.py`（`shell` / `settings-pre` / `restart` / `settings-post` / `hotkeys`）
  → `.smoke/v10_result.json`、`v10_hotkeys.json`、`v10_settings.json`。

## v11 视觉方向稿 v1 全面落地（9/9）

对照 `.refs/shell-hub-visual-direction-v1.html` 与 `…-HANDOFF.md`（用户已过目）：

- **岛 morph**：收起 268×40 / r22 ↔ 对话舱 420×520 / r26；点岛开对话、Esc 或「收起」关对话；
  岛右侧 ▾ 只管 HUD 壳（rail + 下檐 + 面板）展收，不与对话混用。
- **材质统一**：岛收起+舱、rail、列表、编辑、下檐全部 `--glass-chat`；
  `1px solid rgba(0,229,255,.22)` + `12px` 圆角 + `blur(18px) saturate(1.2)`。
- **第一人称 HUD**：中央真穿透，vig / scan / ASCII 仅作微点缀（rail 7px .30、work 6px .14、
  eave 5px .24），无宠物、无 Bento，角标只留右上/右下。
- **展开全屏光效**：HUD 已收起 → 点岛右 ▾ 再展开时 `playExpandCeremony()`
  （`watch(deckOpen) false→true`，`flush:post`），`.fx.is-ceremony` 下
  grain `gFlash` / chroma `cFlash` / edge `eFlash` 各 150ms；实测类名在 378→549ms、
  全屏像素差 mean 5.6/255、max 91；`.fx` 恒 `pointer-events: none` 不挡穿透；
  `prefers-reduced-motion` 跳过；快捷键展开同路；展开→收起不闪。
- **笔记三栏**：结构保留（rail → list → editor），材质随方向稿。

两个 WebView2 坑（已在 `helmet.css` 注释与本轮 findings 留档）：

1. **`backdrop-filter` 只写无前缀一条**：写 `-webkit-` 副本会被 Lightning CSS 合并成
   只剩 `-webkit-`，WebView2 不认 ⇒ blur 实际为 `none`。去掉副本后构建产物保留两条，
   computed 实测 `blur(18px)` 生效。
2. **透明 WebView 里 `mix-blend-mode: screen/overlay` 没有"底"可混** ⇒ 光效肉眼不可见；
   grain/chroma/edge 改为自带 alpha 的普通叠加（Windows 整体合成到桌面），肉眼可见且可截图。

- **验收**：`.smoke/verify_v11.py visual` → `.smoke/v11_visual.json`（9 项全 `true`）；
  系统截屏 `v11_01_island_compact.png` … `v11_final_idle.png`；
  光效证据 `v11_05_expand_ceremony.png`（真屏峰值）、`v11_expand_ceremony.gif`、
  `v11_05c_expand_diff_x8.png`（前后差量 ×8）。
  **HUD 是透明覆盖层：CDP 截图没有桌面底，混合模式与 alpha 与真实渲染不可比，
  验收图一律走系统截屏。**

## v12 提示词嵌聊天（P1 第一项）

- **位置**：对话舱输入框上方一行——`提示词` 按钮（括号里是库条目数）+ 已选中的标题 chip
  （`×` 取消选用）。点开向上弹「提示词百宝箱」只读列表（`snippets`），每次打开都重拉一次，
  主窗刚加的条目不用重开对话就能看见。
- **语义**：选用 = 把提示词内容放进输入框，**不代发**（发不发由人决定）。
  切换时若上一版提示词没被手改过 → 整体替换；若已手写正文 → 新提示词放在前面、正文保留。
  取消时若输入框仍是该提示词原文则清空，否则只清选中态。
- **持久化**：选中 id 落 `localStorage['rr.hud.chatPromptId']`；重开进程后 chip 还在，
  输入框为空则回填该提示词内容；库里那条被删掉时自动清掉悬挂选中态。
- **边界**（不做的事）：舱内不新建 / 改名 / 删除提示词，增删改仍在主窗提示词百宝箱；
  不扩到待办、侧栏，不新增第二套提示词数据结构。
- **验收**：`.smoke/verify_v12.py`——真鼠标点按钮、真按键（`Ctrl+Shift+K` 开舱、
  `Ctrl+Shift+Space` 开壳）、真重启进程，6 项全绿：
  ① 入口与列表（条目数与库一致）② 选用一条且消息数不变（不代发）
  ③ 切第二条整体替换、只留一个选中 ④ 重启后 chip + 回填仍在
  ⑤ 待办/侧栏无提示词 DOM、发送按钮仍按输入启用 ⑥ 自测条目已清、库里不留痕。
  证据 `.smoke/v12_result.json`；系统截屏 `v12_01_prompt_pop.png`（面板）、
  `v12_02_prompt_applied.png`（选用后）、`v12_03_after_restart.png`（重启后）。
- **构建**：先杀旧冒烟 PID，`npx tauri build --debug --no-bundle --config .smoke/tauri.smoke.json`，
  再 `rcedit --application-manifest .smoke/app.manifest` 补 PerMonitorV2；**未出安装包**。
- **数据说明**：验收时提示词库为空，用三条 `【自测】` 临时条目验证，验完已删除（库仍 0 条）。

## 交付边界（v12 时点）

- 只在 `feat/helmet-shell` 分支的本机 **debug 冒烟包**（identifier 带 `-smoke`，
  `--no-bundle`）验证；正式包 identifier 不带 `-smoke`、行为不变，**未出安装器**。
- 未验：多屏、非整数 DPI、任务栏避让下的命中精度与切换延迟。
- 产品对外名统一 **shell-hub**；仓库路径 / 进程名 / `%APPDATA%\x-hub` / 冒烟 identifier 不动。
