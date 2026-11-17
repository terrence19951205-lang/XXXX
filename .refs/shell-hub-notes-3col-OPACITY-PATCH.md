# shell-hub · 侧栏/列表面板不透明度对齐聊天对话框

产品名：**shell-hub**。视觉：v4 青边 + 圆角细边，无两端折线。

## 用户反馈
侧边栏太透，要和对话框差不多不透明。

## 对照基准（聊天对话框 / 灵动岛展开态）
来自探索稿 v4 `.island`：

```css
background: linear-gradient(180deg, rgba(28,36,48,0.96) 0%, rgba(8,12,20,0.97) 100%);
/* ≈ 96%–97% 不透明 */
```

## 旧值（过透）
```css
--glass: rgba(5, 9, 16, 0.58); /* 58% */
.rail / .col-panel {
  background: linear-gradient(...), var(--glass);
}
```

## 新目标值（已写入 explore）
文件：`/workspace/shell-hub-notes-3col-explore.html`

```css
--glass: rgba(8, 12, 20, 0.96);
--glass-deep: rgba(6, 10, 18, 0.97);
--glass-chat: linear-gradient(180deg, rgba(28, 36, 48, 0.96) 0%, rgba(8, 12, 20, 0.97) 100%);

.rail,
.col-panel {
  background: var(--glass-chat);
  backdrop-filter: blur(18px) saturate(1.2);
  border: 1px solid rgba(0,229,255,0.22); /* 保持 v4 青边 */
  border-radius: 12px;
}
```

作用于：左功能侧栏 `.rail`、中栏列表与右栏编辑 `.col-panel`。

## 截图
见 `/workspace/shell-hub-notes-3col-shots/04-opacity-aligned-editor.png`（及 list 对照）。
