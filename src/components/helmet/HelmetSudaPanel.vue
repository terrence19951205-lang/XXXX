<script setup lang="ts">
/**
 * Helmet · 速达（直接挂 x-hub 原版组件）
 *
 * 上一版是我们在 91 行里重写的「列表 + 启动」，功能只有原版的一小截。
 * 原版 Suda.vue 2409 行里已经有：分区/小类、批量管理、拖拽导入、图标扫描、
 * 浏览器书签、管理员启动、定位、右键菜单……能直接挂就别重写。
 *
 * 这里只做三件事：备好主题 token（在 helmet.css 的 .xhub-host 里映射）、
 * 保证 store 已加载、给它一个够大的宿主盒子。
 */
import { onMounted, ref } from 'vue'
import Suda from '../Suda.vue'
import { useStore } from '../../stores/workbench'

const store = useStore()
const ready = ref(false)

onMounted(async () => {
  if (!store.state.loaded) {
    try {
      await store.loadInitialData()
    } catch {
      /* 后端未就绪时 Suda 自己会显示空态 */
    }
  }
  ready.value = true
})
</script>

<template>
  <div class="work suda-host xhub-host">
    <div v-if="ready" class="suda-mount">
      <Suda />
    </div>
    <div v-else class="panel-hint">正在载入速达…</div>
  </div>
</template>

<style scoped>
.suda-host {
  min-height: 0;
}
.suda-mount {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
}
.suda-mount > * {
  flex: 1 1 auto;
  min-height: 0;
}
</style>