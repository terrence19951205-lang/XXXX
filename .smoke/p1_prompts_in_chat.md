# P1 · 提示词嵌进聊天（验收）

日期：2026-11-12 17:45 Asia/Shanghai。
仓库冒烟实例：C:\Users\wcy\projects\XXXX\src-tauri\target\debug\x-hub.exe。只杀/再拉仓库 target 下的进程。原版 C:\Users\wcy\Downloads\x-hub-0.7.2-win-x64\x-hub.exe（PID 12168）全程未动。
验收脚本：.smoke\verify_p1_prompts.py。机器可读结果：.smoke\p1_prompts_result.json（5/5 全绿）。重启后补拍：.smoke\p1_persist_reshoot.json。

结论：**通过**。提示词在对话舱内选用 / 切换，选中态清楚，杀掉仓库进程再拉起后仍在；没有新的侧栏「百宝箱」入口。不走独立浮窗也能选。未扩到待办厚度（子待办 / 周期 / 日历不在本项）。

舱内能力本身在 11-10 已接上（HelmetChatCabin 的提示词条 + PromptManageDialog）。本轮按批准裁切做了可见文案收敛，并补齐真点验收。

## 验收项（真点，5/5）

1. P1-1 对话舱里能看到并选用已有提示词
   - 做法：岛若贴顶先 reveal；已展开或 idle 则点岛打开对话舱（不用热键，避免原版抢快捷键）。点舱内「提示词」按钮，弹出列表，不经独立浮窗。
   - 结果：通过。舱在，按钮文案「提示词 2」，列表出现「【P1】会议纪要」「【P1】摘要提炼」。
   - 截图：C:\Users\wcy\projects\XXXX\.smoke\p1_prompts\01_list_in_chat.png

2. P1-2 选用一条，选中态清楚
   - 做法：真点列表第一条。
   - 结果：通过。输入框回填摘要正文；条上出现 chip「【P1】摘要提炼 ×」；再打开列表，该条高亮且带「✓ 已选用」。
   - 截图：C:\Users\wcy\projects\XXXX\.smoke\p1_prompts\02_selected_a.png 与 02b_selected_mark.png

3. P1-3 切换不同提示词
   - 做法：真点第二条。
   - 结果：通过。chip 换成「【P1】会议纪要 ×」，输入框换成会议纪要正文；只有第二条「✓ 已选用」，第一条不再标记。
   - 截图：C:\Users\wcy\projects\XXXX\.smoke\p1_prompts\03_switched_b.png 与 03b_switch_mark.png

4. P1-4 杀掉仓库进程再拉起，选中仍在
   - 做法：pid_of 只杀 target 下实例，再拉同一 exe；等 CDP 连上 helmet.html 后点岛打开对话舱（不用 Ctrl+Shift+K）。
   - 结果：通过。chip、输入框正文、localStorage 键 rr.hud.chatPromptId 仍是会议纪要。第一次桌面补拍正赶上桌面 ASCII 墙挡住舱，故用重启复拍。复拍的桌面图与 CDP 截图都看得见 chip + 正文。
   - 截图：C:\Users\wcy\projects\XXXX\.smoke\p1_prompts\04_before_restart.png 、 04_after_restart.png 、 04_after_restart_cdp.png

5. P1-5 不出现新的侧栏百宝箱入口
   - 做法：读左轨 data-nav，并在对话舱功能条里目视。
   - 结果：通过。侧栏仍是：待办 / 笔记 / 剪贴板 / 便签 / 倒计时 / 启动 / 搜索 / 设置。无 prompt / 百宝箱 / 提示词 导航。提示词只在舱内「提示词」按钮这一处入口（可浮到桌面，但不是侧栏新项）。
   - 截图：C:\Users\wcy\projects\XXXX\.smoke\p1_prompts\01_list_in_chat.png 与 05_chat_cabin_cdp.png

临时【P1】测试条已在脚本结束时从库里删掉，不留痕。

## 同路 UI 小修

### 1. 可见窗口标题：x-hub 改成 shell-hub

只改本仓库，不动 Downloads 原版包。原生窗口标题大多本来就没有 x-hub 前缀（待办、提示词、通知等）；漏网的是 document.title（任务管理器 WebView2 列表 / CDP 页标题）和个别 HTML / 导出窗。

- C:\Users\wcy\projects\XXXX\src\App.vue：x-hub 主窗 / 对话 / 剪贴板 / 扩展 / 便签 / 倒计时 / 截图选区 / 录制 / 贴图 → 一律 shell-hub …（待办、提示词上轮已改）
- C:\Users\wcy\projects\XXXX\helmet.html：x-hub Helmet → shell-hub
- C:\Users\wcy\projects\XXXX\index.html：x-hub 个人效率工作台 → shell-hub 主窗（源码已改。本轮编进包的运行时标题由 App.vue 写成 shell-hub 主窗，CDP 已是这个值。把 index 初始 title 与主窗对齐，避免和 HUD 精确标题 shell-hub 抢 CDP）
- C:\Users\wcy\projects\XXXX\chat.html：x-hub 对话 → shell-hub 对话
- C:\Users\wcy\projects\XXXX\clipboard.html：x-hub 剪贴板 → shell-hub 剪贴板
- C:\Users\wcy\projects\XXXX\notice.html：x-hub 通知 → shell-hub 通知
- C:\Users\wcy\projects\XXXX\ball.html：x-hub 悬浮球 → shell-hub 悬浮球
- C:\Users\wcy\projects\XXXX\chrome.html：x-hub 浏览器 → shell-hub 浏览器
- C:\Users\wcy\projects\XXXX\pin.html：x-hub 贴图 → shell-hub 贴图
- C:\Users\wcy\projects\XXXX\recorder.html：x-hub 截图 / 录屏 → shell-hub 截图 / 录屏
- C:\Users\wcy\projects\XXXX\export.html 与 src-tauri\src\export_render.rs：x-hub 导出 → shell-hub 导出
- C:\Users\wcy\projects\XXXX\src-tauri\src\helmet_window.rs：Helmet → shell-hub（原生 HUD 标题，避免 Alt+Tab 仍写内部名）

改后 CDP 页标题实测为：shell-hub、shell-hub 主窗、shell-hub 对话、shell-hub 剪贴板、shell-hub 通知、shell-hub 导出、shell-hub 浏览器、shell-hub 贴图、shell-hub 截图 / 录屏。验收结果里 xhub_titles 为空数组。

未改（不是窗口标题、也不是壳面上的残留）：二进制名 / identifier 仍是 x-hub；「x-hub 平台」是平台额度入口名；设置里「使用 x-hub 平台额度」同理。Downloads 原版包未动。

### 2. 对话舱提示词文案

- 「提示词」按钮 title：从提示词百宝箱选用 → 选用提示词
- 空库提示：在主窗「提示词百宝箱」里加条目后，这里就能直接选用 → 点下方「管理提示词」即可新增，然后在这里选用

舱内已有「管理提示词」，再指向「主窗百宝箱」会把人带出壳。侧栏不加百宝箱入口。

### 3. 验收脚本跟上新标题

HUD 页标题不再含 Helmet，verify_v10.connect_ws / helmet_hwnd 和 launch_smoke.py 改为认 helmet.html，或精确标题 shell-hub / 旧名 Helmet。否则会连不上对话舱，或误连初始 title 相同的主窗。这是标题改动顺手修的测试基础设施，不是产品功能。

### 4. 看过但未再改的

对话舱提示词条对比、chip、「✓ 已选用」在截图里已经清楚，间距正常，没有另改 CSS。截图确认键脚本点不到、展开光效、浮球 / Bento / 小游戏按要求不动。

## 编译与回归

只编了一次：npx tauri build --debug --no-bundle --config .smoke/tauri.smoke.json（日志 .smoke\build-p1-prompts.log），随后 rcedit 打 .smoke\app.manifest。编译前只杀仓库 target 实例，12168 仍在。

相关回归即上面 5 条真点，全绿。未再跑 verify_v11 / v12：本轮改了 HUD 标题匹配，这两套脚本里仍有多处写死 Helmet 的旧探测，热键也仍会被前台原版包抢走（已知冲突，不为此杀原版）。P1 验收一律点岛，不用热键。