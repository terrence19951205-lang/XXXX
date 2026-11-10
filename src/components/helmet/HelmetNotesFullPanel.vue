<script setup lang="ts">
/**
 * Helmet · 笔记（直接挂 x-hub 原版 SpeednoteView）
 *
 * 原版速记视图（550 行）＝ 文件夹树（树 + 搜索 + 标签筛选 + 回收站三种形态）
 * + 编辑器同位分流（Markdown 用 NoteEditor / 表格用 SheetEditor），
 * 编辑、软删回收站、导出（md/txt/pdf/sheet）、AI 美化、双链都在里面。
 *
 * 手写那版只有 72 行的只读列表 + 一个简化编辑器，功能差着一整套。
 */
import { inject, onMounted, provide } from 'vue'
import SpeednoteView from '../SpeednoteView.vue'
import { useStore } from '../../stores/workbench'

const store = useStore()

onMounted(async () => {
  if (!store.state.loaded) {
    try {
      await store.loadInitialData()
    } catch {
      /* 后端未就绪时原版自己显示空态 */
    }
  }
})

// 原版组件用 inject('showToast') 弹轻提示；壳里已 provide('hudToast')
const hudToast = inject<((msg: string) => void) | null>('hudToast', null)
if (hudToast) provide('showToast', (msg: string) => hudToast(msg))
</script>

<template>
  <div class="work notes-host xhub-host">
    <SpeednoteView />
  </div>
</template>

<style scoped>
.notes-host {
  min-height: 0;
}
.notes-host > * {
  flex: 1 1 auto;
  min-height: 0;
}
</style>