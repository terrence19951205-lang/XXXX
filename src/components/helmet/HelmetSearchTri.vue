<script setup lang="ts">
/**
 * Helmet · 搜索三栏（P1-3）：左轨 | 结果（按 待办 / 笔记 分组）| 预览
 *
 * - 列表栏顶部是搜索框（与底栏搜索框同一个关键词，底栏输入会把这里打开）
 * - 详情栏：待办显示截止/周期/子项/备注；笔记显示缩略图 + 正文摘要
 * - 「打开」：跳到该功能的三栏并选中那一条
 */
import { computed, inject, nextTick, onMounted, ref, watch, type Ref } from 'vue'
import { isTauri, tauriApi, type Note, type SearchResult, type Todo } from '../../api/tauri'
import { noteSnippet, noteThumb } from '../../utils/noteThumb'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: string): void
  (e: 'open-todo', id: number): void
  (e: 'open-note', id: number): void
}>()
const narrow = inject<Ref<boolean>>('hudNarrow', ref(false))

const q = computed({
  get: () => props.modelValue,
  set: (v: string) => emit('update:modelValue', v),
})
const res = ref<SearchResult | null>(null)
const busy = ref(false)
const sel = ref<{ k: 'todo' | 'note'; id: number } | null>(null)
const fullNote = ref<Note | null>(null)
const inputEl = ref<HTMLInputElement | null>(null)
let timer: number | null = null

async function run() {
  const kw = q.value.trim()
  if (!kw || !isTauri()) {
    res.value = null
    return
  }
  busy.value = true
  try {
    res.value = await tauriApi.searchAll(kw)
  } catch {
    res.value = null
  } finally {
    busy.value = false
  }
}
watch(q, () => {
  if (timer != null) window.clearTimeout(timer)
  timer = window.setTimeout(run, 200)
})
onMounted(() => {
  void run()
  void nextTick(() => inputEl.value?.focus())
})

const todos = computed<Todo[]>(() => res.value?.todos ?? [])
const notes = computed<Note[]>(() => res.value?.notes ?? [])
const total = computed(() => todos.value.length + notes.value.length)

watch(res, () => {
  if (sel.value) {
    const ok = sel.value.k === 'todo' ? todos.value.some((t) => t.id === sel.value!.id) : notes.value.some((n) => n.id === sel.value!.id)
    if (ok) return
  }
  sel.value = null
  if (!narrow.value) {
    if (todos.value.length) sel.value = { k: 'todo', id: todos.value[0].id }
    else if (notes.value.length) sel.value = { k: 'note', id: notes.value[0].id }
  }
})

const selTodo = computed(() => (sel.value?.k === 'todo' ? todos.value.find((t) => t.id === sel.value!.id) ?? null : null))
const selNote = computed(() => (sel.value?.k === 'note' ? notes.value.find((n) => n.id === sel.value!.id) ?? null : null))

watch(selNote, async (n) => {
  fullNote.value = n
  // 搜索结果里的 content 可能是截断摘要：取一次全文给预览
  if (n && isTauri()) {
    try {
      const full = await tauriApi.getNote(n.id)
      if (full && sel.value?.k === 'note' && sel.value.id === n.id) fullNote.value = full
    } catch {
      /* 用摘要兜底 */
    }
  }
})

function dueText(t: Todo): string {
  if (t.due_at == null) return '无截止'
  const d = new Date(t.due_at)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
function hl(text: string): { s: string; m: boolean }[] {
  const kw = q.value.trim()
  if (!kw) return [{ s: text, m: false }]
  const out: { s: string; m: boolean }[] = []
  const lower = text.toLowerCase()
  const k = kw.toLowerCase()
  let i = 0
  while (i < text.length) {
    const j = lower.indexOf(k, i)
    if (j < 0) {
      out.push({ s: text.slice(i), m: false })
      break
    }
    if (j > i) out.push({ s: text.slice(i, j), m: false })
    out.push({ s: text.slice(j, j + k.length), m: true })
    i = j + k.length
  }
  return out
}
function open() {
  if (selTodo.value) emit('open-todo', selTodo.value.id)
  else if (selNote.value) emit('open-note', selNote.value.id)
}
defineExpose({ focus: () => inputEl.value?.focus() })
</script>

<template>
  <div class="tri tri-search" :class="{ 'is-narrow': narrow, 'has-detail': narrow && sel }" data-tri="search">
    <section class="tri-list">
      <div class="tri-hd">
        <div class="tri-title">搜索 <span class="en">Search</span></div>
        <span class="tri-label">{{ busy ? '检索中…' : res ? `${total} 条` : '' }}</span>
      </div>
      <div class="tri-filter">
        <input
          ref="inputEl"
          v-model="q"
          class="hud-input"
          data-search-input
          placeholder="搜待办 / 笔记，回车打开第一条"
          spellcheck="false"
          @keydown.enter.prevent="open"
        />
      </div>
      <div class="tri-scroll">
        <div v-if="!q.trim()" class="hud-empty"><b>输入关键词</b>同时搜待办和笔记</div>
        <div v-else-if="busy && !res" class="hud-loading">检索中…</div>
        <div v-else-if="res && !total" class="hud-empty"><b>没有命中「{{ q }}」</b>换个关键词试试</div>
        <template v-if="todos.length">
          <div class="tri-group">待办 · {{ todos.length }}</div>
          <button
            v-for="t in todos"
            :key="'t' + t.id"
            type="button"
            class="tri-row"
            :class="{ 'is-on': sel?.k === 'todo' && sel.id === t.id }"
            data-search-hit="todo"
            @click="sel = { k: 'todo', id: t.id }"
            @dblclick="emit('open-todo', t.id)"
          >
            <span class="main">
              <span class="t"><template v-for="(p, i) in hl(t.title)" :key="i"><mark v-if="p.m">{{ p.s }}</mark><template v-else>{{ p.s }}</template></template></span>
              <span class="s">{{ t.done ? '已完成' : '未完成' }} · {{ dueText(t) }}</span>
            </span>
          </button>
        </template>
        <template v-if="notes.length">
          <div class="tri-group">笔记 · {{ notes.length }}</div>
          <button
            v-for="n in notes"
            :key="'n' + n.id"
            type="button"
            class="tri-row"
            :class="{ 'is-on': sel?.k === 'note' && sel.id === n.id }"
            data-search-hit="note"
            @click="sel = { k: 'note', id: n.id }"
            @dblclick="emit('open-note', n.id)"
          >
            <img v-if="noteThumb(n.content)" class="thumb" :src="noteThumb(n.content)" alt="" loading="lazy" data-note-thumb />
            <span class="main">
              <span class="t"><template v-for="(p, i) in hl(n.title || '未命名笔记')" :key="i"><mark v-if="p.m">{{ p.s }}</mark><template v-else>{{ p.s }}</template></template></span>
              <span class="s">{{ noteSnippet(n.content, 60) || '（空笔记）' }}</span>
            </span>
          </button>
        </template>
      </div>
    </section>
    <section class="tri-detail" data-tri-detail>
      <template v-if="selTodo || selNote">
        <div class="tri-hd">
          <button class="hud-btn is-sm tri-back" type="button" data-tri-back @click="sel = null">‹ 返回</button>
          <div class="tri-title">预览 <span class="en">{{ selTodo ? 'Todo' : 'Note' }}</span></div>
        </div>
        <div v-if="selTodo" class="tri-body">
          <div class="pv-title">{{ selTodo.title }}</div>
          <div class="tri-label">
            {{ selTodo.done ? '已完成' : '未完成' }} · 截止 {{ dueText(selTodo) }}
            <template v-if="selTodo.repeat_mode !== 'once'"> · 周期待办</template>
          </div>
          <pre v-if="selTodo.description" class="tri-preview-text">{{ selTodo.description }}</pre>
        </div>
        <div v-else-if="selNote" class="tri-body">
          <div class="pv-title">{{ selNote.title || '未命名笔记' }}</div>
          <div class="tri-label">更新于 {{ selNote.updated_at }}</div>
          <img v-if="noteThumb((fullNote || selNote).content)" class="tri-preview-img" :src="noteThumb((fullNote || selNote).content)" alt="笔记图片" data-search-preview-img />
          <pre class="tri-preview-text">{{ noteSnippet((fullNote || selNote).content, 1200) || '（空笔记）' }}</pre>
        </div>
        <div class="tri-acts">
          <button class="hud-btn is-primary" type="button" data-search-open @click="open">
            打开{{ selTodo ? '待办' : '笔记' }}
          </button>
        </div>
      </template>
      <div v-else class="hud-empty"><b>选一条结果</b>右侧预览，「打开」跳到对应功能</div>
    </section>
  </div>
</template>

<style scoped>
.tri-search {
  --tri-list-w: 330px;
}
mark {
  color: var(--hud-ink-on-accent);
  background: rgba(0, 229, 255, 0.85);
  border-radius: 2px;
  padding: 0 1px;
}
.pv-title {
  font-size: var(--hud-fs-lg);
  font-weight: 600;
  line-height: var(--hud-lh-tight);
  word-break: break-word;
}
</style>
