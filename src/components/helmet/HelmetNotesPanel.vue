<script setup lang="ts">
/**
 * shell-hub P0 · 笔记中栏（左功能栏 → 中栏列表）
 *
 * 照抄 `.refs/shell-hub-notes-3col-explore.html` 的第二栏：
 * 标题 + 新建 + ✕ 收起、筛选框、条目（标题 / 摘要两行 / 更新时间）。
 * 点条目 → 右栏 `HelmetNoteEditor` 打开编辑；再点左栏「笔记」按分层收起。
 */
import { onMounted } from 'vue'
import { noteSummary, noteTime, useHelmetNotes } from '../../composables/useHelmetNotes'

const { filter, filtered, activeId, err, open, createNew, closeList, load } = useHelmetNotes()
const emit = defineEmits<{ (e: 'toast', msg: string): void }>()

onMounted(() => void load())

async function onNew() {
  await createNew()
  emit('toast', '已新建笔记')
}
</script>

<template>
  <div class="work">
    <div class="work-hd">
      <div class="title">笔记 <span class="en">Notes</span></div>
      <div class="hd-acts">
        <button class="btn sm primary cut-sm" title="新建笔记" @click="onNew">新建</button>
        <button
          class="icon-btn"
          type="button"
          title="收起笔记列表"
          aria-label="收起笔记列表"
          @click="closeList()"
        >
          ✕
        </button>
      </div>
    </div>
    <div class="work-bd">
      <div class="list-tools">
        <input
          v-model="filter"
          class="field cut-sm"
          type="search"
          placeholder="筛选标题 / 摘要…"
          autocomplete="off"
          spellcheck="false"
        />
      </div>
      <div class="note-list" role="list" aria-label="笔记条目">
        <button
          v-for="n in filtered"
          :key="n.id"
          type="button"
          class="note-row"
          :class="{ 'is-on': n.id === activeId }"
          :title="n.title || '未命名笔记'"
          role="listitem"
          @click="open(n.id)"
        >
          <span class="t">{{ n.title || '未命名笔记' }}</span>
          <span class="s">{{ noteSummary(n.content) }}</span>
          <span class="m">{{ noteTime(n.updated_at) }}</span>
        </button>
        <div v-if="!filtered.length" class="empty">
          {{ filter.trim() ? '无匹配笔记' : '暂无笔记 · 点「新建」' }}
        </div>
      </div>
      <div v-if="err" class="panel-hint">{{ err }}</div>
    </div>
  </div>
</template>