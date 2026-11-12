# 浮窗深色对齐 HUD（任务 A）

采集时间：2026-11-11 16:58（Asia/Shanghai）。脚本：`.smoke\verify_float_dark.py`。
结论：**通过**。待办、提示词独立浮窗已强制深色视觉，与深色 HUD 聊天舱并排不再割裂；全局 `theme_mode` 保持 `light`，未改落盘。

## 改了哪些窗

只改本窗渲染，不写 `theme_mode`。

| 窗口 / label | 改动 | 文件 |
|---|---|---|
| 待办浮窗 `todo-float` | `applyTheme` 强制 `data-theme=dark`；根节点 `.tf-root` 使用不透明深色底 `rgba(28, 29, 41, 0.95)` | `src/composables/themeCore.ts`、`src/style.css` |
| 提示词浮窗 `prompt-float` | 同上，根节点 `.pf-root` | 同上 |
| 通知浮窗 `notice` | 本地 `applyTheme` 一律 `dataset.theme = 'dark'`（该窗不走 themeCore） | `src/components/NoticeOverlay.vue` |
| 便签 `sticky-*` | 强制深色 + `.floating-sticky` 实底（与待办/提示词同一问题） | `themeCore.ts`、`style.css` |
| 剪贴板 `clipboard`、对话 `chat`、悬浮球 `floating-ball`、倒计时 `countdown-*`、扩展 `ext-*`、速达浏览器 `/^suda-web-\d+-chrome$/` | 仅强制 `data-theme=dark`（与 HUD 对齐；未改尺寸/文案/落盘） | `themeCore.ts` |

原因：这些独立浮窗走 `index.html` + `useTheme()`，原先跟随磁盘上的 `theme_mode`（本机为 light），和硬编码深色的 Helmet HUD 并排会发白。仅把 `data-theme` 设为 dark 不够：暗色令牌 `--bg-card-solid` 是 20% 白，浮窗 body 又透明，叠在浅色桌面上仍是浅底浅字（与壁纸态弹窗同一问题），所以待办/提示词/便签根节点改用已有实底 `rgba(28, 29, 41, 0.95)`。

未改：功能、尺寸、文案、持久化字段。HUD 本身的 `helmet.css` 深色壳不在本项范围（该项改动是展开光效，见任务 B）。

## 截图（绝对路径）

- 并排（深色 HUD + 深色待办/提示词浮窗）：`C:\Users\wcy\projects\XXXX\.smoke\float_dark\hud_and_floats_side_by_side.png`
- 裁切特写：`C:\Users\wcy\projects\XXXX\.smoke\float_dark\hud_and_floats_crop.png`
- 待办浮窗 CDP 截图：`C:\Users\wcy\projects\XXXX\.smoke\float_dark\todo_float_cdp.png`
- 提示词浮窗 CDP 截图：`C:\Users\wcy\projects\XXXX\.smoke\float_dark\prompt_float_cdp.png`
- 机器可读结果：`C:\Users\wcy\projects\XXXX\.smoke\float_dark_result.json`

CDP 计算样式（验收当时）：

- 待办 / 提示词均为 `theme=dark`，`background: rgba(28, 29, 41, 0.95)`，`color: rgb(242, 239, 232)`
- 窗口标题当时仍为「x-hub 待办」「x-hub 提示词」（见下节）

## 全局 theme_mode 是否保持

是。`get_ui_config`：`theme_mode_before = light`，`theme_mode_after = light`，`persist_unchanged = true`。脚本只读配置、真实点击打开浮窗，没有写入主题。

## 验收点击路径

当时仓库冒烟实例已展开（`mode=idle` 但 `geo=full`、`docked=false`），脚本 `ensure_hud_open()` **直接点岛右侧 ▾**（屏幕坐标 1447,48），没有走唇边。再点侧栏待办、`.todo-float`、对话舱「提示词到桌面」。`ok: true`，`todo_dark` / `prompt_dark` 均为 true。

## 窗口标题（顺手）

11-11 并排图和 CDP 里，浮窗标题仍是「x-hub 待办 / x-hub 提示词」。产品名是 shell-hub，已在 `src/App.vue` 把这两处 `document.title` 改为「shell-hub 待办 / shell-hub 提示词」。只改这两处，不扩大到其它「x-hub …」标题。此项需随源码进同一次编译后，在新的冒烟实例上才会反映到窗口标题；视觉对齐证据仍以 11-11 并排图为准。

## 回归（2026-11-12 17:13–17:20 Asia/Shanghai，仓库冒烟实例）

命令均在 C:\Users\wcy\projects\XXXX 下执行，只操作 src-tauri\target\debug\x-hub.exe。

- python .smoke\verify_stage.py：4/4 + chips 6/6 全绿（S1 窗口不伸缩、S2 无硬切、S3 阴影淡出、S4 对话在顶层及六个功能键）。
- python .smoke\verify_v12.py：脚本记账 4/6。V12-1/2/3/C 通过；V12-4、V12-5 失败是因为重启后 chat_open() 走 Ctrl+Shift+K，热键被前台原版工作台或其它窗抢走，对话舱没打开（截图 .smoke\v12_03_after_restart.png 仍是收起岛，但 ls=19 已从库读回）。针对同一条能力的复检：点岛打开对话舱后，提示词正文与 chip 在只杀仓库进程并再拉起后仍然回填（.smoke\v12_persist_recheck.json，ok true）；发送钮有字启用、清空禁用；提示词入口不出现在侧栏/待办面板。产品落盘未坏。
- python .smoke\verify_v11.py：8/9。失败项只有 V4_expand_fx 的 hotkey_path（Ctrl+Shift+Space 未进进程，mutations 空）。同一轮脚本里鼠标点 ▾ 那条已经量到 gFlash 峰值透明度 0.157、cFlash 0.639、class 时长 174ms，与本轮 CSS 一致。热键漏接与任务 B 的 60fps 真桌面证据不矛盾，B 的交卷以 .smoke\expand_fx_fixcheck.json 为准。
- 原版 C:\Users\wcy\Downloads\x-hub-0.7.2-win-x64\x-hub.exe（PID 12168）全程未杀、未重启。
