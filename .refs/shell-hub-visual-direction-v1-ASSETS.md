# shell-hub · visual direction v1 · 素材与范围

主文件：`/workspace/shell-hub-visual-direction-v1.html`  
状态：**用户已过目通过** → 全面落地以本包 + HANDOFF 为准（见 `shell-hub-visual-direction-v1-HANDOFF.md`）  
产品名：**shell-hub**（禁止「头盔工作台」）

## 基线（只读，未覆盖）

| 文件 | 角色 |
|------|------|
| `/workspace/shell-hub-notes-3col-explore.html` | 笔记三栏交互 / 深链结构 |
| `/workspace/reality-raid-hud-v08-ascii-explore-v4.html` | 岛 pill↔对话舱 morph、青边圆角 |
| `/workspace/shell-hub-notes-3col-OPACITY-PATCH.md` | 侧栏对齐 `--glass-chat` 的对照说明 |

## 视觉材料

| 素材 | 路径 / 值 | 用途 |
|------|-----------|------|
| 桌面穿透底图 | `./reality-raid-desk-bg.jpg`（`/workspace/reality-raid-desk-bg.jpg`） | PASSTHROUGH |
| 字体 | Google Fonts：Inter / Noto Sans SC / IBM Plex Mono / Oxanium | 层级与 HUD 微标 |
| `--glass` | `rgba(8, 12, 20, 0.96)` | 实心玻璃基色 |
| `--glass-deep` | `rgba(6, 10, 18, 0.97)` | 深玻璃（备用） |
| `--glass-chat` | `linear-gradient(180deg, rgba(28,36,48,0.96) → rgba(8,12,20,0.97))` | **统一材质**：岛收起+对话舱、rail、list、editor、eave |
| `--cyan` | `#00e5ff` | 细边 / 高光 |
| `--amber` | `#e8b84a` | 岛电量微读数（克制） |
| 面板边框 | `1px solid rgba(0,229,255,0.22)` · `border-radius: 12px` · blur ~18px | 列表面板 |
| 岛半径 | compact `22px` → chat `26px`；宽 `--island-w` → `--island-chat-w: 420px` | 岛 morph |
| ASCII 点缀 | 岛 `∷▮∷`、下檐 `┌─ DIR ─┐` | **仅暗示**，无 ASCII 墙 / 无正式扩写 |
| HUD 抛光 | 淡 vignette、~4% scanline、右上/右下 7px 角 tick | 方向气质；**非**侧栏两端折线 |
| 展开全屏光效 | `.fx.is-ceremony` grain+chroma · `--t-flash: 150ms` · `pointer-events:none` | 收起→▾展开触发；`?state=ceremony` 定格 |
| localStorage | `shellhub.visualdir.v1` | 与 notes explore 键隔离 |

## 方向 vs 冻结

**本方向稿强调（可改）：**

- 岛 compact ↔ 对话舱 morph（可点）
- 全表面 `--glass-chat` 材质统一
- 第一人称 HUD / 简洁科技 / 2077 氛围（克制青+琥珀）
- 笔记三栏保留；深链 `?state=island|chat|rail|list|editor|ceremony`

**已冻结 / 硬约束（勿回退）：**

- 无宠物 / 伴游 / 吉祥物
- 无 Bento 布局
- 无侧栏两端折线、无 L 形瞄具角
- 产品名始终 **shell-hub**
- ASCII 正式扩写暂停（本稿只暗示）
- 不覆盖 v4 / notes-3col 基线文件

## 预览与截图

服务：`python3 -m http.server 8765` @ `/workspace`  
预览：`http://127.0.0.1:8765/shell-hub-visual-direction-v1.html`  
截图目录：`/workspace/shell-hub-visual-direction-v1-shots/`
