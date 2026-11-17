<script setup lang="ts">
/**
 * Helmet · 倒计时（挂 x-hub 原版 CountdownCard）
 *
 * 原版能力：多条倒计时（默认上限 6）、新建/编辑/删除、暂停与继续、
 * 到点提醒、「悬浮到桌面」成独立浮窗。壳里此前完全没有这一块。
 *
 * 壳侧只做宿主 + store 首载；倒计时读秒由原组件自己跑。
 */
import { onMounted, ref } from 'vue'
import CountdownCard from '../CountdownCard.vue'
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
  <div class="work cd-host xhub-host">
    <div v-if="ready" class="cd-mount">
      <CountdownCard />
    </div>
    <div v-else class="panel-hint">正在载入倒计时…</div>
  </div>
</template>

<style scoped>
.cd-host {
  min-height: 0;
}
.cd-mount {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
}
.cd-mount > * {
  flex: 1 1 auto;
  min-height: 0;
}
</style>