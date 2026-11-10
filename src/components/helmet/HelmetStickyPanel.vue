<script setup lang="ts">
/**
 * Helmet · 便签（挂 x-hub 原版 StickyCard，两张槽位）
 *
 * 原版便签的能力：随手写、600ms 防抖自动落盘、可「脱离」成独立悬浮便签窗、
 * 已脱离时点同一按钮聚焦那个浮窗。手写壳里完全没有这一块。
 *
 * 壳侧只做宿主：两张卡上下叠，给够高度；store 未加载时先拉一次。
 */
import { onMounted, ref } from 'vue'
import StickyCard from '../StickyCard.vue'
import { useStore } from '../../stores/workbench'

const store = useStore()
const ready = ref(false)

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
  <div class="work sticky-host xhub-host">
    <div v-if="ready" class="sticky-stack">
      <StickyCard :slot="1" title="便签 1" />
      <StickyCard :slot="2" title="便签 2" />
    </div>
    <div v-else class="panel-hint">正在载入便签…</div>
  </div>
</template>

<style scoped>
.sticky-host {
  min-height: 0;
}
.sticky-stack {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
}
.sticky-stack > * {
  flex: 1 1 0;
  min-height: 0;
}
</style>