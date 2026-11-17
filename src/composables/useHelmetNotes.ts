/**
 * shell-hub · 笔记三栏共享状态
 *
 * 形态照抄产品批准稿 `.refs/shell-hub-notes-3col-explore.html`：
 *   左功能栏 → 点「笔记」开中栏列表 → 点条目开右栏编辑；可新建 / 切换 / 分层收起。
 *
 * 中栏（列表）与右栏（编辑）是两个独立列、两个组件，所以状态放模块级单例，
 * 不用父子传参把栏位耦合死。数据仍是 x-hub `notes` 表
 * （list_notes / get_note / create_note / update_note / trash_note）。
 */
import { computed, ref, watch } from 'vue'
import { isTauri, tauriApi, type Note } from '../api/tauri'

export type NoteSaveState = 'idle' | 'dirty' | 'saving' | 'saved'

/** 自动保存延迟：与旧单栏笔记面板一致，避免每敲一个字写一轮库 */
const SAVE_DELAY = 700

const notes = ref<Note[]>([])
const activeId = ref<number | null>(null)
const title = ref('')
const content = ref('')
const status = ref<NoteSaveState>('idle')
const err = ref('')
/** 载入笔记时抑制 watch → 自动保存（否则打开即写一轮库） */
const loading = ref(false)
const loaded = ref(false)
const listOpen = ref(false)
const editorOpen = ref(false)
const filter = ref('')

let timer: number | null = null
/** 切换/连点保护：只为最后一次点名回填编辑器 */
let openSeq = 0

const pad2 = (n: number) => String(n).padStart(2, '0')

/** 列表行的时间戳（与探索稿同口径：YYYY-MM-DD HH:mm） */
export function noteTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`
}

/** 列表行的一行摘要：压平空白，空正文给占位 */
export function noteSummary(text: string | null | undefined): string {
  const flat = (text || '').replace(/\s+/g, ' ').trim()
  return flat || '（无正文）'
}

const live = computed(() => notes.value.filter((n) => !n.deleted_at))
const ordered = computed(() =>
  live.value.slice().sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1)),
)
const filtered = computed(() => {
  const q = filter.value.trim().toLowerCase()
  if (!q) return ordered.value
  return ordered.value.filter((n) => `${n.title} ${n.content}`.toLowerCase().includes(q))
})
const active = computed(() => live.value.find((n) => n.id === activeId.value) ?? null)

async function load(force = false) {
  if (!isTauri()) return
  if (loaded.value && !force) return
  try {
    notes.value = await tauriApi.listNotes()
    loaded.value = true
    err.value = ''
    if (activeId.value != null && !notes.value.some((n) => n.id === activeId.value && !n.deleted_at)) {
      activeId.value = null
      editorOpen.value = false
    }
  } catch (e) {
    err.value = String(e)
  }
}

/** 打开一篇笔记 → 右栏编辑；中栏列表保持展开（两栏并存是本次交互的重点） */
async function open(id: number) {
  if (activeId.value === id) {
    listOpen.value = true
    editorOpen.value = true
    return
  }
  await flush()
  const seq = ++openSeq
  loading.value = true
  try {
    const n = await tauriApi.getNote(id)
    // 等待期间用户可能已改点别的条目：只认最后一次
    if (!n || seq !== openSeq) return
    activeId.value = n.id
    title.value = n.title
    content.value = n.content
    status.value = 'idle'
    listOpen.value = true
    editorOpen.value = true
  } catch (e) {
    err.value = String(e)
  } finally {
    if (seq === openSeq) loading.value = false
  }
}

async function createNew() {
  // 先清掉上一条笔记的延迟保存：否则旧计时器会把「新建的空壳」写回库，吃掉刚输入的内容
  if (timer != null) {
    window.clearTimeout(timer)
    timer = null
  }
  await flush()
  loading.value = true
  try {
    const n = await tauriApi.createNote('未命名笔记')
    notes.value = [n, ...notes.value]
    activeId.value = n.id
    title.value = n.title
    content.value = n.content
    status.value = 'idle'
    filter.value = ''
    listOpen.value = true
    editorOpen.value = true
  } catch (e) {
    err.value = String(e)
  } finally {
    loading.value = false
  }
}

function schedule() {
  status.value = 'dirty'
  if (timer != null) window.clearTimeout(timer)
  const id = activeId.value
  timer = window.setTimeout(() => void save(id), SAVE_DELAY)
}

async function save(id: number | null = activeId.value): Promise<boolean> {
  if (id == null || id !== activeId.value) return false
  if (timer != null) {
    window.clearTimeout(timer)
    timer = null
  }
  status.value = 'saving'
  try {
    const nextTitle = title.value.trim() || '未命名笔记'
    await tauriApi.updateNote(id, nextTitle, content.value)
    const n = notes.value.find((x) => x.id === id)
    if (n) {
      n.title = nextTitle
      n.content = content.value
      n.updated_at = new Date().toISOString()
    }
    status.value = 'saved'
    return true
  } catch (e) {
    err.value = String(e)
    status.value = 'dirty'
    return false
  }
}

async function flush() {
  if (status.value === 'dirty' || status.value === 'saving') await save()
}

/** 显式保存（右栏「保存」按钮）：脏才写，返回是否落盘成功 */
async function saveNow(): Promise<boolean> {
  if (activeId.value == null) return false
  return save()
}

/** 删除 = 移入回收站（可恢复），不硬删 */
async function removeActive(): Promise<boolean> {
  const id = activeId.value
  if (id == null) return false
  if (timer != null) {
    window.clearTimeout(timer)
    timer = null
  }
  status.value = 'idle'
  try {
    await tauriApi.trashNote(id)
    notes.value = notes.value.filter((n) => n.id !== id)
    activeId.value = null
    title.value = ''
    content.value = ''
    editorOpen.value = false
    return true
  } catch (e) {
    err.value = String(e)
    return false
  }
}

function openList() {
  listOpen.value = true
  void load()
}

/** 分层收起第一层：中栏收起，右栏跟着收起（探索稿口径） */
async function closeList() {
  await flush()
  listOpen.value = false
  editorOpen.value = false
  activeId.value = null
  title.value = ''
  content.value = ''
  status.value = 'idle'
}

/** 分层收起第二层：只收右栏，中栏留着继续切换 */
async function closeEditor() {
  await flush()
  editorOpen.value = false
  activeId.value = null
  status.value = 'idle'
}

watch([title, content], () => {
  if (activeId.value != null && !loading.value) schedule()
})

export function useHelmetNotes() {
  return {
    notes,
    activeId,
    title,
    content,
    status,
    err,
    loading,
    listOpen,
    editorOpen,
    filter,
    active,
    filtered,
    live,
    load,
    open,
    createNew,
    save,
    saveNow,
    flush,
    removeActive,
    openList,
    closeList,
    closeEditor,
  }
}