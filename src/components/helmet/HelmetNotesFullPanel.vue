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
import { computed, inject, onMounted, provide, ref, watch, type Ref } from 'vue'
import SpeednoteView from '../SpeednoteView.vue'
import { useStore } from '../../stores/workbench'
import { pendingNoteId } from './hudBus'

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
.notes-filter {
  padding-top: 8px;
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
