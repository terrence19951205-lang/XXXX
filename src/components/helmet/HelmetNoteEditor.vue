<script setup lang="ts">
/**
 * shell-hub P0 · 笔记右栏（中栏列表 → 右栏编辑）
 *
 * 照抄 `.refs/shell-hub-notes-3col-explore.html` 的第三栏：
 * 标题输入 → 更新时间/id 元信息行 → 正文 textarea → 状态 + 删除 / 收起 / 保存。
 * 状态来自 `useHelmetNotes` 单例，与中栏列表共用同一份数据。
 */
import { computed } from 'vue'
import { noteTime, useHelmetNotes } from '../../composables/useHelmetNotes'

const { title, content, status, active, saveNow, closeEditor, removeActive } =
  useHelmetNotes()
const emit = defineEmits<{ (e: 'toast', msg: string): void }>()

const metaText = computed(() =>
  active.value ? `更新 ${noteTime(active.value.updated_at)} · id ${active.value.id}` : '—',
)
const savedText = computed(() => {
  switch (status.value) {
    case 'saving':
      return '保存中…'
    case 'dirty':
      return '未保存'
    case 'saved':
      return '已保存'
    default:
      return '未改动'
  }
})

async function onSave() {
  const ok = await saveNow()
  emit('toast', ok ? '笔记已保存' : '保存失败')
}

async function onDelete() {
  if (await removeActive()) emit('toast', '已移入回收站')
}
</script>

<template>
  <div class="work">
    <div class="work-hd">
      <div class="title">
        <span class="ellipsis">{{ active?.title || '编辑' }}</span>
        <span class="en">Editor</span>
      </div>
      <button
        class="icon-btn"
        type="button"
        title="收起编辑页"
        aria-label="收起编辑页"
        @click="closeEditor()"
      >
        ✕
      </button>
    </div>
    <div class="work-bd">
      <div class="note-ed">
        <input
          v-model="title"
          class="title cut-sm"
          type="text"
          placeholder="标题"
          maxlength="120"
          spellcheck="false"
        />
        <div class="meta-line">{{ metaText }}</div>
        <textarea
          v-model="content"
          class="cut-sm"
          placeholder="在此填写正文…"
          spellcheck="false"
        />
        <div class="bar">
          <span class="saved" :class="{ 'is-ok': status === 'saved' }">{{ savedText }}</span>
          <div class="acts">
            <button class="btn sm danger cut-sm" type="button" @click="onDelete">删除</button>
            <button class="btn sm cut-sm" type="button" @click="closeEditor()">收起</button>
            <button class="btn sm primary cut-sm" type="button" @click="onSave">保存</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>