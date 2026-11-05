<script setup lang="ts">
/**
 * Helmet 座舱壳 POC-1
 * - 默认 collapsed；localStorage `rr.hud.collapsed` 记忆
 * - 收起只留 ≤48px 唤起条
 * - 展开：中央洞穿透；`.hit` 可点；装饰 `pointer-events:none`
 * - 无右栏；grain/色差默认关
 * - 动态穿透：穿透开时 WebView 收不到 pointer → 轮询 helmet_cursor_local
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import { isTauri } from '../api/tauri'

const LS_COLLAPSE = 'rr.hud.collapsed'

const collapsed = ref(true)
const ignoring = ref(false)
const ready = ref(false)

const rootEl = ref<HTMLElement | null>(null)

function readCollapsed(): boolean {
  try {
    const s = localStorage.getItem(LS_COLLAPSE)
    if (s === '0') return false
    if (s === '1') return true
  } catch {
    /* ignore */
  }
  return true
}

function persistCollapsed(v: boolean) {
  try {
    localStorage.setItem(LS_COLLAPSE, v ? '1' : '0')
  } catch {
    /* ignore */
  }
}

async function setIgnore(ignore: boolean) {
  if (!isTauri()) {
    ignoring.value = ignore
    return
  }
  if (ignoring.value === ignore) return
  try {
    await invoke('helmet_set_ignore_cursor_events', { ignore })
    ignoring.value = ignore
  } catch (e) {
    console.warn('[helmet] set_ignore_cursor_events failed', e)
  }
}

function setCollapsed(v: boolean) {
  collapsed.value = v
  persistCollapsed(v)
}

function toggleCollapsed() {
  setCollapsed(!collapsed.value)
}

const shellOpen = computed(() => !collapsed.value)

/** 命中检测：光标落在任一 `.hit` 的包围盒内 */
function cursorOverHit(lx: number, ly: number): boolean {
  const root = rootEl.value
  if (!root) return false
  const hits = root.querySelectorAll<HTMLElement>('.hit')
  for (const el of hits) {
    const r = el.getBoundingClientRect()
    if (lx >= r.left && lx <= r.right && ly >= r.top && ly <= r.bottom) {
      return true
    }
  }
  return false
}

let pollTimer: number | null = null
let unlisteners: UnlistenFn[] = []

async function pollCursor() {
  if (!isTauri() || collapsed.value) return
  try {
    const pos = await invoke<[number, number] | null>('helmet_cursor_local')
    if (!pos) {
      // 光标在窗外：保持穿透，不挡下层
      await setIgnore(true)
      return
    }
    const over = cursorOverHit(pos[0], pos[1])
    await setIgnore(!over)
  } catch {
    /* POC：命令不可用时静默 */
  }
}

function startPoll() {
  stopPoll()
  if (!isTauri()) return
  pollTimer = window.setInterval(() => {
    void pollCursor()
  }, 80)
}

function stopPoll() {
  if (pollTimer != null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

watch(collapsed, async (v) => {
  if (v) {
    stopPoll()
    // 收起态只留唤起条，必须可点
    await setIgnore(false)
  } else {
    // 展开：默认开穿透，轮询在 `.hit` 上临时关闭
    await setIgnore(true)
    startPoll()
  }
})

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.preventDefault()
    toggleCollapsed()
  }
}

onMounted(async () => {
  collapsed.value = readCollapsed()
  ready.value = true
  window.addEventListener('keydown', onKeydown)

  if (collapsed.value) {
    await setIgnore(false)
  } else {
    await setIgnore(true)
    startPoll()
  }

  if (isTauri()) {
    try {
      unlisteners.push(
        await listen('helmet-shown', () => {
          // 每次唤起按记忆恢复；无记忆则收起
          collapsed.value = readCollapsed()
          void (async () => {
            if (collapsed.value) {
              stopPoll()
              await setIgnore(false)
            } else {
              await setIgnore(true)
              startPoll()
            }
          })()
        }),
      )
      unlisteners.push(
        await listen('helmet-hidden', () => {
          stopPoll()
          ignoring.value = false
        }),
      )
    } catch (e) {
      console.warn('[helmet] listen failed', e)
    }
  }
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  stopPoll()
  for (const u of unlisteners) u()
  unlisteners = []
})

/** 非 Tauri / 轮询未就绪时的 DOM 兜底 */
function onHitEnter() {
  if (!collapsed.value) void setIgnore(false)
}
function onHitLeave() {
  if (!collapsed.value) void setIgnore(true)
}
</script>

<template>
  <div
    ref="rootEl"
    class="helmet-root"
    :class="{ collapsed: collapsed, open: shellOpen, ready }"
  >
    <!-- 唤起条：收起态唯一可交互面，≤48px -->
    <button
      type="button"
      class="invoke-bar hit"
      :class="{ 'is-open': shellOpen }"
      :aria-expanded="shellOpen"
      aria-label="切换 Helmet"
      @click="toggleCollapsed"
      @mouseenter="onHitEnter"
      @mouseleave="onHitLeave"
    >
      <span class="dot" aria-hidden="true" />
      <span class="label">{{ shellOpen ? '收起 Helmet' : '展开 Helmet' }}</span>
      <kbd>Esc</kbd>
    </button>

    <!-- 展开 HUD：中央洞无节点（穿透）；边缘灰盒占位 -->
    <div v-show="shellOpen" class="hud" aria-hidden="false">
      <header
        class="top cut-panel hit"
        aria-label="上檐占位"
        @mouseenter="onHitEnter"
        @mouseleave="onHitLeave"
      >
        <div class="ph-ring" />
        <div class="ph-comms">
          <div class="tag">COMMS · POC</div>
          <div class="msg">Helmet 壳就位 · 中央洞穿透</div>
        </div>
      </header>

      <aside
        class="left cut-panel hit"
        aria-label="左栏占位"
        @mouseenter="onHitEnter"
        @mouseleave="onHitLeave"
      >
        <div class="label-row">今日 · 占位</div>
        <div class="ph-block" />
        <div class="ph-block short" />
        <div class="ph-block" />
      </aside>

      <!-- 无右栏（验收约束） -->

      <footer
        class="bot cut-panel hit"
        aria-label="下檐占位"
        @mouseenter="onHitEnter"
        @mouseleave="onHitLeave"
      >
        <span class="ph-btn">校准</span>
        <span class="ph-btn primary">完成聚焦</span>
        <span class="ph-btn ghost">收起</span>
      </footer>
    </div>

    <!-- 装饰/fx：pointer-events:none；grain/色差默认关（不渲染） -->
    <div v-show="shellOpen" class="fx" aria-hidden="true">
      <div class="vignette" />
      <div class="corners">
        <i class="c tl" /><i class="c tr" /><i class="c bl" /><i class="c br" />
      </div>
    </div>

    <div v-if="isTauri()" class="dbg" aria-hidden="true">
      {{ ignoring ? 'PASS' : 'HIT' }} · {{ collapsed ? 'collapsed' : 'open' }}
    </div>
  </div>
</template>

<style scoped>
/* tokens 只读复制自 reality-raid-hud-v05.html */
:global(html),
:global(body) {
  margin: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: transparent !important;
  user-select: none;
}
:global(#app) {
  width: 100%;
  height: 100%;
  background: transparent;
}

.helmet-root {
  --bg-glass: rgba(7, 12, 20, 0.78);
  --cyan: #00e5ff;
  --magenta: #ff2e97;
  --amber: #e8b84a;
  --text-1: #eef4fa;
  --text-2: #b7c5d4;
  --text-3: #8a9bb0;
  --text-4: #5c6b7a;
  --edge: rgba(0, 229, 255, 0.28);
  --rail-w: 236px;
  --eave-top: 70px;
  --eave-bot: 60px;
  --inset: 12px;
  --cut: 8px;
  --ease: cubic-bezier(0.22, 1, 0.36, 1);
  --t-flash: 160ms;
  --t-hover: 100ms;
  --t-panel: 220ms;
  --mono: 'IBM Plex Mono', ui-monospace, monospace;
  --sans: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif;

  position: relative;
  width: 100%;
  height: 100%;
  font-family: var(--sans);
  color: var(--text-1);
  /* 根不接事件：中央洞天然穿透到 WebView 透明像素；控件靠 .hit */
  pointer-events: none;
  opacity: 0;
  transition: opacity var(--t-flash) var(--ease);
}
.helmet-root.ready {
  opacity: 1;
}
.helmet-root .hit {
  pointer-events: auto;
}

/* 唤起条 ≤48px */
.invoke-bar {
  position: absolute;
  top: var(--inset);
  right: 14px;
  z-index: 50;
  height: 36px;
  max-height: 48px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--cyan);
  background: linear-gradient(180deg, rgba(18, 28, 40, 0.96), rgba(6, 10, 16, 0.94));
  border: 1px solid rgba(0, 229, 255, 0.34);
  padding: 0 14px 0 12px;
  cursor: pointer;
  clip-path: polygon(
    6px 0,
    calc(100% - 6px) 0,
    100% 6px,
    100% calc(100% - 6px),
    calc(100% - 6px) 100%,
    6px 100%,
    0 calc(100% - 6px),
    0 6px
  );
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.07),
    0 4px 14px rgba(0, 0, 0, 0.4);
  transition:
    border-color var(--t-hover),
    box-shadow var(--t-hover),
    color var(--t-hover);
}
.invoke-bar:hover {
  border-color: var(--cyan);
  color: #fff;
  box-shadow: 0 0 18px rgba(0, 229, 255, 0.2);
}
.invoke-bar .dot {
  width: 7px;
  height: 7px;
  background: rgba(0, 229, 255, 0.3);
  box-shadow: 0 0 0 1px rgba(0, 229, 255, 0.25);
}
.invoke-bar.is-open .dot {
  background: var(--cyan);
  box-shadow: 0 0 10px rgba(0, 229, 255, 0.85);
}
.invoke-bar kbd {
  font-family: var(--mono);
  font-size: 10px;
  padding: 1px 5px;
  border: 1px solid rgba(0, 229, 255, 0.25);
  color: var(--text-3);
  background: rgba(0, 0, 0, 0.25);
}

.cut-panel {
  position: relative;
  background: var(--bg-glass);
  backdrop-filter: blur(18px) saturate(1.25);
  -webkit-backdrop-filter: blur(18px) saturate(1.25);
  clip-path: polygon(
    var(--cut) 0%,
    calc(100% - var(--cut)) 0%,
    100% var(--cut),
    100% calc(100% - var(--cut)),
    calc(100% - var(--cut)) 100%,
    var(--cut) 100%,
    0% calc(100% - var(--cut)),
    0% var(--cut)
  );
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.05),
    0 12px 40px rgba(0, 0, 0, 0.42);
  border: 1px solid var(--edge);
}

.hud {
  position: absolute;
  inset: 0;
  z-index: 10;
  pointer-events: none;
}
.hud > .hit {
  pointer-events: auto;
}

.top {
  position: absolute;
  top: var(--inset);
  left: 50%;
  transform: translateX(-50%);
  width: min(760px, calc(100% - 52px));
  height: var(--eave-top);
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 14px;
  align-items: center;
  padding: 8px 18px;
  animation: slideDown var(--t-panel) var(--ease) both;
}
.ph-ring {
  width: 48px;
  height: 48px;
  margin: 0 auto;
  border-radius: 50%;
  border: 3px solid rgba(232, 184, 74, 0.35);
  box-shadow: inset 0 0 0 6px rgba(0, 0, 0, 0.25);
  background: conic-gradient(var(--amber) 0 72%, rgba(0, 229, 255, 0.08) 0);
  opacity: 0.85;
}
.ph-comms .tag {
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.16em;
  color: var(--magenta);
}
.ph-comms .msg {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.left {
  position: absolute;
  top: calc(var(--eave-top) + 22px);
  left: var(--inset);
  bottom: calc(var(--eave-bot) + 20px);
  width: var(--rail-w);
  padding: 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  animation: slideLeft var(--t-panel) var(--ease) both;
}
.label-row {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--cyan);
  margin-bottom: 4px;
}
.ph-block {
  height: 44px;
  background: rgba(0, 229, 255, 0.06);
  border: 1px solid rgba(0, 229, 255, 0.14);
  clip-path: polygon(5px 0, calc(100% - 5px) 0, 100% 5px, 100% calc(100% - 5px), calc(100% - 5px) 100%, 5px 100%, 0 calc(100% - 5px), 0 5px);
}
.ph-block.short {
  height: 32px;
  opacity: 0.7;
}

.bot {
  position: absolute;
  bottom: var(--inset);
  left: 50%;
  transform: translateX(-50%);
  width: min(400px, calc(100% - 48px));
  height: var(--eave-bot);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  animation: slideUp var(--t-panel) var(--ease) both;
}
.ph-btn {
  font-size: 13px;
  font-weight: 500;
  border: 1px solid var(--edge);
  background: rgba(0, 229, 255, 0.05);
  color: var(--text-1);
  padding: 9px 14px;
  clip-path: polygon(5px 0, calc(100% - 5px) 0, 100% 5px, 100% calc(100% - 5px), calc(100% - 5px) 100%, 5px 100%, 0 calc(100% - 5px), 0 5px);
}
.ph-btn.primary {
  background: linear-gradient(145deg, rgba(0, 229, 255, 0.28), rgba(0, 229, 255, 0.06));
  border-color: rgba(0, 229, 255, 0.55);
  font-weight: 600;
}
.ph-btn.ghost {
  background: transparent;
  border-color: rgba(122, 143, 163, 0.3);
  color: var(--text-3);
}

.fx {
  position: absolute;
  inset: 0;
  z-index: 8;
  pointer-events: none;
}
.vignette {
  position: absolute;
  inset: 0;
  box-shadow: inset 0 0 90px rgba(0, 0, 0, 0.35);
  pointer-events: none;
}
.corners {
  position: absolute;
  inset: 10px;
  pointer-events: none;
}
.c {
  position: absolute;
  width: 18px;
  height: 18px;
  border-color: rgba(0, 229, 255, 0.55);
  border-style: solid;
  border-width: 0;
  opacity: 0.85;
}
.c.tl {
  top: 0;
  left: 0;
  border-top-width: 1.5px;
  border-left-width: 1.5px;
}
.c.tr {
  top: 0;
  right: 0;
  border-top-width: 1.5px;
  border-right-width: 1.5px;
}
.c.bl {
  bottom: 0;
  left: 0;
  border-bottom-width: 1.5px;
  border-left-width: 1.5px;
}
.c.br {
  bottom: 0;
  right: 0;
  border-bottom-width: 1.5px;
  border-right-width: 1.5px;
}

.dbg {
  position: absolute;
  left: 12px;
  bottom: 8px;
  z-index: 60;
  pointer-events: none;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  color: rgba(0, 229, 255, 0.55);
  background: rgba(0, 0, 0, 0.35);
  padding: 2px 8px;
  clip-path: polygon(4px 0, calc(100% - 4px) 0, 100% 4px, 100% calc(100% - 4px), calc(100% - 4px) 100%, 4px 100%, 0 calc(100% - 4px), 0 4px);
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-12px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}
@keyframes slideLeft {
  from {
    opacity: 0;
    transform: translateX(-14px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}
</style>
