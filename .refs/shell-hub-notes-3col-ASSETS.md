# shell-hub 三栏笔记探索稿 · 素材清单

主文件：`/workspace/shell-hub-notes-3col-explore.html`  
状态：**探索稿，非最终定稿**  
视觉基线：`/workspace/reality-raid-hud-v08-ascii-explore-v4.html`（未改写）

## 用到的视觉 / ASCII 素材

| 素材 | 路径 / 来源 | 用途 |
|------|-------------|------|
| 桌面穿透底图 | `/workspace/reality-raid-desk-bg.jpg`（相对引用 `./reality-raid-desk-bg.jpg`） | 中央 PASSTHROUGH 示意 |
| 色板与字体 | 继承 v4 token：`--cyan #00e5ff`、IBM Plex Mono / Noto Sans SC / Oxanium / Inter（Google Fonts） | HUD 深色科技感 |
| 侧栏圆角细边 | 内联 CSS（对齐 v4 增量：去 SVG `edge` 切角、去两端 L 形瞄具） | 左栏 rail |
| ASCII 点缀（轻量内联） | 灵动岛 `∷▮∷`、下檐 `┌─ NOTES ─┐` | 壳层氛围，**未**捆绑 ascii-sharks / amart 全库 |
| amart / ascii-sharks | **未引用** | 本探索聚焦三栏交互，保持单文件可本地预览 |

## 未使用（刻意）

- 吉祥物 / 伴游类角色 UI
- 侧栏两端折线、`svg.edge` 八边形切角、L 形瞄具
- 文案「头盔工作台」
- 覆盖 v3/v4 基线文件

## 预览

若 `/workspace` 已有 `python3 -m http.server` 监听 **8765**：

`http://127.0.0.1:8765/shell-hub-notes-3col-explore.html`
