<script setup lang="ts">
/**
 * Helmet P0 · 剪贴板历史
 * 复用 x-hub `clipboard_history`（list / copy）。取用＝放回系统剪贴板并收起头盔，
 * 由用户在原窗口 Ctrl+V；不在头盔内伪造「粘贴到别的窗口」。
 */
import { computed, onMounted, ref } from 'vue'
import { isTauri, tauriApi, type ClipboardItem } from '../../api/tauri'

const emit = defineEmits<{
  (e: 'count', n: number): void
  (e: 'taken', label: string): void
}>()

const items = ref<ClipboardItem[]>([])
const kw = ref('')
const err = ref('')
const busy = ref(false)

const visible = computed(() =>
  kw.value.trim()
    ? items.value.filter((i) => (i.content || '').toLowerCase().includes(kw.value.trim().toLowerCase()))
    : items.value,
)

function preview(i: ClipboardItem): string {
  if (i.kind === 'image') return '[图片] ' + (i.content || '剪贴板图片')
  if (i.kind === 'file') return '[文件] ' + ((i.file_paths && i.file_paths[0]) || i.content || '')
  return (i.content || '').replace(/\s+/g, ' ').slice(0, 160) || '(空)'
}

async function load() {
  if (!isTauri()) return
  try {
    items.value = await tauriApi.clipboardList(undefined, 40, 0)
    emit('count', items.value.length)
    err.value = ''
  } catch (e) {
    err.value = String(e)
  }
}

async function take(i: ClipboardItem) {
  if (busy.value) return
  busy.value = true
  try {
    await tauriApi.clipboardCopy(i.id)
    emit('taken', preview(i))
  } catch (e) {
    err.value = String(e)
  } finally {
    busy.value = false
  }
}

onMounted(load)
defineExpose({ load })
</script>

<template>
  <div class="work">
    <div class="work-hd">
      <div class="title">剪贴板 <span class="en">Clipboard</span></div>
      <button class="btn sm cut-sm" @click="load">刷新</button>
    </div>
    <div class="work-bd">
      <div class="row-add">
        <input v-model="kw" class="field cut-sm" placeholder="筛近期复制内容…" spellcheck="false" />
      </div>
      <div class="list">
        <div v-if="!visible.length" class="empty">
          {{ kw ? '没有匹配的复制记录。' : '还没有剪贴板记录。复制一段文字后再看。' }}
        </div>
        <button
          v-for="i in visible"
          :key="i.id"
          class="item clip-item cut-sm"
          :title="preview(i)"
          @click="take(i)"
        >
          <span class="t">{{ preview(i) }}</span>
          <span class="m">
            {{ i.kind.toUpperCase() }} · {{ i.source_app || '未知来源' }} · {{ i.is_pinned ? '已置顶' : i.created_at }}
          </span>
        </button>
      </div>
      <div class="panel-hint">点击一条 → 放回系统剪贴板并收起 shell-hub，回到原窗口 Ctrl+V。</div>
      <div v-if="err" class="panel-hint">{{ err }}</div>
    </div>
  </div>
</template>