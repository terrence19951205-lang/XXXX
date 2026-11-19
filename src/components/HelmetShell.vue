<script setup lang="ts">
/**
 * Helmet 座舱壳 v0.8 · 灵动岛
 *
 * 形态（PRD v0.4.1）：
 *  - idle：只留顶部小岛（shell-hub + 日衰% + ▾），中央桌面可点。
 *  - deck：左轨（功能短名常显）+ 面板从轨右缘铺开；中央洞可点桌面。
 *  - chat：点小岛（或左轨「聊天」），完整对话舱挂在岛下。
 *  对话舱与 HUD 壳（左轨/面板）相互独立：可同时开；收起对话只收舱，▾ 仍只管壳。
 *
 * 穿透：非 idle 时窗口铺满工作区，默认整窗穿透，80ms 轮询
 * `helmet_cursor_local` 命中 `.hit` 才临时关穿透（Windows 单窗方案）。
 */
import { computed, nextTick, onMounted, onUnmounted, provide, ref, watch, watchEffect } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import { getCurrentWindow } from '@tauri-apps/api/window'
import { PhysicalPosition, PhysicalSize } from '@tauri-apps/api/dpi'
import {
  PLATFORM_ENTRY_NAME,
  displayModelName,
  isPlatformModel,
  isTauri,
  tauriApi,
  type ChatModelConfig,
  type ClipboardItem,
  type Countdown,
} from '../api/tauri'
import HelmetChatCabin from './helmet/HelmetChatCabin.vue'
import HelmetTodoTri from './helmet/HelmetTodoTri.vue'
import HelmetNotesFullPanel from './helmet/HelmetNotesFullPanel.vue'
import HelmetClipTri from './helmet/HelmetClipTri.vue'
import HelmetSearchTri from './helmet/HelmetSearchTri.vue'
import HelmetSudaPanel from './helmet/HelmetSudaPanel.vue'
import { pendingNoteId, pendingTodoId } from './helmet/hudBus'
import HelmetSettingsFullPanel from './helmet/HelmetSettingsFullPanel.vue'
import HelmetBoot from './helmet/HelmetBoot.vue'
import { useHelmetNotes } from '../composables/useHelmetNotes'
import './helmet/helmet.css'
import './helmet/hud-kit.css'
import { FEATURES } from '../config/features'
import { useStore } from '../stores/workbench'

type Mode = 'idle' | 'deck' | 'chat'
/** P1-3：便签并进笔记（笔记列表筛选「便签」），倒计时/日衰放到岛上一眼可见，二者不再占左轨 */
type PanelKey = 'todos' | 'notes' | 'clipboard' | 'launch' | 'search' | 'settings'
const PANEL_KEYS: PanelKey[] = ['todos', 'notes', 'clipboard', 'launch', 'search', 'settings']
const store = useStore()

const LS_OLD_COLLAPSE = 'rr.hud.collapsed'
const LS_HOURS = 'rr.hud.hours'
/** 折叠记忆：贴顶收起（lip）落盘；杀进程重启后按上次折叠态回来 */
const LS_COLLAPSED = 'rr.hud.collapsed.v10'
const SS_BOOT = 'rr.hud.bootPlayed'
/** 满屏判定：窗口常驻工作区，高度上千 px；小窗时代留下的兜底判据 */
const isFullWindow = () => document.documentElement.clientHeight > 300
/** 岛的最小可信宽度（量到比这个还小说明正处在裁切/切换瞬间，读数丢弃） */
const MIN_ISLAND_W = 180
/** 满屏基准的最小尺寸（CSS）：低于这个值说明量到的是小窗，不能当工作区基准 */
const FULL_MIN_CW = 640
const FULL_MIN_CH = 400
/** 移开鼠标后多久再贴顶 */
const HIDE_MS = 450
/** 指针离开「岛 + 对话舱」且舱内无键盘焦点后，满此时长只收对话舱，不收 HUD 壳/面板 */
const CHAT_IDLE_MS = 5000

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

const deckOn = ref(false)
const chatOn = ref(false)
const panel = ref<PanelKey>('todos')
/** 设置面板的两个页签：system = 原版 SettingsView（系统级配置）；island = 小岛自己的口径 */
const settingsTab = ref<'system' | 'island'>('system')

/* 截图 / 录屏：原版是两个独立窗口（recorder-overlay / recorder-control），由后端预创建。
 * 壳这边不做面板，只做「唤起」——但必须先把自己藏起来：HUD 是常驻置顶的，
 * 不藏就会把自己（岛、面板、阴影）印进用户的截图里。 */
const capturing = ref(false)
let captureTimer: number | null = null

async function openCapture(mode: 'shot' | 'record') {
  if (!isTauri()) return
  capturing.value = true
  if (captureTimer) window.clearTimeout(captureTimer)
  // 兜底：万一焦点没回来（用户切到别的程序），60 秒后自己恢复，不留在隐形状态
  captureTimer = window.setTimeout(() => {
    capturing.value = false
    captureTimer = null
  }, 60_000)
  try {
    await tauriApi.recorderOpenOverlay(mode)
  } catch (e) {
    capturing.value = false
    showToast(String(e))
  }
}

/** 壳这边替用户收掉选区层：选区层显示时键盘焦点可能仍落在 HUD（我们自己把窗口
 *  藏起来但没让出焦点），Overlay 内置的 Esc 就收不到；用户在 HUD 上按 Esc 时
 *  由我们调 recorder_close_overlay，交互结果一致。 */
async function closeCapture() {
  if (!isTauri()) return
  try {
    await tauriApi.recorderCloseOverlay()
  } catch {
    /* 窗口已收也不该报错打扰用户 */
  }
  endCapture()
}

function onSudaOpenPanel(e: Event) {
  const detail = (e as CustomEvent<{ id: number; name?: string }>).detail
  if (!detail || typeof detail.id !== 'number') return
  void tauriApi
    .sudaBrowserOpen(detail.id)
    .then(() => {
      // 浏览器窗是普通窗，HUD 常驻置顶会压在它上面：把 deck 收起来，
      // 让出画面（岛还在，随时可再展开），别让面板挡着用户要看的东西。
      setMode('idle')
      showToast(`已在应用内浏览器打开 ${detail.name ?? '网页'}`)
    })
    .catch((err) => showToast(String(err)))
}

/** 选区层收工（截图完成或被 Esc 取消）→ 把自己显回来。
 *  不能靠 window focus 判断：实测选区层 set_focus 后 HUD 仍会收到 focus，
 *  一收到就恢复 → 岛又出现在用户的截图里。改用后端 hide_overlay 的全局广播。 */
function endCapture() {
  if (!capturing.value) return
  capturing.value = false
  if (captureTimer) {
    window.clearTimeout(captureTimer)
    captureTimer = null
  }
}
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
const chatOpen = computed(() => chatOn.value)
const deckOpen = computed(() => deckOn.value)
/** 旧脚本兼容：仅对话开时为 chat；HUD 开（不论对话是否开）为 deck；都关为 idle */
const mode = computed<Mode>(() => {
  if (deckOn.value) return 'deck'
  if (chatOn.value) return 'chat'
  return 'idle'
})

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

/* 录音不在后台继续：HUD 壳收起时笔记那一路立即停录丢弃（对话舱收起会卸载组件，自己停） */
watch(deckOpen, (open) => {
  if (!open) window.dispatchEvent(new CustomEvent('hud-voice-stop', { detail: { owner: 'notes', reason: '录音已停止（HUD 已收起，这段未保存）' } }))
})

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

/**
 * 形态只由 CSS 表达 —— 窗口常驻工作区，一次都不缩。
 *
 * 参照稿（reality-raid-hud-*）是 100vw×100vh 的舞台：岛、舱、左轨都在同一张画布上演，
 * 没有任何「改窗口大小」的动作。早先为了"不占中央桌面"把窗口缩成岛的外包矩形，
 * 代价是 WebView2 每次 resize 都重建合成面：重绘那一瞬整块窗口铺出浅灰底
 * （看着就是岛下面多了一个灰方块），岛的 32px 阴影又被窗口边硬裁成一条直线，
 * 展开/收起时还会闪。改成窗口不动、docked 用 transform 把岛藏到屏幕上沿，
 * 这三样一起消失，动的只有 CSS。
 */
/** 贴顶收起：岛滑出屏幕上沿（CSS 260ms），窗口照旧铺满，穿透交给光标轮询 */
async function applyLip(): Promise<boolean> {
  if (mode.value !== 'idle' || pinned()) return false
  if (geo.value !== 'full') await expandToWorkArea()
  docked.value = true
  geo.value = 'lip'
  persistCollapsed(true)
  return true
}

/** 等窗口真正变成满屏（helmet-shown 早于 WebView resize 时，尺寸还是旧值） */
async function waitForFull(timeout = 1200): Promise<boolean> {
  const t0 = performance.now()
  while (!isFullWindow() && performance.now() - t0 < timeout) {
    await new Promise((r) => setTimeout(r, 40))
  }
  return isFullWindow()
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
 * 窗口几何唯一出口：永远铺满工作区，不随形态伸缩（见 applyBand 的注释）。
 * 形态（idle / deck / chat / 浮层 / 开场）只切 CSS 状态；
 * 穿透由光标轮询按 .hit 命中决定——满窗也不挡桌面点击。
 */
async function syncWindow() {
  if (!isTauri()) return
  await expandToWorkArea()
  if (bootActive.value) {
    // 开场要能点一下跳过：整窗接事件
    stopPoll()
    await setIgnore(false)
    return
  }
  // docked/geo 由 applyBand/applyLip/reveal 维护，这里不覆盖
  startPoll()
}

async function syncAfterShape() {
  hoursOpen.value = false
  await nextTick()
  await syncWindow()
  try {
    localStorage.setItem(LS_OLD_COLLAPSE, !deckOn.value && !chatOn.value ? '1' : '0')
  } catch {
    /* ignore */
  }
  if (deckOn.value || chatOn.value) {
    debugText.value = ''
    void refreshBadges()
  } else {
    scheduleHide()
  }
}

/**
 * 形态切换：'chat' 只开对话舱，'deck' 只开 HUD 壳，'idle' 只收 HUD 壳。
 * 收起对话请走 closeChat()，不要用 setMode('idle')——那会把已开面板一起收掉。
 */
async function setMode(next: Mode) {
  if (next === 'chat') {
    if (chatOn.value) return
    chatOn.value = true
    await syncAfterShape()
    return
  }
  if (next === 'deck') {
    if (deckOn.value) return
    deckOn.value = true
    await syncAfterShape()
    return
  }
  if (!deckOn.value) return
  deckOn.value = false
  await syncAfterShape()
}

function openPanel(raw: PanelKey | 'sticky' | 'countdown') {
  // 老入口（快捷键/脚本/舱内直达）还可能传 sticky / countdown：便签 → 笔记·便签筛选；倒计时 → 设置·小岛
  let key: PanelKey
  if (raw === 'sticky') {
    notesView.value = 'sticky'
    key = 'notes'
  } else if (raw === 'countdown') {
    settingsTab.value = 'island'
    key = 'settings'
  } else {
    key = PANEL_KEYS.includes(raw) ? raw : 'todos'
  }
  panel.value = key
  if (!deckOn.value) void setMode('deck')
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

/** 左栏「搜索」：打开搜索三栏（结果按待办/笔记分组 + 预览），焦点给列表栏顶部的搜索框 */
async function focusSearch() {
  openPanel('search')
  for (let i = 0; i < 8; i++) {
    await nextTick()
    const el = document.querySelector<HTMLInputElement>('[data-search-input]')
    if (el) {
      el.focus()
      el.select()
      if (document.activeElement === el) return
    }
    await new Promise((r) => setTimeout(r, 40))
  }
}

/** 岛上 ⚙：上下班时间在「设置 · 小岛」里配（不再弹岛下浮层） */
function openIslandSettings() {
  settingsTab.value = 'island'
  openPanel('settings')
}

/** 岛右侧 ▾/▴：唯一的 HUD 壳展开/收起入口（不管对话舱） */
function onToggleHud() {
  if (deckOn.value) void setMode('idle')
  else void openPanel(panel.value)
}

/** 点岛主体（品牌/灯/日衰区）→ 打开或聚焦对话舱；⚙ 与 ▾ 各自 stop，不落到这里 */
function onIslandClick(e: MouseEvent) {
  const t = e.target as HTMLElement | null
  if (
    t &&
    (t.closest('.island-toggle') ||
      t.closest('.island-gear') ||
      t.closest('.island-chat') ||
      t.closest('.island-act'))
  )
    return
  if (chatOn.value) return
  void setMode('chat')
}

/** 只收对话舱：HUD 壳、左轨、已开功能面板保持 */
function closeChat() {
  if (!chatOn.value) return
  chatOn.value = false
  chatIdleSince = 0
  void syncAfterShape()
}

/** 键盘焦点是否还在岛或对话舱内（输入框 / 舱内控件）。在则不因指针移开而自动收舱。 */
function cabinKeyboardFocus(): boolean {
  // 切到桌面后 WebView 仍保留 activeElement，但它已不再持有键盘焦点。
  if (!document.hasFocus()) return false
  const el = document.activeElement as HTMLElement | null
  if (!el || el === document.body || el === document.documentElement) return false
  return !!el.closest('.island-chat, .island')
}

/** 指针是否落在岛（含紧凑脸）或可见对话卡片的外框内。两块合起来才是计时区。 */
function cursorOverCabinBlock(lx: number, ly: number): boolean {
  for (const sel of ['.island', '.island-chat']) {
    const el = document.querySelector(sel) as HTMLElement | null
    if (!el) continue
    const cs = getComputedStyle(el)
    if (cs.visibility === 'hidden' || cs.display === 'none') continue
    const r = el.getBoundingClientRect()
    if (r.width <= 0 || r.height <= 0) continue
    if (lx >= r.left && lx <= r.right && ly >= r.top && ly <= r.bottom) return true
  }
  return false
}

let chatIdleSince = 0

/** 离开岛+舱满 5s 且舱内无焦点 → 只收对话。回到岛/舱或重新获得焦点则清零。 */
function tickChatIdle(pos: [number, number] | null) {
  if (!chatOpen.value) {
    chatIdleSince = 0
    return
  }
  if (cabinKeyboardFocus()) {
    chatIdleSince = 0
    return
  }
  if (pos && cursorOverCabinBlock(pos[0], pos[1])) {
    chatIdleSince = 0
    return
  }
  const now = performance.now()
  if (!chatIdleSince) chatIdleSince = now
  if (now - chatIdleSince >= CHAT_IDLE_MS) {
    chatIdleSince = 0
    closeChat()
  }
}

/** 左轨「聊天」：展开或聚焦对话舱，不用对话替换当前面板 */
function onRailChat() {
  if (!chatOn.value) {
    void setMode('chat')
    return
  }
  void nextTick(() => document.querySelector<HTMLTextAreaElement>('.composer textarea')?.focus())
}

/** 对话 + 面板同时开时，把岛/舱挪到左轨面板右侧，避免挡住列表/输入/收起控件 */
const besideDock = computed(() => chatOpen.value && deckOpen.value)
const besideLeft = ref(0)
const besideStyle = computed(() => {
  if (!besideDock.value) return undefined
  return {
    left: `${besideLeft.value}px`,
    transform: 'none',
    '--beside-left': `${besideLeft.value}px`,
  } as Record<string, string>
})
let dockRo: ResizeObserver | null = null

function measureBeside() {
  if (!besideDock.value) {
    besideLeft.value = 0
    return
  }
  const dock = document.querySelector('.hud.is-open .dock') as HTMLElement | null
  const right = dock ? dock.getBoundingClientRect().right : 0
  besideLeft.value = Math.max(0, Math.round(right + 16))
}

/** 已开功能面板时，可见对话卡片（.island-chat，从顶栏到输入栏）与该面板可见外框顶对齐、底对齐、同高。
 *  对齐的是这张卡片本身，不是包含岛 / 快捷入口 / 空隙的包裹层。无面板则回到默认高度。岛位置不变。 */
const cabinAlignOn = ref(false)
const cabinAlignVars = ref<Record<string, string>>({})
const wrapLayoutStyle = computed(() => {
  const base = besideStyle.value ?? {}
  return { ...base, ...cabinAlignVars.value }
})

function measureCabinAlign() {
  if (!chatOpen.value || !deckOpen.value) {
    cabinAlignOn.value = false
    cabinAlignVars.value = {}
    return
  }
  const panelEl = document.querySelector('.hud.is-open .panel-col') as HTMLElement | null
  const island = islandEl.value
  if (!panelEl || !island) {
    cabinAlignOn.value = false
    cabinAlignVars.value = {}
    return
  }
  const pr = panelEl.getBoundingClientRect()
  const ir = island.getBoundingClientRect()
  if (pr.height < 40) {
    cabinAlignOn.value = false
    cabinAlignVars.value = {}
    return
  }
  // 相对 .island（position:relative）定位可见卡片，使其顶/底与面板可见外框重合。
  const top = Math.round(pr.top - ir.top)
  const h = Math.max(1, Math.round(pr.height))
  cabinAlignOn.value = true
  cabinAlignVars.value = {
    '--cabin-align-top': `${top}px`,
    '--cabin-align-h': `${h}px`,
  }
}

function layoutDockAndCabin() {
  measureBeside()
  measureCabinAlign()
}

function bindDockObserver() {
  dockRo?.disconnect()
  dockRo = null
  const dock = document.querySelector('.hud.is-open .dock')
  const panelEl = document.querySelector('.hud.is-open .panel-col')
  if (typeof ResizeObserver !== 'undefined' && (dock || panelEl)) {
    dockRo = new ResizeObserver(() => layoutDockAndCabin())
    if (dock) dockRo.observe(dock)
    if (panelEl && panelEl !== dock) dockRo.observe(panelEl)
  }
  layoutDockAndCabin()
}

watch([besideDock, panel, chatOpen, deckOpen], () => {
  void nextTick(() => {
    bindDockObserver()
  })
})

/** Esc / 快捷键收起：立即贴顶只剩唇边 + 顶部热区，绝不隐藏整个 helmet */
async function collapseNow() {
  if (mode.value !== 'idle' || pinned()) return
  const ok = await applyLip()
  if (!ok) return
  startPoll()
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
  // 轮询必须继续：窗是满的，顶边那 10px 热区要靠它关掉穿透才能收到唤出；
  // 其余位置由它保持穿透，桌面照常可点。
  startPoll()
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

/** 顶部热区 / 岛被指到：岛从屏幕上沿滑下来（窗口不动） */
async function reveal() {
  if (docked.value) outSince = 0
  if (!docked.value || localState) return
  localState = true
  try {
    docked.value = false
    persistCollapsed(false)
    geo.value = 'band'
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
  // 原版全局搜索是 Teleport 到 body 的模态，不在 rootEl 里；命中表要把它算上，
  // 否则弹窗区域会被判成「非控件」→ 穿透开 → 点不动
  const hits = [
    ...root.querySelectorAll<HTMLElement>('.hit'),
    // 任何 Teleport 到 body 的原版弹窗（搜索卡片 / 新建倒计时 .modal-card / 以后别的）
    ...document.querySelectorAll<HTMLElement>('.modal-mask > *'),
  ]
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
  // 满窗常驻后，idle 也必须轮询：岛四周与整个中央都是透明的，
  // 光标不在任何 .hit 上时必须保持穿透，否则整屏都挡桌面点击。
  if (bootActive.value) return
  try {
    const pos = await invoke<[number, number] | null>('helmet_cursor_local')
    if (!pos) {
      await setIgnore(true)
      tickChatIdle(null)
      return
    }
    await setIgnore(!cursorOverHit(pos[0], pos[1]))
    tickChatIdle(pos)
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

/** 落盘值：平台入口存 PLATFORM_ENTRY_NAME（内部标识），自备模型存名字 */
function modelValue(m: ChatModelConfig): string {
  return isPlatformModel(m) ? PLATFORM_ENTRY_NAME : m.name
}
function modelLabel(m: ChatModelConfig): string {
  return displayModelName(modelValue(m))
}

async function loadSettings() {
  if (!isTauri()) return
  try {
    if (!store.state.loaded) {
      try {
        await store.loadInitialData()
      } catch {
        /* 小岛提示音等依赖 config；失败时保持默认关闭 */
      }
    }
    const cfg = await tauriApi.getUiConfig()
    // 平台入口依赖账号登录：账号功能关着就不列（config/features）
    cfgModels.value = (cfg.chat_models || []).filter((m) => FEATURES.account || !isPlatformModel(m))
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
    showToast(`聊天模型已存：${displayModelName(name) || '未设置'}`)
  } catch (e) {
    showToast('模型保存失败')
    console.warn('[helmet] set_chat_selected_model failed', e)
  }
}

function toggleCountdownSound() {
  void store.setCountdownSound(!store.state.config.countdown_sound)
}

/* ------------------------------------------------------------------ */
/* 搜索（待办 + 笔记 + 速达，一处直达）                                */
/* ------------------------------------------------------------------ */

const q = ref('')
/** 笔记面板当前视图：笔记 / 便签（便签并入笔记的列表筛选） */
const notesView = ref<'notes' | 'sticky'>('notes')

function clearSearch() {
  q.value = ''
}

function openNoteFromSearch(id: number) {
  notesView.value = 'notes'
  openPanel('notes')
  pendingNoteId.value = id
}

function openTodoFromSearch(id: number) {
  pendingTodoId.value = id
  openPanel('todos')
}

/* 剪贴板「插入」：对话舱开着 → 填进舱输入框（草稿，不发送）；否则收起 HUD、粘贴到上一个窗口 */
async function onClipInsert(item: ClipboardItem) {
  if (chatOn.value) {
    if (item.kind !== 'text') {
      try {
        await tauriApi.clipboardCopy(item.id)
      } catch {
        /* ignore */
      }
      showToast('对话里不发图片：已复制到剪贴板')
      return
    }
    window.dispatchEvent(new CustomEvent('hud-cabin-insert', { detail: { text: item.content } }))
    showToast('已填进对话输入框（未发送）')
    return
  }
  await setMode('idle')
  try {
    await tauriApi.clipboardPaste(item.id)
  } catch (e) {
    showToast('插入失败：' + String(e).slice(0, 60))
  }
}

/* ------------------------------------------------------------------ */
/* 宽度：三栏面板有上限，中央桌面始终留出可点区域；与对话舱同开时窄屏把详情收进列表 */
/* ------------------------------------------------------------------ */
const vw = ref(typeof window !== 'undefined' ? document.documentElement.clientWidth : 1600)
/** 中央桌面至少留这么宽（CSS px）给用户点 */
const CENTER_RESERVE = 220
const TRI_MAX = 960
const panelMaxW = computed(() => {
  const chat = chatOpen.value ? 420 + 16 : 0
  return Math.max(360, Math.min(TRI_MAX, vw.value - 14 - 72 - 16 - chat - CENTER_RESERVE))
})
/** 列表 + 详情两栏放不下（< 680）时进窄屏：详情收进列表，点条目 push 出来 */
const hudNarrow = computed(() => panelMaxW.value < 680)
provide('hudNarrow', hudNarrow)

/* 岛上的倒计时：取最近一个未结束的，一眼可见（配置仍在原版倒计时数据里，不另开面板） */
const countdowns = ref<Countdown[]>([])
async function refreshCountdowns() {
  if (!isTauri()) return
  try {
    countdowns.value = await tauriApi.listCountdowns()
  } catch {
    countdowns.value = []
  }
}
const nextCountdown = computed(() => {
  const now = nowMs.value
  const live = countdowns.value.filter((c) => !c.finished && (c.paused || c.end_at > now))
  live.sort((a, b) => (a.paused ? Infinity : a.end_at) - (b.paused ? Infinity : b.end_at))
  return live[0] ?? null
})
const countdownLabel = computed(() => {
  const c = nextCountdown.value
  if (!c) return ''
  const left = c.paused ? c.paused_remaining_ms ?? 0 : c.end_at - nowMs.value
  const m = Math.max(0, Math.round(left / 60000))
  const txt = m >= 1440 ? `${Math.floor(m / 1440)}天` : m >= 60 ? `${Math.floor(m / 60)}h${m % 60 ? (m % 60) + 'm' : ''}` : `${m}m`
  return `${c.name} ${txt}`
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

// 挂进来的原版组件（TodoView 等）用 inject('showToast') 弹提示，接到壳的 toast 上
provide('hudToast', showToast)
// 原版组件（设置/AI 面板等）注入的是 'showToast'，转同一个提示出口，
// 否则它们的保存/失败提示会被静默吞掉。
provide('showToast', showToast)

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
    // 总开关只管 HUD 壳：已展开 → 收起；只在岛/唇边 → 展开上次的面板。对话舱不动。
    if (deckOn.value) await setMode('idle')
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
    // 原版全局搜索（分组结果 + 键盘上下选 + 回车打开），直接挂原版弹窗
    await focusSearch()
    return
  }
}

/* ------------------------------------------------------------------ */
/* 键盘                                                                */
/* ------------------------------------------------------------------ */

/** 关最上层原版弹层：优先 × / 关闭，其次「取消」；都没有就不动（不误删内容） */
function closeTopModal() {
  const sheets = document.querySelectorAll<HTMLElement>('[data-inline-sheet]')
  const masks = document.querySelectorAll<HTMLElement>('.modal-mask')
  const top = sheets[sheets.length - 1] ?? masks[masks.length - 1]
  if (!top) return
  const btns = [...top.querySelectorAll<HTMLButtonElement>('button')]
  const pick =
    top.querySelector<HTMLButtonElement>('.te-close, .modal-close, [data-close], button[aria-label="关闭"]') ||
    btns.find((b) => ['取消', '关闭', '×', '✕'].includes((b.textContent || '').trim()))
  pick?.click()
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Tab') keyboardNav.value = true
  if (bootActive.value && (e.key === 'Enter' || e.key === 'Escape' || e.key === ' ')) {
    e.preventDefault()
    endBoot()
    return
  }
  // 选区层开着时，Esc 先归选区层：HUD 这时是隐藏但仍持焦的，
  // 不接管的话 Overlay 自己的 keydown 根本收不到，用户会觉得 Esc 失灵。
  if (capturing.value && e.key === 'Escape') {
    e.preventDefault()
    void closeCapture()
    return
  }
  if (e.key === 'Escape') {
    e.preventDefault()
    // 原版弹层（待办编辑 / 倒计时 / 速达编辑…）开着：Esc 只关弹层，不动 HUD。
    // 弹层自己处理了 Esc 就已经没了；还在的话替它点关闭/取消（遮罩不接点击，见 hud-kit.css）
    if (document.querySelector('.modal-mask, [data-inline-sheet]')) {
      window.setTimeout(() => closeTopModal(), 0)
      return
    }
    if (hoursOpen.value) {
      hoursOpen.value = false
      return
    }
    if (panel.value === 'search' && deckOn.value && q.value) {
      clearSearch()
      return
    }
    if (chatOn.value) {
      closeChat()
      return
    }
    if (deckOn.value) {
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
    void focusSearch()
    return
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
  // 速达里点「网页」资源：原版 store 会派发 suda-open-web-panel，交给主窗的
  // suda-web 视图去渲染内嵌面板。那个面板是 main 窗的子 webview（main.add_child），
  // 在 HUD 里没有 main 窗可供挂靠 —— 所以壳这边把它转成「应用内浏览器窗口」
  //（原版同一套池窗口 suda-web-{i} + BrowserChrome，标签页/地址栏/前进后退都在）。
  window.addEventListener('suda-open-web-panel', onSudaOpenPanel as EventListener)
  unlisteners.push(() =>
    window.removeEventListener('suda-open-web-panel', onSudaOpenPanel as EventListener),
  )
  if (isTauri()) {
    // 选区层 hide_overlay() 里的全局广播（截图完成 / Esc 取消都会走到）
    void listen('recorder-overlay-hidden', () => endCapture()).then((un) =>
      unlisteners.push(un),
    )
  }
  window.addEventListener('pointerdown', onPointerDownAny, true)
  window.addEventListener('pointermove', onAnyPointerMove, { passive: true })
  nowMs.value = Date.now()
  const tick = window.setInterval(() => (nowMs.value = Date.now()), 15000)
  unlisteners.push(() => window.clearInterval(tick))
  void refreshCountdowns()
  const cdTick = window.setInterval(() => void refreshCountdowns(), 60000)
  unlisteners.push(() => window.clearInterval(cdTick))
  const onWinResize = () => {
    vw.value = document.documentElement.clientWidth
    layoutDockAndCabin()
  }
  window.addEventListener('resize', onWinResize)
  unlisteners.push(() => window.removeEventListener('resize', onWinResize))

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
  dockRo?.disconnect()
  dockRo = null
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

defineExpose({ openPanel, setMode })
</script>

<template>
  <div
    ref="rootEl"
    class="helmet-root"
    :class="{
      ready,
      'no-anim': noAnim,
      'island-docked': docked,
      compact: geo !== 'full',
      'is-capturing': capturing,
    }"
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
    <div
      ref="wrapEl"
      class="island-wrap"
      :class="{ 'is-beside-dock': besideDock, 'is-align-panel': cabinAlignOn }"
      :style="wrapLayoutStyle"
      @focusin="onFocusIn"
      @focusout="onFocusOut"
    >
      <div
        ref="islandEl"
        class="island hit"
        :class="{ 'is-chat': chatOpen, 'is-align-panel': cabinAlignOn }"
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
            <span class="cn">shell-hub</span>
            <span class="en">{{ chatOpen ? 'GENERAL AI · LOCAL' : '点击打开对话' }}</span>
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
          <!-- 倒计时一眼可见（P1-3：不再单开面板）：最近一个未结束的倒计时 -->
          <span v-if="countdownLabel && !chatOpen" class="island-cd" data-island-countdown :title="`倒计时 · ${countdownLabel}`">
            ⏱ {{ countdownLabel }}
          </span>
          <!-- 截图 / 录屏：唤起原版全屏选区层（recorder-overlay 窗由后端预创建） -->
          <button
            class="island-act hit"
            type="button"
            data-act="shot"
            title="区域截图（原版选区层：框选后可标注，出图进剪贴板）"
            aria-label="区域截图"
            @click.stop="openCapture('shot')"
          >
            ⌗
          </button>
          <button
            class="island-act hit"
            type="button"
            data-act="record"
            title="GIF 录屏（原版选区层：框选后设帧率与时长）"
            aria-label="GIF 录屏"
            @click.stop="openCapture('record')"
          >
            ◉
          </button>
          <button
            class="island-gear"
            type="button"
            title="上下班时间（设置 · 小岛）"
            aria-label="设定上下班时间"
            data-island-hours
            @click.stop="openIslandSettings"
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

        <HelmetChatCabin
          v-if="chatOpen"
          @close="closeChat"
          @toast="showToast"
        />
      </div>

    </div>

    <!-- ******************************************** 躯干：左轨 + 面板（无右栏、无底栏） -->
    <div class="hud" :class="{ 'is-open': deckOpen }" :aria-hidden="!deckOpen">
      <div class="dock">
        <nav class="rail panel hit" aria-label="shell-hub 模块">
          <pre class="ascii-bg is-rail" aria-hidden="true">{{ asciiRail }}</pre>
          <span class="rail-cap">OPS</span>
          <button
            class="nav-btn"
            data-nav="chat"
            :class="{ 'is-on': chatOpen }"
            title="聊天"
            aria-label="聊天"
            @click="onRailChat"
          >
            <span class="lab">聊天</span>
          </button>
          <button
            class="nav-btn"
            data-nav="todos"
            :class="{ 'is-on': panel === 'todos' && deckOpen }"
            title="待办"
            aria-label="待办"
            @click="openPanel('todos')"
          >
            <span class="badge" :class="{ 'is-zero': todoCount === 0 }">{{ todoCount }}</span>
            <span class="lab">待办</span>
          </button>
          <button
            class="nav-btn"
            data-nav="notes"
            :class="{ 'is-on': panel === 'notes' && noteListOpen }"
            title="笔记"
            aria-label="笔记"
            @click="toggleNotes"
          >
            <span class="lab">笔记</span>
          </button>
          <button
            class="nav-btn"
            data-nav="clipboard"
            :class="{ 'is-on': panel === 'clipboard' && deckOpen }"
            title="剪贴板"
            aria-label="剪贴板"
            @click="openPanel('clipboard')"
          >
            <span class="badge" :class="{ 'is-zero': clipCount === 0 }">{{ clipCount }}</span>
            <span class="lab">剪贴板</span>
          </button>
          <button
            class="nav-btn"
            data-nav="launch"
            :class="{ 'is-on': panel === 'launch' && deckOpen }"
            title="启动常用工具"
            aria-label="启动"
            @click="openPanel('launch')"
          >
            <span class="lab">启动</span>
          </button>
          <button
            class="nav-btn"
            data-nav="search"
            :class="{ 'is-on': panel === 'search' && deckOpen }"
            title="搜索"
            aria-label="搜索"
            @click="focusSearch"
          >
            <span class="lab">搜索</span>
          </button>
          <span class="rail-sep" aria-hidden="true" />
          <button
            class="nav-btn"
            data-nav="settings"
            :class="{ 'is-on': panel === 'settings' && deckOpen }"
            title="设置"
            aria-label="设置"
            @click="openPanel('settings')"
          >
            <span class="lab">设置</span>
          </button>
        </nav>

        <aside
          class="panel-col panel hit"
          :class="{ 'is-tri': true, 'is-narrow': hudNarrow }"
          :style="{ width: `${panelMaxW}px` }"
          :data-tri-w="panelMaxW"
          aria-label="shell-hub 面板"
        >
          <pre class="ascii-bg is-work" aria-hidden="true">{{ asciiPanel }}</pre>
          <div v-if="panel === 'todos'" class="work"><HelmetTodoTri /></div>
          <HelmetNotesFullPanel v-if="panel === 'notes'" v-model:view="notesView" />
          <div v-if="panel === 'clipboard'" class="work"><HelmetClipTri @insert="onClipInsert" /></div>
          <div v-if="panel === 'search'" class="work">
            <HelmetSearchTri v-model="q" @open-todo="openTodoFromSearch" @open-note="openNoteFromSearch" />
          </div>
          <HelmetSudaPanel v-if="panel === 'launch'" />
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
            <div class="work-bd is-settings">
              <HelmetSettingsFullPanel v-model:tab="settingsTab">
                <template #island>
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
                      <option v-for="m in cfgModels" :key="m.id" :value="modelValue(m)">
                        {{ modelLabel(m) }}
                      </option>
                    </select>
                  </div>
                </div>
                <div class="set-acts">
                  <span class="hint">{{ displayModelName(modelPick) || '未设置' }} · {{ cfgModels.length }} 个可用</span>
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
              <div class="set-block">
                <h4>倒计时到点提示音</h4>
                <p class="set-note">岛上倒计时到点时额外播放提示音（默认关闭）。</p>
                <div class="set-acts">
                  <span class="hint">{{ store.state.config.countdown_sound ? '已开启' : '已关闭' }}</span>
                  <button class="btn sm cut-sm" type="button" @click="toggleCountdownSound">
                    {{ store.state.config.countdown_sound ? '关闭' : '开启' }}
                  </button>
                </div>
              </div>
                </template>
              </HelmetSettingsFullPanel>
            </div>
          </div>
        </aside>

        <!-- 第三栏：笔记编辑（点中栏条目才出现，可单独收起） -->
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