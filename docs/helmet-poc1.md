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

## 本地验证（本轮可不跑 Win）

1. 确认分支：`git checkout feat/helmet-shell && git merge-base --is-ancestor v0.9.7 HEAD`
2. 常规前端依赖就绪后：`npm run tauri dev`（或项目惯用脚本）
3. 主窗控制台：`await invoke('helmet_show')`
4. 验收：
   - 默认收起，仅右上唤起条
   - 点条 / Esc 展开；中央区域鼠标应落到下层窗口
   - 移到上/左/下灰盒可点；移出后恢复穿透
   - 再收起后只留唤起条
5. `cargo check`（在 `src-tauri/`）应通过（需 Rust toolchain）

## 已知限制

- **单窗动态穿透**：穿透开启后 WebView 收不到 `pointerenter`；POC 用系统光标轮询兜底。Windows 实机仍需验证 DPI / 多屏 / 任务栏避让下的命中精度与切换延迟。
- `helmet_cursor_local` 目前仅 Windows 实现；其它平台返回 `null`，依赖 `mouseenter`/`mouseleave` 兜底（穿透开时同样可能失效）。
- 未接托盘 / 快捷键 / 主窗入口；未改仪表盘路由。
- HUD 为占位灰盒，非像素级还原 `reality-raid-hud-v05.html`。
- 未跑本机 Hermes / Win 冒烟（按授权硬限制）。

## 关键文件

- `src-tauri/src/helmet_window.rs`
- `src-tauri/src/lib.rs`（mod / init / commands）
- `src-tauri/capabilities/default.json`（`helmet` + ignore-cursor 权限）
- `helmet.html` / `src/light/helmet.ts` / `src/components/HelmetShell.vue`
- `vite.config.ts`（多页入口 `helmet`）
- `docs/helmet-poc1.md`
