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

## v13 展开光效改为源码移植（缺口 1 收口）

**结论先写**：v11/v12 那套光效数值是我自己造的（veil 压暗层、grain 0.14、chroma 0.95、
`z-index:70`），不是参考稿的；现全部撤掉，改为从
`reality-raid-hud-v08-ascii-explore-v4.html` 的 `.fx` 家族逐条搬值。

### 移植的原始数值（不再自行发明）

| 项 | 源码值 |
| --- | --- |
| `.fx` | `opacity/visibility` 过渡 `var(--t-flash)=150ms var(--ease)` |
| `.scan` | `repeating-linear-gradient` 3px / `rgba(0,229,255,.01)`，`screen`，`opacity:.4` |
| `.vig` | `inset 0 0 110px rgba(0,0,0,.28)`；展开态 `inset 0 0 90px rgba(0,0,0,.35)` + 1px 青边 `.06` |
| `.grain` | `feTurbulence fractalNoise / .9 / 3 / stitchTiles`，`160px`，`overlay` |
| `.chroma` | `90deg rgba(255,46,151,.04) → transparent 30% → transparent 70% → rgba(0,229,255,.04)`，`screen` |
| `gFlash` | `0 → .04@40% → 0` |
| `cFlash` | `0 → .65@40% → 0` |
| `.corners` | `inset 18px`（展开 14px）/ `28px`（展开 32px）/ 2px 边 / `.72`（展开 `.82`） |
| `cIn` / `cOut` | `0→1@50%→.7` / `.7→1@40%→0` |
| 层序 | `.fx` 在 `.hud` **之下**（源码 z 12 / 20）；本壳对应 30 / 40，只染桌面与穿透区，不压面板 |

### 真正的病根（不是数值）

- **`classList.add('is-ceremony')` 会被 Vue 的 `:class` 在下一次 patch 覆盖掉**，
  仪式类只活了一个渲染周期，闪光根本没机会跑满 150ms。改由 `fxCeremonyOn` /
  `fxFlashoutOn` 两个 `ref` 驱动 `:class`，`nextTick` 后再置真，150ms 后置假。
- 收起按源码走 `cOut`：`.fx` 多留 150ms（`is-flashout`），取景框先亮后收，再整层隐去；
  开→关不重放 grain/chroma。
- **更正 v11 的说法**：当时判定「透明 WebView 里 `mix-blend-mode` 没有底可混所以不可见」，
  这个结论是错的。透明底上 `screen/overlay` 的合成结果就是源色本身，可见；
  当时真正的原因是上面的类被抹掉 + 数值是自造的。

### 验收（`.smoke/verify_expand_fx.py`，5/5）

`.smoke/expand_fx_fixcheck.json`：

- **A1** 收起→▾ 只触发一次；页面内 8ms 自采样抓到 20 帧处于仪式态，
  `grain=gFlash/0.15s`、`chroma=cFlash/0.15s`，整段时长 176ms，全程 `pointer-events:none`。
- **A2** 峰值帧光效贡献：`delta_max 10`、`delta_mean 1.79`、`px_gt3 98433`，
  计算态 `chroma .65 / grain .04 / cFlash + gFlash`（`.smoke/fx_layer.json`，
  另存 `fx_layer/{base,peak,diff_x24}.png`）。
  ｜旧脚本的「均值≥12」是我按自造版本定的阈值，已作废；真值量法见下。
- **A3** 展开→收起不再触发仪式。
- **A4** 展开态把光标移到中央后 `ignoring=true`、窗口带 `WS_EX_TRANSPARENT`、
  中央像素的根祖先不是 HUD、左侧导航栏仍是 HUD（`WindowFromPoint` + `GetAncestor`，
  与系统投递点击同一套规则）。
- **A5** `--force-prefers-reduced-motion` 启动，`matchMedia` 真为 true，仪式 0 次。

### 测量方法上的三处修正（原脚本测的不是这件事）

1. **旧 A1 等 1 秒后才读 computed style**，那时类早被摘掉，必然读到 `none`——
   不是「动画没跑」，是取样时机错。
2. **屏幕像素法在亮背景下测不出**：`screen` 混色增量 ≈ `s·(1-b)`，
   底几乎白（实测 b≈.92）时只有 ~0.5/255。改为在页面内临时铺 `#02040a`
   （同源码 `--void`，层序在 `.fx` 之下）再截屏量差，量的是这一闪本身；
   测完立即移除，不改应用状态。
3. **CDP `Emulation.setEmulatedMedia` 在 WebView2 上返回成功但 `matchMedia` 不变**，
   A5 改用浏览器启动参数，并以 `matchMedia===true` 作为判定前提（否则这项不算通过）。

### 与源码的像素等价性（`.smoke/fx_ab.html`）

把「源码原样 CSS」与「移植后的 helmet.css 块」放进同一页、同一深色底、
同样把 150ms 动画钉在 40%（`-60ms` + `paused`），headless Edge 截图逐像素比对：
**99.94% 像素一致（排除左上角标签），最大差 2/255**（混色取整）。
即移植块与参考稿在峰值帧上等价，不是"我认为等价"。

### 遗留与边界

- 源值本身很轻：深色背景上全屏均值抬升约 1.8–3.4/255（与用户录屏同帧 3.42 同量级）；
  **浅色/白底应用之上几乎看不见**——这是源码的设计强度，不是实现缺陷。
  若要更明显，属于产品决定（需要主人点头），不能由我改数。
- 仍只在单屏 2560×1528 @150% 上验；多屏、分数 DPI、任务栏避让未验。

## v14 舞台模型：不缩窗、对话置顶（回应「灰方块 / 一直闪 / 不丝滑 / AI 不在顶层」）

### 一、灰色方块与阴影硬边：根因是缩窗，不是样式

v13 之前，idle 时把窗口缩成「岛的外包矩形 + 少量留边」（实测 294×64 CSS），
贴顶时再缩到 10px 唇边条。截屏取证（`.smoke/eye_idle.png`）显示：
以岛为中心有一块**与窗口等宽的浅灰矩形**，底边是**一条笔直硬线**，岛的 32px 阴影在此断掉。

排除法定位：页面里 `html/body/#app` 全透明、`.fx` 为 `opacity:0/visibility:hidden`、
`elementFromPoint` 在灰区取到的都是透明元素；把 `documentElement` 整体隐藏后灰区随之消失——
说明灰是**窗口层**画的。WebView2 在窗口 resize 后会重建合成面，重绘瞬间把窗口底色铺出来，
而窗口又只有岛那么大，于是「灰板 + 阴影被窗口边裁断」同时出现。

修法照参照稿（`reality-raid-hud-*` 是 100vw×100vh 舞台，从不动窗口）：
**窗口常驻工作区，一次不缩**；`docked`（贴顶）只用 `.island-wrap` 的 transform 把岛滑到屏幕上沿；
穿透交给已有的光标轮询（`.hit` 命中 → 关穿透，否则保持穿透）。
`applyBand/applyLip` 从「改窗口矩形」降级为「只切状态」，`applyRect/bandRect/lipRect/PAD_*/LIP_*/HOT_*` 全部删除。

顺带修掉两处「停了轮询就等于全屏挡桌面」的旧逻辑（`collapseNow`、`tickDock` 收起分支）：
满窗之后轮询必须常开，否则整块屏幕抢点击。

### 二、一直闪 / 不丝滑：尺寸抖动没了，曲线本来就顺

缩窗时代每次展开/收起是一次 294×64 ↔ 2560×1528 的 resize，合成面重建那一两帧就是「闪」。
窗口不动之后，动效只剩 CSS，逐帧采样（页面内 8ms，`.smoke/verify_expand_motion.json`）：

| 指标 | 实测 |
| --- | --- |
| `.hud` opacity | 0 → 1，**中间态 10 帧**，锯齿 **0** |
| `.dock` translateX | 0 → 14px，**中间态 12 帧**，锯齿 **0** |
| `.island` 位置 | 全程 `(720, 12)`，**一位没动** |

即：淡入与左滑都是逐级推进，没有「上去又掉回来」的来回，岛也没有跳位。
贴顶/唤出的时长也对齐参照稿 token：`--t-island 280ms`、`--t-collapse 150ms`。

### 三、AI 对话放到所有功能之上

- 左轨删掉 `data-nav="chat"`（原 03 项），导航现在是 6 项：待办/笔记/剪贴板/启动/搜索/设置。
- 点岛主体进对话舱（`mode=chat`），舱在 `.island-wrap`（z-index **60**）里，左轨与面板在 `.hud`（**40**）——
  对话天然压在 HUD 之上。
- 舱里新增**功能直达条**（`.fn-bar`）：待办 / 笔记 / 剪贴板 / 启动 / 搜索 / 设置 六个键，
  点一下即切到对应面板（`@open-panel` → `openPanel`，`mode` 自动落到 deck，舱随之收起）。
  搜索不是面板，走 `focusSearch()` 把底栏搜索框叫到焦点；原先「调一次 focus 就宣布成功」
  会被随后的卸载抢走焦点，改成重试若干帧直到真的拿到。

### 四、验收（`.smoke/verify_stage.py`，4/4 + 6/6）

| 项 | 判据 | 结果 |
| --- | --- | --- |
| S1 窗口不伸缩 | idle / band / docked / deck / chat 五态窗口矩形相同 | ✅ 全为 `2560×1528 @ (0,0)` |
| S2 岛右侧无硬切 | 岛右缘外 2→90px 逐像素，>12/255 的跳变数 | ✅ 0（旧模型下必然在窗口边跳一次） |
| S3 阴影自然淡出 | 该剖面回到桌面底色 | ✅ 212→226→237→243→246→247→248 单调收敛 |
| S4 对话在顶层 | 岛点开 mode=chat、z(岛) > z(hud)、六个功能键逐个真到 | ✅ z 60>40，6/6 面板命中 |

`.smoke/verify_expand_motion.py`：`ok=true`（见上表）。

### 五、测量上的坑（复用脚本时必须知道）

- 窗口矩形来自 Tauri，单位是 **DIP**；`SetCursorPos` / 截屏要的是**物理像素**，
  两者差一个 `monitor_width / innerWidth`（本机 1.5）。按 DIP 去点，落点在岛左侧约 480px 外，
  会得到「点了没反应」的假结论。判定命中要乘 `k`，截屏裁切也要乘 `k`。
- 240ms 的动画不要用截屏连拍量：一次 `mss.grab` 约 100ms 以上，抓到的第一帧就已经是终态。
  用页面内 8ms 自采样读 `getComputedStyle`。

## v22 十二个域接完后的待复验清单

功能面（速达 / 待办 / 笔记 / 剪贴板 / 搜索 / 便签 / 倒计时 / 提示词 / 系统设置 /
智能体审批 / 截图录屏 / 速达浏览器 / 待办·提示词浮窗）已逐个接完，逐个都按「改库并读回」
或「窗口枚举」验过。下面三项是**本轮没验成**的，别当成已完成：

1. **待办浮窗 / 提示词浮窗的渲染层**。只做到窗口级：调 `toggle_todo_float` 后能枚举到
   320×440 可见窗、内含 WebView2 子窗，再调一次即销毁。像素与 DOM 没验。
2. **截图框选后的「确认截图 / 钉住」**。唤起与 Esc 复位验过；往选区层窗口注入指针事件
   没能触发它的 pointerdown，那一步仍是原组件自身逻辑，未在本轮点过。
3. **自动收起后能否靠鼠标唤回**。当作缺陷线索记着，但**没有定论**：当时
   `mss`/`ImageGrab` 全部 BitBlt 失败、`helmet_cursor_local` 返回 null，事后无 x-hub
   进程时也照样失败 —— 那是**桌面会话被锁**的特征，不是应用行为。等屏幕亮着时按
   「收起 → 鼠标移到屏幕顶边 → 岛应滑出」复验；若那时 `helmet_cursor_local` 仍返回
   null，才是真缺陷。

回归：`verify_v11.py`（9/9）、`verify_stage.py`（4/4 + chips 6/6）、`verify_v12.py`（6/6）
都要在屏幕可用的会话里重跑一遍，确认这十二轮没碰坏岛/展开/对话。
