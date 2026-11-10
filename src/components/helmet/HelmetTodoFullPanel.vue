<script setup lang="ts">
/**
 * Helmet · 待办（直接挂 x-hub 原版 TodoView）
 *
 * 手写那版只有「列表 + 勾选 + 新增 + 删除」，原版 TodoView.vue（1608 行）里有：
 * 范围（今天/本周/本月/全部）× 形态（列表/日历）两个正交维度、日历格、
 * 周期待办的展开与回滚、子任务拖拽/拆出、标签、提醒方式、逾期标记、批量完成。
 *
 * 壳侧同样只做三件事：备好 store、把 HUD 的 toast 注入进去、给够高的宿主。
 */
import { inject, onMounted, provide, ref } from 'vue'
import TodoView from '../TodoView.vue'
import { useStore } from '../../stores/workbench'

const store = useStore()
const ready = ref(false)

// 原版组件用 inject('showToast') 弹提示；壳里已经有一个 showToast，接上去复用
const hudToast = inject<((msg: string) => void) | null>('hudToast', null)
if (hudToast) provide('showToast', (msg: string) => hudToast(msg))

onMounted(async () => {
  if (!store.state.loaded) {
    try {
      await store.loadInitialData()
    } catch {
      /* 后端未就绪时原版自己显示空态 */
    }
  }
  ready.value = true
})
</script>

<template>
  <div class="work todo-host xhub-host">
    <div v-if="ready" class="todo-mount">
      <TodoView />
    </div>
    <div v-else class="panel-hint">正在载入待办…</div>
  </div>
</template>

<style scoped>
.todo-host {
  min-height: 0;
}
.todo-mount {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
}
.todo-mount > * {
  flex: 1 1 auto;
  min-height: 0;
}
</style>