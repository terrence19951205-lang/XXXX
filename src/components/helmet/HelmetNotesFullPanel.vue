<script setup lang="ts">
/**
 * Helmet · 笔记（直接挂 x-hub 原版 SpeednoteView）
 *
 * 原版速记视图（550 行）＝ 文件夹树（树 + 搜索 + 标签筛选 + 回收站三种形态）
 * + 编辑器同位分流（Markdown 用 NoteEditor / 表格用 SheetEditor），
 * 编辑、软删回收站、导出（md/txt/pdf/sheet）、AI 美化、双链都在里面。
 *
 * P1-3：便签并入笔记——列表顶部多一个筛选「笔记 / 便签」，便签不再单独占左轨。
 * 便签数据仍是原版 stickies / detached_stickies 两张表（slot 1/2），只换入口，不迁移、不改结构；
 * 已脱离成桌面浮窗的便签读写浮窗那一份，并可一键聚焦浮窗。
 */
import { computed, inject, onBeforeUnmount, onMounted, provide, ref, watch, type Ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { getCurrentWebview } from '@tauri-apps/api/webview'
import { isTauri } from '../../api/tauri'
import SpeednoteView from '../SpeednoteView.vue'
import { useStore } from '../../stores/workbench'
import { pendingNoteId } from './hudBus'
import { useVoiceInput } from '../../composables/useVoiceInput'

const store = useStore()
const narrow = inject<Ref<boolean>>('hudNarrow', ref(false))
const props = defineProps<{ view?: 'notes' | 'sticky' }>()
const emit = defineEmits<{ (e: 'update:view', v: 'notes' | 'sticky'): void }>()
const view = computed({
  get: () => props.view ?? 'notes',
  set: (v) => emit('update:view', v),
})

const sn = ref<InstanceType<typeof SpeednoteView> | null>(null)
/** 搜索「打开笔记」：切到笔记视图并选中那一条（SpeednoteView.openNote 是原版外部入口） */
function consumePending() {
  const id = pendingNoteId.value
  if (id == null || !sn.value) return
  pendingNoteId.value = null
  view.value = 'notes'
  sn.value.openNote(id)
}
watch([pendingNoteId, sn], consumePending)

onMounted(async () => {
  if (!store.state.loaded) {
    try {
      await store.loadInitialData()
    } catch {
      /* 后端未就绪时原版自己显示空态 */
    }
  }
  consumePending()
})

// 原版组件用 inject('showToast') 弹轻提示；壳里已 provide('hudToast')
const hudToast = inject<((msg: string) => void) | null>('hudToast', null)
if (hudToast) provide('showToast', (msg: string) => hudToast(msg))

/* ---------- 录音转文字：插到编辑器光标处（P1-3） ---------- */
/** 编辑器是 Milkdown（ProseMirror contenteditable）：焦点回到编辑区后 insertText，
 *  ProseMirror 会在它记住的选区（即录音前的光标）插入，并走原版自动保存。 */
function insertAtCursor(text: string): boolean {
  const host = document.querySelector<HTMLElement>('.notes-host')
  if (!host) return false
  const act = document.activeElement as HTMLElement | null
  let target: HTMLElement | null = act && host.contains(act) && (act.isContentEditable || act.tagName === 'TEXTAREA') ? act : null
  if (!target) target = host.querySelector<HTMLElement>('.ProseMirror[contenteditable="true"], .ProseMirror, textarea.cm-content, [contenteditable="true"]')
  if (!target) return false
  target.focus()
  if (target.tagName === 'TEXTAREA') {
    const ta = target as HTMLTextAreaElement
    const s = ta.selectionStart ?? ta.value.length
    const e = ta.selectionEnd ?? s
    ta.setRangeText(text, s, e, 'end')
    ta.dispatchEvent(new Event('input', { bubbles: true }))
    return true
  }
  return document.execCommand('insertText', false, text)
}
const voice = useVoiceInput({
  owner: 'notes',
  onText: (text) => {
    if (insertAtCursor(text)) hudToast?.('已插入到光标处')
    else hudToast?.('没有打开的笔记：先选一条笔记再录音')
  },
  toast: (m) => hudToast?.(m),
})
watch(view, (v) => {
  if (v !== 'notes') voice.cancel('录音已停止（已切到便签）')
})

/* ---------- 拖入图片（P1-3）：原生拖放 → 读文件 → 合成一次「粘贴图片」交给编辑器 ---------- */
const dropHint = ref(false)
let unDrop: (() => void) | null = null
function editorEl(): HTMLElement | null {
  return document.querySelector<HTMLElement>('.notes-host .ProseMirror')
}
function overEditor(pos: { x: number; y: number }): boolean {
  const el = editorEl()
  if (!el) return false
  const r = el.closest<HTMLElement>('.milkdown, .note-editor, .editor-wrap')?.getBoundingClientRect() ?? el.getBoundingClientRect()
  const s = window.devicePixelRatio || 1
  const x = pos.x / s
  const y = pos.y / s
  return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom
}
async function pasteFiles(files: File[]) {
  const el = editorEl()
  if (!el) {
    hudToast?.('先打开一条笔记再拖入图片')
    return
  }
  el.focus()
  const dt = new DataTransfer()
  for (const f of files) dt.items.add(f)
  el.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }))
}
onMounted(async () => {
  if (!isTauri()) return
  try {
    unDrop = await getCurrentWebview().onDragDropEvent(async (event) => {
      if (view.value !== 'notes') return
      const ev = event.payload
      if (ev.type === 'enter' || ev.type === 'over') {
        dropHint.value = 'position' in ev ? overEditor(ev.position) : dropHint.value
        return
      }
      if (ev.type === 'leave') {
        dropHint.value = false
        return
      }
      if (ev.type !== 'drop') return
      const hit = dropHint.value || overEditor(ev.position)
      dropHint.value = false
      if (!hit) return
      const imgs = ev.paths.filter((p) => /\.(png|jpe?g|webp|bmp|gif)$/i.test(p))
      if (!imgs.length) {
        hudToast?.('笔记里只支持拖入图片')
        return
      }
      const files: File[] = []
      for (const p of imgs.slice(0, 6)) {
        try {
          const r = await invoke<{ b64: string; mime: string; name: string }>('read_drop_image', { path: p })
          const bin = Uint8Array.from(atob(r.b64), (c) => c.charCodeAt(0))
          files.push(new File([bin], r.name, { type: r.mime }))
        } catch (e) {
          hudToast?.(String(e).slice(0, 80))
        }
      }
      if (files.length) await pasteFiles(files)
    })
  } catch {
    /* 拖放事件不可用时静默 */
  }
})
onBeforeUnmount(() => unDrop?.())

/* ---------- 便签（slot 1 / 2） ---------- */
const SLOTS = [1, 2]
const stickySlot = ref<number | null>(null)
function isDetached(slot: number) {
  return store.state.detached.some((d) => d.slot === slot)
}
function stickyContent(slot: number): string {
  if (isDetached(slot)) return store.state.detached.find((d) => d.slot === slot)?.content ?? ''
  return store.state.stickies.find((s) => s.slot === slot)?.content ?? ''
}
function stickyUpdated(slot: number): string {
  const s = isDetached(slot)
    ? store.state.detached.find((d) => d.slot === slot)
    : store.state.stickies.find((x) => x.slot === slot)
  return s?.updated_at ?? ''
}
const stickyCount = computed(() => SLOTS.filter((s) => stickyContent(s).trim()).length)
const draft = ref('')
let saveTimer: number | null = null
watch(
  [stickySlot, view],
  () => {
    if (view.value === 'sticky' && stickySlot.value == null && !narrow.value) stickySlot.value = 1
    draft.value = stickySlot.value != null ? stickyContent(stickySlot.value) : ''
  },
  { immediate: true },
)
async function flush() {
  if (saveTimer != null) {
    window.clearTimeout(saveTimer)
    saveTimer = null
  }
  const slot = stickySlot.value
  if (slot == null || draft.value === stickyContent(slot)) return
  try {
    if (isDetached(slot)) {
      await store.saveDetachedSticky(slot, draft.value)
      const d = store.state.detached.find((x) => x.slot === slot)
      if (d) (d as { content: string }).content = draft.value
    } else {
      await store.saveSticky(slot, draft.value)
    }
  } catch (e) {
    hudToast?.('便签保存失败：' + String(e).slice(0, 60))
  }
}
function onInput() {
  if (saveTimer != null) window.clearTimeout(saveTimer)
  saveTimer = window.setTimeout(() => void flush(), 600)
}
async function pickSlot(s: number) {
  await flush()
  stickySlot.value = s
}
async function focusFloat(slot: number) {
  try {
    await store.focusDetachedSticky(slot)
  } catch (e) {
    hudToast?.(String(e).slice(0, 60))
  }
}
function firstLine(s: string) {
  return s.split('\n').find((l) => l.trim())?.trim() || '（空便签）'
}

</script>

<template>
  <div class="work notes-host xhub-host" :data-notes-view="view">
    <div class="notes-filter tri-filter" data-tri-filter>
      <button class="hud-chip" :class="{ 'is-on': view === 'notes' }" data-filter="notes" @click="view = 'notes'">
        笔记 <span class="n">{{ store.state.notes.length }}</span>
      </button>
      <button class="hud-chip" :class="{ 'is-on': view === 'sticky' }" data-filter="sticky" @click="view = 'sticky'">
        便签 <span class="n">{{ stickyCount }}</span>
      </button>
    </div>
    <SpeednoteView v-show="view === 'notes'" ref="sn" />
    <div v-if="dropHint && view === 'notes'" class="note-drop-hint" data-note-drop-hint>松手把图片插到笔记里</div>
    <button
      v-if="view === 'notes'"
      class="hud-btn note-mic mic-btn"
      type="button"
      data-voice="notes"
      :data-voice-state="voice.state.value"
      :class="{ 'is-rec': voice.state.value === 'recording', 'is-busy': voice.state.value === 'transcribing' || voice.state.value === 'asking' }"
      :title="voice.state.value === 'recording' ? '停止录音，转成文字插到光标处' : '语音输入：按一下开始，再按一下结束，文字插到编辑器光标处'"
      :aria-label="voice.state.value === 'recording' ? '停止录音' : '语音输入'"
      :disabled="voice.state.value === 'transcribing'"
      @mousedown.prevent
      @click="voice.toggle()"
    >
      {{ voice.state.value === 'recording' ? `■ 停止 ${voice.elapsed.value}s` : voice.state.value === 'transcribing' ? '转写中…' : voice.state.value === 'asking' ? '等待麦克风授权…' : '🎙 语音' }}
    </button>
    <div
      v-if="view === 'sticky'"
      class="tri tri-sticky"
      :class="{ 'is-narrow': narrow, 'has-detail': narrow && stickySlot != null }"
      data-tri="sticky"
    >
      <section class="tri-list">
        <div class="tri-hd">
          <div class="tri-title">便签 <span class="en">Sticky</span></div>
        </div>
        <div class="tri-scroll">
          <button
            v-for="s in SLOTS"
            :key="s"
            type="button"
            class="tri-row"
            :class="{ 'is-on': stickySlot === s }"
            :data-sticky-slot="s"
            @click="pickSlot(s)"
          >
            <span class="main">
              <span class="t">便签 {{ s }}{{ isDetached(s) ? ' · 桌面浮窗' : '' }}</span>
              <span class="s">{{ firstLine(stickyContent(s)) }}</span>
            </span>
          </button>
        </div>
      </section>
      <section class="tri-detail" data-tri-detail>
        <template v-if="stickySlot != null">
          <div class="tri-hd">
            <button class="hud-btn is-sm tri-back" type="button" data-tri-back @click="flush().then(() => (stickySlot = null))">
              ‹ 返回
            </button>
            <div class="tri-title">便签 {{ stickySlot }} <span class="en">Sticky</span></div>
            <button v-if="isDetached(stickySlot)" class="hud-btn is-sm" type="button" @click="focusFloat(stickySlot)">
              聚焦桌面浮窗
            </button>
          </div>
          <div class="tri-body">
            <textarea
              v-model="draft"
              class="hud-textarea sticky-ta"
              data-sticky-text
              placeholder="随手记…（自动保存）"
              @input="onInput"
              @blur="flush"
            />
            <span class="tri-label">自动保存 · {{ stickyUpdated(stickySlot) || '尚未写过' }}</span>
          </div>
        </template>
        <div v-else class="hud-empty"><b>选一张便签</b>随手记，自动保存</div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.notes-host {
  min-height: 0;
}
.notes-host > :deep(.speednote),
.notes-host > :not(.notes-filter):not(style) {
  flex: 1 1 auto;
  min-height: 0;
}
.notes-host {
  position: relative;
}
.notes-filter {
  padding-top: 8px;
}
.note-drop-hint {
  position: absolute;
  inset: 48px 12px 12px;
  z-index: 3;
  display: grid;
  place-items: center;
  pointer-events: none;
  font-size: 13px;
  color: #00e5ff;
  border: 1.5px dashed rgba(0, 229, 255, 0.55);
  border-radius: 10px;
  background: rgba(0, 229, 255, 0.06);
}
.note-mic {
  position: absolute;
  right: 14px;
  bottom: 12px;
  z-index: 4;
}
.tri-sticky {
  --tri-list-w: 260px;
}
.sticky-ta {
  flex: 1 1 auto;
  min-height: 240px;
  resize: none;
}
</style>
