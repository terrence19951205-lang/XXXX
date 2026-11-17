# shell-hub · 视觉方向 v1 · 全面落地交接

**状态：用户已过目通过（「没啥改的了就这样吧」）→ 请按此全面落地**  
**产品名：shell-hub**（禁止「头盔工作台」/ REALITY RAID 作产品名）  
**来源：Prototype Builder → Hermes开发**  
**日期：2026-11-06（Asia/Shanghai）**

---

## 定稿主包（照抄视觉）

| 用途 | 路径 |
|------|------|
| 可点 HTML 定稿（方向稿，交互与材质以此为准） | `/workspace/shell-hub-visual-direction-v1.html` |
| 素材 / token / 冻结约束说明 | `/workspace/shell-hub-visual-direction-v1-ASSETS.md` |
| 截图目录（1440×810） | `/workspace/shell-hub-visual-direction-v1-shots/` |
| 岛收起 | `…/01-island-compact.png` |
| 岛对话舱 | `…/02-island-chat.png` |
| 笔记列表 | `…/03-notes-list.png` |
| 笔记编辑 | `…/04-notes-editor.png` |
| 桌面穿透底图 | `/workspace/reality-raid-desk-bg.jpg` |
| 应用图标 | `/workspace/shell-hub-icons/`（32/48/128/256/1024 + svg） |

预览（本机 box）：`http://127.0.0.1:8765/shell-hub-visual-direction-v1.html`  
深链：`?state=island|chat|rail|list|editor`

---

## 相关基线（只读参考，勿回退方向稿已统一的材质）

| 文件 | 角色 |
|------|------|
| `/workspace/reality-raid-hud-v08-ascii-explore-v4.html` | HUD 视觉基线 v4（侧栏已去两端折线） |
| `/workspace/shell-hub-notes-3col-explore.html` | 三栏笔记探索（用户曾点头落地交互）；材质已对齐 glass-chat |
| `/workspace/shell-hub-notes-3col-OPACITY-PATCH.md` | 侧栏不透明度对齐岛对话框的 CSS 目标值 |

**落地以 visual-direction-v1 为准**；notes-3col / v4 仅作交互与历史对照。笔记三栏结构保留。

---

## 必须落地

1. **灵动岛 morph**：pill ↔ 对话舱（宽/高/圆角 22→26）；点岛开对话；Esc/收起关对话；岛右侧 ▾ 只管 HUD 壳（rail+下檐+面板）展收。
2. **材质统一**：岛收起+舱、rail、列表、编辑、下檐全部 `--glass-chat` 族；青边 `1px solid rgba(0,229,255,0.22)`；面板圆角 `12px`；blur ~18px。
3. **第一人称 HUD**：中央穿透桌面；克制青 + 琥珀微读数；淡 vignette / 轻扫描线可保留；**不要**满屏霓虹。
4. **笔记三栏**：rail → list → editor；无宠物；无 Bento；侧栏**无**两端折线 / L 瞄具。
5. **ASCII**：正式扩写仍暂停；仅允许岛/下檐级微点缀（与方向稿一致）。

### Token 目标值

```css
--glass: rgba(8, 12, 20, 0.96);
--glass-deep: rgba(6, 10, 18, 0.97);
--glass-chat: linear-gradient(180deg, rgba(28, 36, 48, 0.96) 0%, rgba(8, 12, 20, 0.97) 100%);
--cyan: #00e5ff;
--amber: #e8b84a;
/* 面板 */ border: 1px solid rgba(0,229,255,0.22); border-radius: 12px;
/* 岛 */ compact radius 22px → chat 26px; --island-chat-w: 420px;
```

---

## 不要做

- 宠物 / 伴游 / 吉祥物  
- Bento 布局  
- 侧栏两端折线或 L 形瞄具  
- 把产品叫「头盔工作台」  
- ASCII 墙 / 正式 ASCII 扩写  
- 另出 v5 折线方案（除非用户或大管家点名）  
- 覆盖探索 HTML 当源码仓唯一真相——工程应迁入本机 Hermes 工程；HTML 是视觉照抄源

---


---

## 增量 · HUD 展开全屏光效（2026-11-06 补回）

**确认：** 对照 v4 `applyCollapsed(..., withCeremony)` / `.fx.is-ceremony`，收起后再点岛右侧 ▾ 展开 HUD 时**应有**全屏光效。方向稿 v1 曾漏掉，已补回。

| 项 | 说明 |
|----|------|
| 触发 | HUD **已收起** → 点岛右侧 ▾ **再展开**（`setHudOpen(true)` 且此前为关） |
| 动效 | 全屏 grain（噪点 overlay）+ chroma（左右品红/青微渐变 screen）一闪；克制，非霓虹铺满 |
| 时长 | `--t-flash: 150ms`（动画结束后移除 `is-ceremony`） |
| 穿透 | `.fx` 始终 `pointer-events: none`，**不挡**中央 PASSTHROUGH 点击 |
| 减动效 | `prefers-reduced-motion: reduce` 时跳过闪光 |
| 源码 | `/workspace/shell-hub-visual-direction-v1.html`（`.fx .grain/.chroma` + `playExpandCeremony`） |
| 截图 | `/workspace/shell-hub-visual-direction-v1-shots/05-expand-ceremony.png`（`?state=ceremony` 峰值定格） |
| 深链 | `?state=ceremony` 供对照；实机交互不需此参 |

**落地：** 在壳 HUD 展收路径照抄上述触发与时长；勿改其它已定稿交互。

## 验收建议（对照截图）

- [ ] 岛收起态 ≈ `01-island-compact.png`  
- [ ] 岛对话舱 ≈ `02-island-chat.png`  
- [ ] 笔记列表 ≈ `03-notes-list.png`  
- [ ] 笔记编辑 ≈ `04-notes-editor.png`  
- [ ] 侧栏/面板不透明度与对话舱同级（约 96%–97%），非半透明雾感  
- [ ] 无折线瞄具、无宠物、无 Bento
- [ ] 收起→▾展开有 ~150ms 全屏光效，且不挡穿透（对照 `05-expand-ceremony.png`）  

有对不上的开发反馈再找 Prototype Builder；无反馈则探索侧收口，不再改方向稿。
