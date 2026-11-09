<script setup lang="ts">
/**
 * Helmet 座舱壳 v0.8 · 灵动岛
 *
 * 形态（PRD v0.4.1）：
 *  - idle：只留顶部居中小岛（shell-hub + 剩余工时%）与右上「展开」，
 *          窗口本身缩到这两个控件的外包矩形 → 中央与大部分桌面天然可点。
 *  - deck：短暂态；左侧序号轨 + 面板（待办/笔记/剪贴板/速达）+ 底栏搜索；
 *          无右栏；中央洞始终可点桌面。
 *  - chat：点小岛，完整对话舱挂在岛下（多会话/模型/消息线/输入框）。
 *
 * 穿透：非 idle 时窗口铺满工作区，默认整窗穿透，80ms 轮询
 * `helmet_cursor_local` 命中 `.hit` 才临时关穿透（Windows 单窗方案）。
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch, watchEffect } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import { getCurrentWindow } from '@tauri-apps/api/window'
import { PhysicalPosition, PhysicalSize } from '@tauri-apps/api/dpi'
import {
  PLATFORM_ENTRY_NAME,
  isPlatformModel,
  isTauri,
  tauriApi,
  type ChatModelConfig,
  type SearchResult,
} from '../api/tauri'
import HelmetChatCabin from './helmet/HelmetChatCabin.vue'
import HelmetTodoPanel from './helmet/HelmetTodoPanel.vue'
import HelmetNotesPanel from './helmet/HelmetNotesPanel.vue'
import HelmetNoteEditor from './helmet/HelmetNoteEditor.vue'
import HelmetClipboardPanel from './helmet/HelmetClipboardPanel.vue'
import HelmetLaunchPanel from './helmet/HelmetLaunchPanel.vue'
import HelmetBoot from './helmet/HelmetBoot.vue'
import { useHelmetNotes } from '../composables/useHelmetNotes'
import './helmet/helmet.css'

type Mode = 'idle' | 'deck' | 'chat'
type PanelKey = 'todos' | 'notes' | 'clipboard' | 'launch' | 'settings'

const LS_OLD_COLLAPSE = 'rr.hud.collapsed'
const LS_HOURS = 'rr.hud.hours'
/** 折叠记忆：贴顶收起（lip）落盘；杀进程重启后按上次折叠态回来 */
const LS_COLLAPSED = 'rr.hud.collapsed.v10'
const SS_BOOT = 'rr.hud.bootPlayed'
/** 满屏判定：收起的小窗只有几十 px 高，满屏工作区上千 px 高 */
const isFullWindow = () => document.documentElement.clientHeight > 300
/** 岛完整显示时的小窗 = 岛外包矩形 + 四周留边（阴影不被窗口裁掉） */
const PAD_L = 12
const PAD_R = 14
const PAD_Y = 12
/** 贴顶收起：只留 4px 唇边；顶部 10px 是唤出热区 */
const LIP_PX = 4
const HOT_PX = 10
const HOT_EXTRA = 160
/** 岛的最小可信宽度（量到比这个还小说明正处在裁切/切换瞬间，读数丢弃） */
const MIN_ISLAND_W = 180
/** 满屏基准的最小尺寸（CSS）：低于这个值说明量到的是小窗，不能当工作区基准 */
const FULL_MIN_CW = 640
const FULL_MIN_CH = 400
/** 移开鼠标后多久再贴顶 */
const HIDE_MS = 450
/** 岛滑出屏幕的动画时长（缩窗前要等它走完，否则动画被窗口裁掉） */
const DOCK_ANIM_MS = 280

/** 窗口几何：full=满屏工作区；band=岛完整显示；lip=贴顶只剩唇边+热区 */
type Geo = 'full' | 'band' | 'lip'
const geo = ref<Geo>('full')
/** 岛是否已贴顶收起（CSS 类名同步，动画由 CSS 负责） */
const docked = ref(false)
const hovering = ref(false)
/** 键盘 Tab 聚焦时钉住；鼠标点选不钉（否则点一次 ⚙ 就再也不收） */
const keyboardNav = ref(false)
const bootActive = ref(false)
const islandCss = ref({ w: 220, h: 40 })

/** 折叠记忆读写（localStorage 落在 WebView2 用户数据目录，进程重启仍在） */
function readCollapsed(): boolean {
  try {
    return localStorage.getItem(LS_COLLAPSED) === '1'
  } catch {
    return false
  }
}

function persistCollapsed(v: boolean) {
  try {
    localStorage.setItem(LS_COLLAPSED, v ? '1' : '0')
  } catch {
    /* ignore */
  }
}

const mode = ref<Mode>('idle')
const panel = ref<PanelKey>('todos')
const ready = ref(false)
const noAnim = ref(false)
const ignoring = ref<boolean | null>(null)
const hoursOpen = ref(false)
/**
 * 笔记三栏（中栏列表 + 右栏编辑）：状态在 useHelmetNotes 单例里，
 * 栏位显隐由它驱动；这里只把它当「笔记区开没开」的开关用。
 */
const noteStore = useHelmetNotes()
const noteListOpen = noteStore.listOpen
const noteEditorOpen = noteStore.editorOpen
const toastMsg = ref('')
const debugText = ref('')

const rootEl = ref<HTMLElement | null>(null)
const wrapEl = ref<HTMLElement | null>(null)
const islandEl = ref<HTMLElement | null>(null)

/** 调试角标只在 ?dbg=1 时出现，正常使用时界面上不留内部状态字样 */
const showDbg = typeof location !== 'undefined' && new URLSearchParams(location.search).has('dbg')
const chatOpen = computed(() => mode.value === 'chat')
const deckOpen = computed(() => mode.value === 'deck')

/* ------------------------------------------------------------------ */
/* 展开全屏仪式光效                                                     */
/* 与 morph / 材质同一路：HUD 收起态 → ▾（或快捷键）展开的那一下，       */
/* 全屏 grain + chroma 闪 150ms（方向稿 v1 .fx.is-ceremony 同规格）。    */
/* .fx 整层 pointer-events:none，永不挡中央 PASSTHROUGH 点击。           */
/* ------------------------------------------------------------------ */

const FLASH_MS = 150
const fxCeremony = ref(0)
/* 收起瞬间：源实现保留 .fx 150ms 播 cOut（四角先亮后收），再整体隐去 */
const fxCollapsing = ref(false)
/* 这两个必须走 Vue 绑定：class 属性由 :class 托管，classList.add 会被下一次 patch 抹掉
   （曾因此「展开了却看不到闪」——不是数值问题，是类被重渲染清掉） */
const fxCeremonyOn = ref(false)
const fxFlashoutOn = ref(false)
let fxTimer: number | null = null
let fxOutTimer: number | null = null

const reducedFx = () =>
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

function playExpandCeremony() {
  if (fxOutTimer != null) {
    window.clearTimeout(fxOutTimer)
    fxOutTimer = null
  }
  fxCollapsing.value = false
  fxFlashoutOn.value = false
  if (reducedFx()) return
  if (fxTimer != null) window.clearTimeout(fxTimer)
  fxCeremonyOn.value = false
  nextTick(() => {
    fxCeremonyOn.value = true
    fxCeremony.value += 1
    fxTimer = window.setTimeout(() => {
      fxCeremonyOn.value = false
      fxTimer = null
    }, FLASH_MS + 20)
  })
}

/* 开→关：不重放 grain/chroma，只让取景框 cOut 收走（同源 .fx.is-flashout） */
function playCollapseOut() {
  if (fxTimer != null) {
    window.clearTimeout(fxTimer)
    fxTimer = null
  }
  fxCeremonyOn.value = false
  if (reducedFx()) {
    fxFlashoutOn.value = false
    return
  }
  fxFlashoutOn.value = false
  nextTick(() => {
    fxFlashoutOn.value = true
    fxCollapsing.value = true
    if (fxOutTimer != null) window.clearTimeout(fxOutTimer)
    fxOutTimer = window.setTimeout(() => {
      fxFlashoutOn.value = false
      fxCollapsing.value = false
      fxOutTimer = null
    }, FLASH_MS)
  })
}

watch(
  deckOpen,
  (open, was) => {
    if (open && !was) playExpandCeremony()
    else if (!open && was) playCollapseOut()
  },
  { flush: 'pre' }
)

/* ------------------------------------------------------------------ */
/* 窗口矩形                                                            */
/* ------------------------------------------------------------------ */

type Rect = { x: number; y: number; w: number; h: number }
/** 满屏时的窗口基准（物理 px + 缩放 + CSS 视口），之后所有几何换算都按它算 */
type Frame = Rect & { scale: number; cw: number; ch: number }
let frameRect: Frame | null = null

async function setIgnore(ignore: boolean) {
  if (ignoring.value === ignore) return
  if (!isTauri()) {
    ignoring.value = ignore
    return
  }
  try {
    await invoke('helmet_set_ignore_cursor_events', { ignore })
    ignoring.value = ignore
  } catch (e) {
    console.warn('[helmet] set_ignore_cursor_events failed', e)
  }
}

/** 量岛尺寸（CSS px）——对话舱展开时岛是 420×520，不能拿来算小窗 */
function measureIsland() {
  const el = islandEl.value
  if (!el) return
  if (chatOpen.value) return
  // 窗口缩到唇边（比岛还窄）时岛被裁掉，offsetWidth 量到的是裁切后的宽度：
  // 拿它算唇边会 428 → 276 → … 一路缩下去，热区跟着消失（实测踩过）。
  if (document.documentElement.clientWidth < islandCss.value.w) return
  const prev = el.style.transition
  el.style.transition = 'none'
  const w = el.offsetWidth
  const h = el.offsetHeight
  el.style.transition = prev
  // 再兜一层：小窗/开场切换的瞬间会量到几十像素的残值，低于岛的最小可读宽度一律不信
  if (w >= MIN_ISLAND_W && h > 8) islandCss.value = { w, h }
}

/** 记录满屏窗口原点/缩放；只有满屏才能拿到工作区原点 */
async function captureFrame(): Promise<boolean> {
  if (!isTauri()) return false
  const cw = document.documentElement.clientWidth
  const ch = document.documentElement.clientHeight
  // 小窗（band/lip）也是 >0 的合法尺寸，拿它当「满屏基准」会让之后所有展开都还原成小窗，
  // 于是 deck 打不开、窗口永远缩着（实测踩过）。满屏基准必须达到桌面量级才认。
  if (!(cw >= FULL_MIN_CW && ch >= FULL_MIN_CH)) return false
  try {
    const win = getCurrentWindow()
    const pos = await win.outerPosition()
    const size = await win.innerSize()
    const s = size.width / cw
    if (!(s > 0.2)) return false
    frameRect = { x: pos.x, y: pos.y, w: size.width, h: size.height, scale: s, cw, ch }
    return true
  } catch (e) {
    console.warn('[helmet] 记录窗口基准失败', e)
    return false
  }
}

/** 岛完整显示的小窗矩形（CSS，原点 = 工作区左上；岛水平居中于工作区） */
function bandRect() {
  const cw = frameRect?.cw || document.documentElement.clientWidth
  const w = islandCss.value.w + PAD_L + PAD_R
  const h = islandCss.value.h + PAD_Y * 2
  return { left: Math.round((cw - w) / 2), top: 0, w: Math.round(w), h: Math.round(h) }
}

/** 贴顶收起的小窗矩形：只剩唇边 + 热区（中央桌面天然可点） */
function lipRect() {
  const cw = frameRect?.cw || document.documentElement.clientWidth
  const w = islandCss.value.w + HOT_EXTRA
  // 唇边 4px 必须落在热区内，窗口高度取两者较大者
  const h = Math.max(HOT_PX, LIP_PX)
  return { left: Math.round((cw - w) / 2), top: 0, w: Math.round(w), h }
}

async function applyRect(r: { left: number; top: number; w: number; h: number }): Promise<boolean> {
  if (!frameRect) return false
  try {
    const win = getCurrentWindow()
    const { x, y, scale } = frameRect
    await win.setPosition(
      new PhysicalPosition(x + Math.round(r.left * scale), y + Math.round(r.top * scale)),
    )
    await win.setSize(new PhysicalSize(Math.round(r.w * scale), Math.round(r.h * scale)))
    debugText.value = `${r.w}x${r.h}css`
    return true
  } catch (e) {
    console.warn('[helmet] 调整窗口失败', e)
    return false
  }
}

/** 等窗口真正变成满屏（helmet-shown 早于 WebView resize 时，尺寸还是旧值） */
async function waitForFull(timeout = 1200): Promise<boolean> {
  const t0 = performance.now()
  while (!isFullWindow() && performance.now() - t0 < timeout) {
    await new Promise((r) => setTimeout(r, 40))
  }
  return isFullWindow()
}

/** 岛完整显示：窗口 = 岛外包矩形（band） */
async function applyBand(): Promise<boolean> {
  if (mode.value !== 'idle' || pinned()) return false
  measureIsland()
  if (!frameRect) await captureFrame()
  if (!frameRect) return false
  const ok = await applyRect(bandRect())
  if (!ok) return false
  docked.value = false
  persistCollapsed(false)
  geo.value = 'band'
  return true
}

/** 贴顶收起：先让岛滑出屏幕（动画可见），再把窗口缩到唇边条 */
async function applyLip(): Promise<boolean> {
  if (mode.value !== 'idle' || pinned()) return false
  measureIsland()
  if (!frameRect) await captureFrame()
  if (!frameRect) return false
  if (!docked.value) {
    docked.value = true
    await new Promise((r) => setTimeout(r, DOCK_ANIM_MS))
  }
  // 动画这 280ms 里用户可能已经点了岛/三角：此刻窗该是满的，不能再缩
  if (mode.value !== 'idle' || pinned()) return false
  const ok = await applyRect(lipRect())
  if (!ok) return false
  geo.value = 'lip'
  persistCollapsed(true)
  return true
}

/** 小窗 → 满屏：还原满屏基准矩形（无基准才请后端铺满工作区） */
async function expandToWorkArea(): Promise<boolean> {
  if (!isTauri()) return false
  if (isFullWindow()) {
    if (!frameRect) void captureFrame()
    geo.value = 'full'
    return true
  }
  try {
    const win = getCurrentWindow()
    if (frameRect && frameRect.cw >= FULL_MIN_CW) {
      docked.value = false
      await win.setPosition(new PhysicalPosition(frameRect.x, frameRect.y))
      await win.setSize(new PhysicalSize(frameRect.w, frameRect.h))
    } else {
      // 没有可信的满屏基准：请后端铺满工作区（helmet-shown 在非 idle 态不会抢收）
      frameRect = null
      await invoke('helmet_show')
    }
    let ok = await waitForFull()
    if (!ok) {
      // setSize 没顶到桌面：不要在这里再 invoke('helmet_show')——后端也会 setSize，
      // 两路同时改窗会卡在中间尺寸（实测把窗口缩成一条 276×3）。留待下次 helmet-shown 自愈。
      console.warn('[helmet] 恢复工作区未达满屏，保持现状')
    }
    if (ok) {
      await captureFrame()
      geo.value = 'full'
      docked.value = false
      persistCollapsed(false)
    }
    return ok
  } catch (e) {
    console.warn('[helmet] 恢复工作区失败', e)
    return false
  }
}

/* ------------------------------------------------------------------ */
/* 形态切换                                                            */
/* ------------------------------------------------------------------ */

/**
 * 窗口几何唯一出口：
 *  - idle 且无浮层、未开场 → 岛（band）或贴顶唇边条（lip）；两者都不占中央桌面
 *  - 其余（deck / chat / 上下班浮层 / 开场）→ 铺满工作区；deck/chat 用光标轮询命中 .hit
 */
async function syncWindow() {
  if (!isTauri()) return
  const wantFull = mode.value !== 'idle' || hoursOpen.value || bootActive.value
  if (wantFull) {
    const ok = await expandToWorkArea()
    geo.value = 'full'
    docked.value = false
    if (bootActive.value) {
      // 开场要能点一下跳过：整窗接事件
      stopPoll()
      await setIgnore(false)
      return
    }
    if (ok) {
      await setIgnore(true)
      startPoll()
    } else {
      // 展开失败（极少见）：退化为满窗 + 轮询，至少控件还能点
      await setIgnore(true)
      startPoll()
    }
    return
  }
  stopPoll()
  const ok = docked.value ? await applyLip() : await applyBand()
  if (ok) {
    // lip：整窗只剩顶部热区那一条，保持接事件（唤出靠 pointerenter）；
    // band：岛四周还有 PAD 透明留边，继续轮询光标——无命中时整窗穿透，留边不抢点
    await setIgnore(false)
    if (geo.value === 'band') startPoll()
  } else {
    // 收不起来：退化为满窗 + 轮询，至少岛还能点
    await setIgnore(true)
    startPoll()
  }
}

async function setMode(next: Mode) {
  if (mode.value === next) return
  const wasIdle = mode.value === 'idle'
  mode.value = next
  hoursOpen.value = false
  await nextTick()
  await syncWindow()
  try {
    localStorage.setItem(LS_OLD_COLLAPSE, next === 'idle' ? '1' : '0')
  } catch {
    /* ignore */
  }
  if (!wasIdle || next !== 'idle') debugText.value = ''
  if (next !== 'idle') void refreshBadges()
  else scheduleHide()
}

function openPanel(key: PanelKey) {
  panel.value = key
  if (mode.value !== 'deck') void setMode('deck')
  if (key === 'notes') {
    noteStore.openList()
  }
  if (key === 'settings') {
    hoursDraft.value = { ...hours.value }
    void loadSettings()
  }
}

/** 左栏「笔记」：没开就开中栏列表；已开则分层收起（中栏 + 右栏一起收） */
function toggleNotes() {
  if (panel.value === 'notes' && noteListOpen.value) {
    void noteStore.closeList()
    return
  }
  openPanel('notes')
}

/** 左栏「搜索」：底栏搜索框是全局入口，把它叫到焦点即可，不另造第二个搜索面板 */
async function focusSearch() {
  if (mode.value !== 'deck') await setMode('deck')
  await nextTick()
  const el = document.querySelector<HTMLInputElement>('.quick-search input')
  el?.focus()
  el?.select()
}

/** 岛右侧 ▾/▴：唯一的 HUD 展开/收起入口 */
function onToggleHud() {
  if (deckOpen.value) void setMode('idle')
  else void openPanel(panel.value)
}

/** 点岛主体（品牌/灯/日衰区）→ 完整 AI 对话舱；⚙ 与 ▾ 各自 stop，不落到这里 */
function onIslandClick(e: MouseEvent) {
  const t = e.target as HTMLElement | null
  if (t && (t.closest('.island-toggle') || t.closest('.island-gear') || t.closest('.island-chat'))) return
  if (chatOpen.value) return
  void setMode('chat')
}

function closeChat() {
  void setMode('idle')
}

/** Esc / 快捷键收起：立即贴顶只剩唇边 + 顶部热区，绝不隐藏整个 helmet */
async function collapseNow() {
  if (mode.value !== 'idle' || pinned()) return
  const ok = await applyLip()
  if (!ok) return
  stopPoll()
  await setIgnore(false)
  hovering.value = false
}

/* ------------------------------------------------------------------ */
/* 贴顶收起 / 唤出                                                     */
/* ------------------------------------------------------------------ */

let watchTimer: number | null = null
/** 首次观察到「光标不在窗内」的时刻；0 = 光标在窗内 */
let outSince = 0
/** 硬性等待（比如刚收起 HUD，先让界面静止一会儿） */
let hideNotBefore = 0
let localState = false
/** 启动后的第一次 helmet-shown 是自举显示：不能把落盘的折叠态冲掉 */
let firstShow = true

/** 这些态下岛必须完整显示（钉住）：对话、躯干、上下班浮层、开场 */
function pinned() {
  return chatOpen.value || deckOpen.value || hoursOpen.value || bootActive.value
}

function focusInside() {
  const w = wrapEl.value
  return !!(w && document.activeElement && w.contains(document.activeElement))
}

function scheduleHide(delay = HIDE_MS) {
  hideNotBefore = performance.now() + delay
}

/** 光标是否还在本窗里（真的问系统：穿透/改尺寸时 pointer 事件会漏） */
async function cursorInWindow(): Promise<boolean | null> {
  try {
    const pos = await invoke<[number, number] | null>('helmet_cursor_local')
    return pos != null
  } catch {
    return null
  }
}

/**
 * 贴顶看门狗：每 250ms 问一次系统光标。
 * 从「第一次看到光标在窗外」起满 450ms 才收——不靠 pointerleave
 * （改尺寸/穿透时它会漏，岛会一直挂着），也不受 tick 相位影响。
 */
async function tickDock() {
  if (!isTauri() || docked.value) return
  const now = performance.now()
  if (pinned() || mode.value !== 'idle') {
    outSince = 0
    return
  }
  if (keyboardNav.value && focusInside()) {
    outSince = 0
    return
  }
  const inside = await cursorInWindow()
  if (inside !== false) {
    outSince = 0
    if (inside === true) hovering.value = true
    return
  }
  if (!outSince) outSince = now
  if (now - outSince < HIDE_MS || now < hideNotBefore) return
  if (!frameRect) await captureFrame()
  const ok = await applyLip()
  if (!ok) return
  hovering.value = false
  stopPoll()
  await setIgnore(false)
}

function armWatch() {
  if (watchTimer != null) return
  if (!isTauri()) return
  watchTimer = window.setInterval(() => void tickDock(), 250)
}

function disarmWatch() {
  if (watchTimer != null) {
    window.clearInterval(watchTimer)
    watchTimer = null
  }
}

/** 顶部热区 / 岛被指到：先把窗口长回 band，再让岛滑下来 */
async function reveal() {
  if (docked.value) outSince = 0
  if (!docked.value || localState) return
  localState = true
  try {
    measureIsland()
    if (!frameRect) await captureFrame()
    if (frameRect) await applyRect(bandRect())
    docked.value = false
    persistCollapsed(false)
    geo.value = 'band'
    // 从唇边唤出后也要重新开始轮询：band 四周的 PAD 留边是透明的，
    // 没轮询就一直抢点（A3 实测踩到过）
    await setIgnore(false)
    startPoll()
  } finally {
    localState = false
  }
}

function onHoverIn() {
  hovering.value = true
  void reveal()
}

/** 贴顶时窗口只剩一条 10px 热区：这里收到任何指针移动，说明光标就在顶边上 */
function onAnyPointerMove() {
  if (docked.value) onHoverIn()
}

function onHoverOut() {
  hovering.value = false
  // 收起交给 tickDock 判定（以系统光标为准）
}

function onFocusIn() {
  void reveal()
}

function onFocusOut() {
  window.setTimeout(() => {
    if (!focusInside()) hovering.value = false
  }, 0)
}

/* ------------------------------------------------------------------ */
/* 开场（ASCII 海洋）：只作开机，不常驻、不可喂                           */
/* ------------------------------------------------------------------ */

function bootWanted() {
  try {
    return sessionStorage.getItem(SS_BOOT) !== '1'
  } catch {
    return true
  }
}

function endBoot() {
  if (!bootActive.value) return
  bootActive.value = false
  try {
    sessionStorage.setItem(SS_BOOT, '1')
  } catch {
    /* ignore */
  }
  outSince = 0
  scheduleHide(HIDE_MS)
  armWatch()
  void syncWindow()
}

/* ------------------------------------------------------------------ */
/* 穿透：光标轮询命中 .hit                                             */
/* ------------------------------------------------------------------ */

function cursorOverHit(lx: number, ly: number): boolean {
  const root = rootEl.value
  if (!root) return false
  const hits = root.querySelectorAll<HTMLElement>('.hit')
  for (const el of hits) {
    // 关闭态的躯干/浮层 visibility:hidden（会继承），其矩形仍在原位——
    // 不排除会让光标扫到不可见区域时误关穿透
    if (getComputedStyle(el).visibility === 'hidden') continue
    const r = el.getBoundingClientRect()
    if (r.width <= 0 || r.height <= 0) continue
    if (lx >= r.left && lx <= r.right && ly >= r.top && ly <= r.bottom) return true
  }
  return false
}

let pollTimer: number | null = null
let unlisteners: UnlistenFn[] = []

async function pollCursor() {
  if (!isTauri()) return
  // idle 的 band 态也要轮询：岛四周 PAD 留边是透明的，无命中必须保持穿透
  if (mode.value === 'idle' && !hoursOpen.value && !bootActive.value && geo.value !== 'band') return
  try {
    const pos = await invoke<[number, number] | null>('helmet_cursor_local')
    if (!pos) {
      await setIgnore(true)
      return
    }
    await setIgnore(!cursorOverHit(pos[0], pos[1]))
  } catch {
    /* 命令不可用时静默 */
  }
}

function startPoll() {
  stopPoll()
  if (!isTauri()) return
  pollTimer = window.setInterval(() => void pollCursor(), 60)
}

function stopPoll() {
  if (pollTimer != null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

/* ------------------------------------------------------------------ */
/* 日衰 / 剩余工时                                                      */
/* ------------------------------------------------------------------ */

/** 上下班浮层在 idle 态也要完整可见：开则铺满窗，关则缩回岛 */
watch(hoursOpen, async () => {
  await nextTick()
  await syncWindow()
})

function readHours(): { start: string; end: string } {
  try {
    const raw = localStorage.getItem(LS_HOURS)
    if (raw) {
      const v = JSON.parse(raw) as { start?: string; end?: string }
      if (/^\d{2}:\d{2}$/.test(v.start || '') && /^\d{2}:\d{2}$/.test(v.end || '')) {
        return { start: v.start as string, end: v.end as string }
      }
    }
  } catch {
    /* ignore */
  }
  return { start: '09:00', end: '18:30' }
}

const hours = ref(readHours())
const hoursDraft = ref({ ...hours.value })
const nowMs = ref(Date.now())

function toMin(hhmm: string): number {
  const [h, m] = hhmm.split(':').map((x) => parseInt(x, 10))
  return (h || 0) * 60 + (m || 0)
}

const remain = computed(() => {
  const s = toMin(hours.value.start)
  let e = toMin(hours.value.end)
  const d = new Date(nowMs.value)
  const cur = d.getHours() * 60 + d.getMinutes() + d.getSeconds() / 60
  let c = cur
  if (e <= s) {
    e += 1440
    if (c < s) c += 1440
  }
  const total = Math.max(1, e - s)
  const left = Math.max(0, Math.min(total, e - c))
  return { pct: Math.round((left / total) * 100), leftMin: Math.round(left), total }
})

const pct = computed(() => remain.value.pct)
const warn = computed(() => pct.value <= 20)
const ringLen = computed(() => ((pct.value / 100) * 50.24).toFixed(2))
const remainLabel = computed(() => {
  const m = remain.value.leftMin
  if (m <= 0) return '已下班'
  const h = Math.floor(m / 60)
  const mm = m % 60
  return `还剩 ${h ? h + 'h' : ''}${mm ? mm + 'm' : h ? '' : '0m'}`
})
const hoursLabel = computed(() => `${hours.value.start}–${hours.value.end}`)

function saveHours() {
  const { start, end } = hoursDraft.value
  if (!/^\d{2}:\d{2}$/.test(start) || !/^\d{2}:\d{2}$/.test(end)) return
  hours.value = { start, end }
  try {
    localStorage.setItem(LS_HOURS, JSON.stringify(hours.value))
  } catch {
    /* ignore */
  }
  nowMs.value = Date.now()
  hoursOpen.value = false
  showToast(`上下班已存：${start}–${end}`)
}

/* ------------------------------------------------------------------ */
/* 设置：聊天模型 + 快捷键一览（读写同一份 config，落盘后重启仍在）      */
/* ------------------------------------------------------------------ */

const cfgModels = ref<ChatModelConfig[]>([])
const modelPick = ref('')
const hotkeys = ref({
  toggle: 'Ctrl+Shift+Space',
  chat: 'Ctrl+Shift+K',
  clipboard: 'Ctrl+`',
  search: 'Ctrl+K',
  notes: 'Ctrl+Shift+N',
})

function modelLabel(m: ChatModelConfig): string {
  return isPlatformModel(m) ? PLATFORM_ENTRY_NAME : m.name
}

async function loadSettings() {
  if (!isTauri()) return
  try {
    const cfg = await tauriApi.getUiConfig()
    cfgModels.value = cfg.chat_models || []
    modelPick.value = cfg.chat_selected_model || ''
    hotkeys.value = {
      toggle: cfg.global_shortcut || hotkeys.value.toggle,
      chat: cfg.chat_shortcut || hotkeys.value.chat,
      clipboard: cfg.clipboard_shortcut || hotkeys.value.clipboard,
      search: cfg.search_shortcut || hotkeys.value.search,
      notes: cfg.notes_shortcut || hotkeys.value.notes,
    }
  } catch (e) {
    console.warn('[helmet] 读取设置失败', e)
  }
}

/** 落全局记住的对话模型（后端锁内读改写，主窗/独立窗/小岛共用一份） */
async function saveModel() {
  if (!isTauri()) return
  const name = modelPick.value.trim()
  try {
    await tauriApi.setChatSelectedModel(name)
    showToast(`聊天模型已存：${name || '未设置'}`)
  } catch (e) {
    showToast('模型保存失败')
    console.warn('[helmet] set_chat_selected_model failed', e)
  }
}

/* ------------------------------------------------------------------ */
/* 搜索（待办 + 笔记 + 速达，一处直达）                                */
/* ------------------------------------------------------------------ */

const q = ref('')
const results = ref<SearchResult | null>(null)
const searching = ref(false)
let searchTimer: number | null = null

async function runSearch() {
  const kw = q.value.trim()
  if (!kw || !isTauri()) {
    results.value = null
    return
  }
  searching.value = true
  try {
    results.value = await tauriApi.searchAll(kw)
  } catch (e) {
    console.warn('[helmet] search failed', e)
    results.value = null
  } finally {
    searching.value = false
  }
}

watch(q, () => {
  if (searchTimer != null) window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => void runSearch(), 220)
})

function clearSearch() {
  q.value = ''
  results.value = null
}

function openNoteFromSearch(id: number) {
  panel.value = 'notes'
  noteStore.openList()
  void noteStore.open(id)
  clearSearch()
}

async function launchFromSearch(id: number) {
  try {
    await tauriApi.launchResource(id)
    clearSearch()
    await setMode('idle')
  } catch (e) {
    showToast('启动失败：' + String(e).slice(0, 50))
  }
}

const searchTotal = computed(() => {
  const r = results.value
  return r ? r.todos.length + r.notes.length + r.resources.length : 0
})

/* ------------------------------------------------------------------ */
/* 角标 / 提示                                                         */
/* ------------------------------------------------------------------ */

const todoCount = ref(0)
const clipCount = ref(0)
let toastTimer: number | null = null

function showToast(msg: string) {
  toastMsg.value = msg
  if (toastTimer != null) window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => (toastMsg.value = ''), 2200)
}

async function refreshBadges() {
  if (!isTauri()) return
  try {
    const todos = await tauriApi.listTodos()
    todoCount.value = todos.filter((t) => !t.done).length
  } catch {
    /* ignore */
  }
  try {
    const clips = await tauriApi.clipboardList(undefined, 40, 0)
    clipCount.value = clips.length
  } catch {
    /* ignore */
  }
}

function onTaken(label: string) {
  showToast('已放回剪贴板：' + label.slice(0, 24))
  void setMode('idle')
}

function onLaunched(name: string) {
  showToast('已调起：' + name)
  void setMode('idle')
}

/* ------------------------------------------------------------------ */
/* 全局快捷键 → HUD 内面板                                             */
/* ------------------------------------------------------------------ */

/**
 * 原版快捷键（剪贴板 / 搜索 / 聊天 / 速记 / 总开关）在冒烟构建里不再弹独立小窗，
 * 由 helmet_window.rs::open_panel 转发到本事件：一律打开 HUD 内的对应面板。
 */
async function onHotkey(p: string) {
  if (bootActive.value) endBoot()
  if (p === 'toggle') {
    // 总开关：已展开 → 收起；只在岛/唇边 → 展开上次的面板
    if (mode.value !== 'idle') await setMode('idle')
    else openPanel(panel.value)
    return
  }
  if (p === 'chat') {
    await setMode('chat')
    return
  }
  if (p === 'clipboard') {
    openPanel('clipboard')
    return
  }
  if (p === 'notes') {
    openPanel('notes')
    return
  }
  if (p === 'settings') {
    openPanel('settings')
    return
  }
  if (p === 'search') {
    if (mode.value !== 'deck') await setMode('deck')
    await nextTick()
    const el = document.querySelector<HTMLInputElement>('.quick-search input')
    el?.focus()
    el?.select()
  }
}

/* ------------------------------------------------------------------ */
/* 键盘                                                                */
/* ------------------------------------------------------------------ */

function onKeydown(e: KeyboardEvent) {
  const tag = (e.target as HTMLElement | null)?.tagName
  const inField = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
  if (e.key === 'Tab') keyboardNav.value = true
  if (bootActive.value && (e.key === 'Enter' || e.key === 'Escape' || e.key === ' ')) {
    e.preventDefault()
    endBoot()
    return
  }
  if (e.key === 'Escape') {
    e.preventDefault()
    if (hoursOpen.value) {
      hoursOpen.value = false
      return
    }
    if (results.value) {
      clearSearch()
      return
    }
    if (mode.value !== 'idle') {
      void setMode('idle')
      return
    }
    // idle 且岛还完整显示：Esc 只把它收回顶部唇边，不关掉整个 helmet
    if (!docked.value) void collapseNow()
    return
  }
  if (e.ctrlKey && e.shiftKey && (e.key === 'V' || e.key === 'v')) {
    e.preventDefault()
    void openPanel('clipboard')
    return
  }
  if (e.ctrlKey && (e.key === 'k' || e.key === 'K')) {
    e.preventDefault()
    if (mode.value !== 'deck') void openPanel('todos')
    nextTick(() => {
      const el = document.querySelector<HTMLInputElement>('.quick-search input')
      el?.focus()
    })
    return
  }
  if (!inField && e.key === '/' && mode.value === 'deck') {
    e.preventDefault()
    document.querySelector<HTMLInputElement>('.quick-search input')?.focus()
  }
}

/* ------------------------------------------------------------------ */
/* 生命周期                                                            */
/* ------------------------------------------------------------------ */

function bindDebug() {
  watchEffect(() => {
    ;(window as unknown as { __helmet?: unknown }).__helmet = {
      mode: mode.value,
      panel: panel.value,
      geo: geo.value,
      docked: docked.value,
      hover: hovering.value,
      boot: bootActive.value,
      ignoring: ignoring.value,
      chat: chatOpen.value,
      deck: deckOpen.value,
      pct: pct.value,
      remain: remainLabel.value,
      hours: hoursLabel.value,
      todos: todoCount.value,
      clip: clipCount.value,
      // 笔记三栏取证：验收脚本要能看见「中栏开没开、右栏开没开、当前是哪一条」
      notes: {
        list: noteListOpen.value,
        editor: noteEditorOpen.value,
        active: noteStore.activeId.value,
        count: noteStore.live.value.length,
      },
      // 几何取证：验收脚本要能看见「岛量到多大」和「满屏基准记成了什么」
      island: { ...islandCss.value },
      frame: frameRect ? { ...frameRect } : null,
      viewport: [document.documentElement.clientWidth, document.documentElement.clientHeight],
      // 展开仪式光效取证：触发次数 + 规格时长（对照 .fx.is-ceremony 的 DOM 类）
      fx: { ceremony: fxCeremony.value, flashMs: FLASH_MS },
    }
  })
}

/** 鼠标按下就把「键盘钉住」放掉，免得点一次岛之后永远不收 */
function onPointerDownAny() {
  keyboardNav.value = false
}

onMounted(async () => {
  ready.value = true
  bindDebug()
  // 折叠记忆：先在本地把 docked 摆好，后续 syncWindow 才会直接收到 lip
  docked.value = readCollapsed()
  void loadSettings()
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('pointerdown', onPointerDownAny, true)
  window.addEventListener('pointermove', onAnyPointerMove, { passive: true })
  nowMs.value = Date.now()
  const tick = window.setInterval(() => (nowMs.value = Date.now()), 15000)
  unlisteners.push(() => window.clearInterval(tick))

  bootActive.value = false

  if (!isTauri()) {
    void refreshBadges()
    return
  }

  // 先装监听再 show：helmet-shown 是「开场 + 贴顶」的唯一入口，事件早于挂载会丢
  try {
    unlisteners.push(
      await listen('helmet-shown', () => {
        void (async () => {
          await waitForFull()
          await captureFrame()
          const startup = firstShow
          firstShow = false
          // 本次会话还没放过开场：趁机放一遍（跳过/播完即记，不再重放）
          if (mode.value === 'idle' && !hoursOpen.value && !bootActive.value && bootWanted()) {
            bootActive.value = true
            await syncWindow()
            return
          }
          // 由主动展开（deck/chat/浮层）驱动的 show 不抢收
          if (mode.value !== 'idle' || hoursOpen.value || bootActive.value) return
          // 启动首帧：按落盘记忆恢复折叠态（docked 已在 mount 时读好）；
          // 之后每次唤起（快捷键/托盘）仍先完整露岛，静止 450ms 再贴顶
          if (!startup) {
            docked.value = false
            persistCollapsed(false)
          }
          await syncWindow()
          scheduleHide()
        })()
      }),
    )
    unlisteners.push(
      await listen('helmet-hidden', () => {
        stopPoll()
        ignoring.value = null
      }),
    )
    // 全局快捷键 → HUD 内面板（helmet_window.rs::open_panel 转发）
    unlisteners.push(
      await listen<{ panel?: string }>('helmet-hotkey', (e) => {
        void onHotkey(String(e.payload?.panel || 'toggle'))
      }),
    )
  } catch (e) {
    console.warn('[helmet] listen failed', e)
  }

  // 预创建窗是隐藏的 1280×720 占位：必须请后端铺满工作区后才敢记基准
  try {
    await invoke('helmet_show')
  } catch {
    /* ignore */
  }
  await waitForFull()
  await nextTick()
  measureIsland()
  await captureFrame()

  // 窗已在屏上且本会话没放过开场 → 当场放；否则直接按 idle 收
  let visible = true
  try {
    visible = await getCurrentWindow().isVisible()
  } catch {
    /* ignore */
  }
  if (visible && !bootActive.value && bootWanted()) bootActive.value = true

  await syncWindow()
  // 开场跑完之前不贴顶；无开场则 450ms 后自己贴顶
  outSince = 0
  armWatch()
  if (!bootActive.value) scheduleHide()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('pointerdown', onPointerDownAny, true)
  window.removeEventListener('pointermove', onAnyPointerMove)
  disarmWatch()
  stopPoll()
  if (fxTimer != null) window.clearTimeout(fxTimer)
  for (const u of unlisteners) u()
  unlisteners = []
})

/* ------------------------------------------------------------------ */
/* ASCII 纹理（只铺在壳体内部，永不进中央穿透区）                        */
/* ------------------------------------------------------------------ */

/** 左轨：竖向刻线 + 点阵，两端平直收口——不做折线 / L 形瞄具 / ┌┘ 端饰 */
const asciiRail = computed(() => {
  const rows: string[] = []
  for (let i = 0; i < 26; i++) {
    if (i % 6 === 0) rows.push('·╌·')
    else if (i % 6 === 3) rows.push(' ▪ ')
    else rows.push(' │ ')
  }
  return rows.join('\n')
})

/** 面板：稀疏点阵底纹（不排字，避免与内容抢读） */
const asciiPanel = computed(() => {
  const rows: string[] = []
  for (let y = 0; y < 30; y++) {
    let s = ''
    for (let x = 0; x < 46; x++) {
      const k = (x * 7 + y * 11) % 17
      s += k === 0 ? '·' : k === 5 ? ' ' : k === 9 ? '˙' : ' '
    }
    rows.push(s)
  }
  return rows.join('\n')
})

/** 底栏：横向量尺 */
const asciiEave = computed(() => {
  const line = '─ · ─ · ─ · ─ · ─ · ─ · ─ · ─ · ─ · ─ · ─ · ─ · ─ · ─ · ─ · ─ · '
  return [line, line].join('\n')
})

defineExpose({ openPanel, setMode })
</script>

<template>
  <div
    ref="rootEl"
    class="helmet-root"
    :class="{ ready, 'no-anim': noAnim, 'island-docked': docked, compact: geo !== 'full' }"
    :data-mode="mode"
    :data-panel="panel"
  >
    <!-- 顶部 10px 唤出热区（贴顶时鼠标移到屏幕顶边即可唤出） -->
    <div
      class="island-hot hit"
      aria-hidden="true"
      @pointerenter="onHoverIn"
      @pointerleave="onHoverOut"
    />
    <!-- 贴顶时露出的 4px 唇边 -->
    <div class="island-lip-tip" aria-hidden="true" />

    <!-- ******************************************** 灵动岛（常驻，可贴顶） -->
    <div ref="wrapEl" class="island-wrap" @focusin="onFocusIn" @focusout="onFocusOut">
      <div
        ref="islandEl"
        class="island hit"
        :class="{ 'is-chat': chatOpen }"
        role="button"
        :aria-expanded="chatOpen"
        :aria-label="chatOpen ? '对话舱' : 'shell-hub · 点击打开 AI 对话'"
        :title="chatOpen ? '对话舱 · 通用 AI' : `对话舱 · ${remainLabel}（${hoursLabel}）`"
        @click="onIslandClick"
        @pointerenter="onHoverIn"
        @pointerleave="onHoverOut"
      >
        <div class="island-face">
          <span class="island-led" aria-hidden="true" />
          <div class="island-brand">
            <span class="cn">{{ chatOpen ? '聊天 · Comms' : 'shell-hub' }}</span>
                        <span class="en">{{ chatOpen ? 'GENERAL AI · LOCAL' : 'SHELL-HUB' }}</span>
          </div>
          <div class="island-decay">
            <span class="island-pct" :class="{ warn }">{{ pct }}%</span>
            <span class="island-ring" aria-hidden="true">
              <svg viewBox="0 0 22 22">
                <circle class="track" cx="11" cy="11" r="8" />
                <circle
                  class="fg"
                  :class="{ warn }"
                  cx="11"
                  cy="11"
                  r="8"
                  :stroke-dasharray="`${ringLen} 50.24`"
                />
              </svg>
            </span>
          </div>
          <button
            class="island-gear"
            type="button"
            title="设定上下班时间"
            aria-label="设定上下班时间"
            @click.stop="
              hoursOpen = !hoursOpen;
              hoursDraft = { ...hours }
            "
          >
            ⚙
          </button>
          <!-- HUD 唯一开关：▾ 展开 / ▴ 收起（不点岛主体、不开对话） -->
          <button
            class="island-toggle"
            type="button"
            :aria-expanded="deckOpen"
            :title="deckOpen ? '收起 shell-hub HUD' : '展开 shell-hub HUD'"
                        :aria-label="deckOpen ? '收起 shell-hub HUD' : '展开 shell-hub HUD'"
            @click.stop="onToggleHud"
          >
            <span class="chev" :class="{ 'is-up': deckOpen }" aria-hidden="true">{{ deckOpen ? '▴' : '▾' }}</span>
          </button>
        </div>

        <HelmetChatCabin v-if="chatOpen" @close="closeChat" @toast="showToast" />
      </div>

      <!-- 上下班配置（挂岛下，独立 hit） -->
      <div v-if="hoursOpen" class="hours-pop panel cut hit" @click.stop>
        <h4>上下班 · 日衰口径</h4>
        <div class="row">
          <div class="cg">
            <label>上班</label>
            <input v-model="hoursDraft.start" type="time" step="60" />
          </div>
          <div class="cg">
            <label>下班</label>
            <input v-model="hoursDraft.end" type="time" step="60" />
          </div>
        </div>
        <div class="acts">
          <span class="hint">{{ remainLabel }} · {{ pct }}%</span>
          <button class="btn primary sm cut-sm" @click="saveHours">保存</button>
        </div>
      </div>
    </div>

    <!-- ******************************************** 躯干：左轨 + 面板 + 底栏（无右栏） -->
    <div class="hud" :class="{ 'is-open': deckOpen }" :aria-hidden="!deckOpen">
      <div class="dock">
        <nav class="rail panel hit" aria-label="shell-hub 模块">
          <pre class="ascii-bg is-rail" aria-hidden="true">{{ asciiRail }}</pre>
          <span class="rail-cap">OPS</span>
          <button
            class="nav-btn"
            data-nav="todos"
            :class="{ 'is-on': panel === 'todos' && deckOpen }"
            title="待办"
            @click="openPanel('todos')"
          >
            <span class="ico">01</span>
            <span class="badge" :class="{ 'is-zero': todoCount === 0 }">{{ todoCount }}</span>
            <span class="lab">待办</span>
          </button>
          <button
            class="nav-btn"
            data-nav="notes"
            :class="{ 'is-on': panel === 'notes' && noteListOpen }"
            title="笔记"
            @click="toggleNotes"
          >
            <span class="ico">02</span>
            <span class="lab">笔记</span>
          </button>
          <button class="nav-btn" data-nav="chat" title="聊天 / AI" @click="setMode('chat')">
            <span class="ico">03</span>
            <span class="lab">聊天 / AI</span>
          </button>
          <button
            class="nav-btn"
            data-nav="clipboard"
            :class="{ 'is-on': panel === 'clipboard' && deckOpen }"
            title="剪贴板"
            @click="openPanel('clipboard')"
          >
            <span class="ico">04</span>
            <span class="badge" :class="{ 'is-zero': clipCount === 0 }">{{ clipCount }}</span>
            <span class="lab">剪贴板</span>
          </button>
          <button
            class="nav-btn"
            data-nav="launch"
            :class="{ 'is-on': panel === 'launch' && deckOpen }"
            title="启动常用工具"
            @click="openPanel('launch')"
          >
            <span class="ico">05</span>
            <span class="lab">启动常用</span>
          </button>
          <button class="nav-btn" data-nav="search" title="搜索" @click="focusSearch">
            <span class="ico">06</span>
            <span class="lab">搜索</span>
          </button>
          <span class="rail-sep" aria-hidden="true" />
          <button
            class="nav-btn"
            data-nav="settings"
            :class="{ 'is-on': panel === 'settings' && deckOpen }"
            title="设置"
            @click="openPanel('settings')"
          >
            <span class="ico">⚙</span>
            <span class="lab">设置</span>
          </button>
        </nav>

        <aside
          class="panel-col panel hit"
          :class="{ 'is-notes-list': panel === 'notes', 'is-collapsed': panel === 'notes' && !noteListOpen }"
          aria-label="shell-hub 面板"
        >
          <pre class="ascii-bg is-work" aria-hidden="true">{{ asciiPanel }}</pre>
          <HelmetTodoPanel
            v-show="panel === 'todos'"
            @count="todoCount = $event"
            @toast="showToast"
            @close="setMode('idle')"
          />
          <HelmetNotesPanel v-if="panel === 'notes'" @toast="showToast" />
          <HelmetClipboardPanel
            v-if="panel === 'clipboard'"
            @count="clipCount = $event"
            @taken="onTaken"
          />
          <HelmetLaunchPanel
            v-if="panel === 'launch'"
            @launched="onLaunched"
            @toast="showToast"
          />
          <div v-if="panel === 'settings'" class="work">
            <div class="work-hd">
              <div class="title">设置 <span class="en">Settings</span></div>
              <button
                class="icon-btn"
                type="button"
                title="收起设置"
                aria-label="收起设置"
                @click="setMode('idle')"
              >
                ✕
              </button>
            </div>
            <div class="work-bd">
              <div class="set-block">
                <h4>上下班 · 日衰口径</h4>
                <p class="set-note">灵动岛的百分比按这段区间衰减，到下班点为 0%。</p>
                <div class="set-row-inputs">
                  <div class="cg">
                    <label>上班</label>
                    <input v-model="hoursDraft.start" type="time" step="60" class="cut-sm" />
                  </div>
                  <div class="cg">
                    <label>下班</label>
                    <input v-model="hoursDraft.end" type="time" step="60" class="cut-sm" />
                  </div>
                </div>
                <div class="set-acts">
                  <span class="hint">{{ hoursLabel }} · {{ remainLabel }}</span>
                  <button class="btn sm primary cut-sm" @click="saveHours">保存</button>
                </div>
              </div>
              <div class="set-block">
                <h4>聊天模型</h4>
                <p class="set-note">新会话默认用这个模型；与主窗、独立对话窗共用同一份模型配置，落盘后重启仍在。</p>
                <div class="set-row-inputs is-one">
                  <div class="cg">
                    <label>模型</label>
                    <select v-model="modelPick" class="cut-sm" title="聊天默认模型" @change="saveModel">
                      <option value="">（未设置）</option>
                      <option v-for="m in cfgModels" :key="m.id" :value="modelLabel(m)">
                        {{ modelLabel(m) }}
                      </option>
                    </select>
                  </div>
                </div>
                <div class="set-acts">
                  <span class="hint">{{ modelPick || '未设置' }} · {{ cfgModels.length }} 个可用</span>
                  <button class="btn sm cut-sm" type="button" @click="loadSettings">重新读取</button>
                </div>
              </div>
              <div class="set-block">
                <h4>快捷键 · 呼出 HUD 内面板</h4>
                <div class="set-row"><span>唤起 / 收起 HUD</span><b>{{ hotkeys.toggle }}</b></div>
                <div class="set-row"><span>聊天</span><b>{{ hotkeys.chat }}</b></div>
                <div class="set-row"><span>剪贴板</span><b>{{ hotkeys.clipboard }}</b></div>
                <div class="set-row"><span>搜索</span><b>{{ hotkeys.search }}</b></div>
                <div class="set-row"><span>笔记</span><b>{{ hotkeys.notes }}</b></div>
              </div>
              <div class="set-block">
                <h4>壳体</h4>
                <div class="set-row"><span>产品</span><b>shell-hub</b></div>
                <div class="set-row"><span>展开 / 收起</span><b>岛右侧 ▾</b></div>
                <div class="set-row"><span>贴顶收起</span><b>Esc 收回唇边</b></div>
              </div>
            </div>
          </div>
        </aside>

        <!-- 第三栏：笔记编辑（点中栏条目才出现，可单独收起） -->
        <aside
          v-if="panel === 'notes' && noteListOpen && noteEditorOpen"
          class="panel-col panel hit is-notes-editor"
          aria-label="笔记编辑"
        >
          <HelmetNoteEditor @toast="showToast" />
        </aside>
      </div>

      <!-- 底栏：一处搜索待办与笔记（+ 速达） -->
      <footer class="eave-bot panel cut hit">
        <pre class="ascii-bg is-eave" aria-hidden="true">{{ asciiEave }}</pre>
        <div class="quick-search">
          <span class="tag">Search</span>
          <input
            v-model="q"
            class="cut-sm"
            placeholder="搜待办 / 笔记 / 速达，回车打开"
            spellcheck="false"
            @keydown.enter.prevent="runSearch"
          />
        </div>
        <span class="ctx-hint">
          {{ searching ? '检索中…' : results ? `${searchTotal} 条` : '待办 · 笔记 · 速达' }}
        </span>
      </footer>

      <div v-if="results" class="search-pop panel cut hit">
        <div v-if="!searchTotal" class="empty" style="padding: 14px">没有命中「{{ q }}」。</div>
        <button
          v-for="t in results.todos"
          :key="'t' + t.id"
          class="search-hit"
          @click="
            openPanel('todos');
            clearSearch()
          "
        >
          <span class="kind">待办</span>
          <span class="t">{{ t.title }}</span>
        </button>
        <button
          v-for="n in results.notes"
          :key="'n' + n.id"
          class="search-hit"
          @click="openNoteFromSearch(n.id)"
        >
          <span class="kind">笔记</span>
          <span class="t">{{ n.title }}</span>
        </button>
        <button
          v-for="r in results.resources"
          :key="'r' + r.id"
          class="search-hit"
          @click="launchFromSearch(r.id)"
        >
          <span class="kind">速达 · {{ r.kind }}</span>
          <span class="t">{{ r.name }}</span>
        </button>
      </div>
    </div>

    <!-- 装饰（不吃事件）：淡 vignette + 轻扫描线常驻展开态；
         收起→展开那一下 .is-ceremony 全屏 grain+chroma 150ms；对话/收起态不铺满屏 -->
    <div
      class="fx"
      :class="{
        'is-on': deckOpen || fxCollapsing,
        'is-ceremony': fxCeremonyOn,
        'is-flashout': fxFlashoutOn,
      }"
      aria-hidden="true"
    >
      <div class="vig" />
      <div class="scan" />
      <div class="grain" />
      <div class="chroma" />
      <div class="corners">
        <i class="tl" /><i class="tr" /><i class="bl" /><i class="br" />
      </div>
    </div>

    <!-- 开场：ASCII 海洋（只作开机，结束即卸载） -->
    <HelmetBoot v-if="bootActive" @done="endBoot" />

    <div v-if="showDbg" class="dbg" aria-hidden="true">
      {{ mode }} · {{ geo }} · {{ ignoring ? 'PASS' : 'HIT' }} · {{ debugText }}
    </div>

    <div v-if="toastMsg" class="toast cut-sm">{{ toastMsg }}</div>
  </div>
</template>