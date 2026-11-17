<script setup lang="ts">
/**
 * Helmet · 剪贴板三栏（P1-3）：左轨 | 历史列表 | 详情预览
 *
 * - 列表栏顶部：搜索 + 筛选 全部 / 文本 / 图片（文件条目归「全部」）
 * - 详情栏：文本全文 / 图片大图预览，「复制」「插入」「置顶」「删除」
 *   「插入」：对话舱开着 → 填进舱输入框（草稿，不发送）；否则收起 HUD 粘贴到上一个窗口
 * 数据走原版 clipboard_* 命令，与原版剪贴板浮层同一份。
 */
import { computed, inject, onMounted, ref, watch, type Ref } from 'vue'
import { convertFileSrc } from '@tauri-apps/api/core'
import { isTauri, tauriApi, type ClipboardItem } from '../../api/tauri'

const toast = inject<((m: string) => void) | null>('hudToast', null)
const narrow = inject<Ref<boolean>>('hudNarrow', ref(false))
const emit = defineEmits<{ (e: 'insert', item: ClipboardItem): void }>()

type Kind = 'all' | 'text' | 'image'
const kind = ref<Kind>('all')
const kw = ref('')
const items = ref<ClipboardItem[]>([])
const loading = ref(true)
const activeId = ref<number | null>(null)
const confirmDel = ref(false)
let timer: number | null = null

async function load() {
  if (!isTauri()) {
    loading.value = false
    return
  }
  try {
    items.value = await tauriApi.clipboardList(kw.value.trim() || undefined, 200, 0)
  } catch (e) {
    toast?.('读取剪贴板历史失败：' + String(e).slice(0, 60))
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(kw, () => {
  if (timer != null) window.clearTimeout(timer)
  timer = window.setTimeout(load, 200)
})

const rows = computed(() =>
  items.value.filter((i) => kind.value === 'all' || i.kind === kind.value),
)
const counts = computed(() => ({
  all: items.value.length,
  text: items.value.filter((i) => i.kind === 'text').length,
  image: items.value.filter((i) => i.kind === 'image').length,
}))
const active = computed(() => items.value.find((i) => i.id === activeId.value) ?? null)
watch(rows, (r) => {
  if (activeId.value != null && !r.some((i) => i.id === activeId.value)) activeId.value = null
  if (activeId.value == null && !narrow.value && r.length) activeId.value = r[0].id
})
watch(activeId, () => (confirmDel.value = false))

function imgSrc(i: ClipboardItem): string {
  return i.image_path && isTauri() ? convertFileSrc(i.image_path) : ''
}
function title(i: ClipboardItem): string {
  if (i.kind === 'image') return '图片'
  if (i.kind === 'file') return i.file_paths.map((p) => p.split(/[\\/]/).pop()).join('，') || '文件'
  return i.content.replace(/\s+/g, ' ').trim() || '（空白）'
}
function when(i: ClipboardItem): string {
  const t = Date.parse(i.updated_at.replace(' ', 'T'))
  if (!Number.isFinite(t)) return ''
  const s = Math.max(0, (Date.now() - t) / 1000)
  if (s < 60) return '刚刚'
  if (s < 3600) return `${Math.floor(s / 60)} 分钟前`
  if (s < 86400) return `${Math.floor(s / 3600)} 小时前`
  return `${Math.floor(s / 86400)} 天前`
}
const KIND_LABEL: Record<string, string> = { text: '文本', image: '图片', file: '文件' }

async function copy(i: ClipboardItem) {
  try {
    await tauriApi.clipboardCopy(i.id)
    toast?.('已复制到剪贴板')
  } catch (e) {
    toast?.('复制失败：' + String(e).slice(0, 60))
  }
}
async function pin(i: ClipboardItem) {
  try {
    const u = await tauriApi.clipboardTogglePin(i.id)
    const k = items.value.findIndex((x) => x.id === i.id)
    if (k >= 0) items.value[k] = u
  } catch (e) {
    toast?.(String(e).slice(0, 60))
  }
}
async function del(i: ClipboardItem) {
  if (!confirmDel.value) {
    confirmDel.value = true
    return
  }
  try {
    await tauriApi.clipboardDelete(i.id)
    items.value = items.value.filter((x) => x.id !== i.id)
    activeId.value = null
  } catch (e) {
    toast?.(String(e).slice(0, 60))
  }
}
</script>

<template>
  <div class="tri tri-clip" :class="{ 'is-narrow': narrow, 'has-detail': narrow && active }" data-tri="clipboard">
    <section class="tri-list">
      <div class="tri-hd">
        <div class="tri-title">剪贴板 <span class="en">Clipboard</span></div>
        <button class="hud-btn is-sm" type="button" title="刷新" @click="load">↻</button>
      </div>
      <div class="tri-filter" data-tri-filter>
        <input v-model="kw" class="hud-input" data-clip-search placeholder="搜索剪贴板历史…" />
        <button class="hud-chip" :class="{ 'is-on': kind === 'all' }" data-filter="all" @click="kind = 'all'">
          全部 <span class="n">{{ counts.all }}</span>
        </button>
        <button class="hud-chip" :class="{ 'is-on': kind === 'text' }" data-filter="text" @click="kind = 'text'">
          文本 <span class="n">{{ counts.text }}</span>
        </button>
        <button class="hud-chip" :class="{ 'is-on': kind === 'image' }" data-filter="image" @click="kind = 'image'">
          图片 <span class="n">{{ counts.image }}</span>
        </button>
      </div>
      <div class="tri-scroll">
        <div v-if="loading" class="hud-loading">正在读取…</div>
        <div v-else-if="!rows.length" class="hud-empty">
          <b>{{ kw ? `没有命中「${kw}」` : kind === 'image' ? '还没有图片记录' : '还没有剪贴板记录' }}</b>
          复制过的文本和图片会出现在这里
        </div>
        <button
          v-for="i in rows"
          :key="i.id"
          type="button"
          class="tri-row"
          :class="{ 'is-on': i.id === activeId }"
          :data-clip-id="i.id"
          @click="activeId = i.id"
        >
          <img v-if="i.kind === 'image' && imgSrc(i)" class="thumb" :src="imgSrc(i)" alt="" loading="lazy" />
          <span class="main">
            <span class="t">{{ i.is_pinned ? '📌 ' : '' }}{{ title(i) }}</span>
            <span class="s">{{ KIND_LABEL[i.kind] }} · {{ i.source_app || '未知来源' }} · {{ when(i) }}</span>
          </span>
        </button>
      </div>
    </section>
    <section class="tri-detail" data-tri-detail>
      <template v-if="active">
        <div class="tri-hd">
          <button class="hud-btn is-sm tri-back" type="button" data-tri-back @click="activeId = null">‹ 返回</button>
          <div class="tri-title">预览 <span class="en">{{ KIND_LABEL[active.kind] }}</span></div>
          <span class="tri-label">{{ active.source_app || '' }} · {{ when(active) }}</span>
        </div>
        <div class="tri-body">
          <img v-if="active.kind === 'image' && imgSrc(active)" class="tri-preview-img" :src="imgSrc(active)" alt="剪贴板图片" />
          <pre v-else-if="active.kind === 'file'" class="tri-preview-text">{{ active.file_paths.join('\n') }}</pre>
          <pre v-else class="tri-preview-text" data-clip-preview>{{ active.content }}</pre>
        </div>
        <div class="tri-acts">
          <button class="hud-btn is-primary" type="button" data-clip-copy @click="copy(active)">复制</button>
          <button
            class="hud-btn"
            type="button"
            data-clip-insert
            title="对话舱开着时填进输入框（不发送）；否则收起 HUD 粘贴到上一个窗口"
            @click="emit('insert', active)"
          >
            插入
          </button>
          <span class="sp" />
          <button class="hud-btn is-sm" type="button" @click="pin(active)">{{ active.is_pinned ? '取消置顶' : '置顶' }}</button>
          <button class="hud-btn is-sm is-danger" type="button" @click="del(active)">{{ confirmDel ? '再点一次删除' : '删除' }}</button>
        </div>
      </template>
      <div v-else class="hud-empty"><b>选一条记录</b>右侧预览全文或大图，可复制或插入</div>
    </section>
  </div>
</template>

<style scoped>
.tri-clip {
  --tri-list-w: 330px;
}
.tri-filter .hud-input {
  flex: 1 1 100%;
  margin-bottom: 2px;
}
</style>
