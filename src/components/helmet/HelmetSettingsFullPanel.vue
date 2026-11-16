<script setup lang="ts">
/**
 * Helmet · 系统设置（挂 x-hub 原版 SettingsView）
 *
 * 原版能力：通用（开机自启、快捷键、托盘）、账号、AI 服务（多 provider / 密钥）、
 * 外观、数据（备份恢复、数据目录）、功能开关、扩展、工作台。壳里原来只有我们
 * 自己写的「上下班 / 模型 / 只读快捷键」三块，系统级配置一项都没有。
 *
 * 壳侧只做三件事：宿主容器、宽面板尺寸、把原版要的 toast 注入转过去。
 */
import { onMounted, ref } from 'vue'
// 设置页的样式整块外移在 settings/shared.css（由主窗的 style.css @import 引入），
// Helmet 入口故意不加载 style.css（会把 body 白底带进透明 HUD），所以这里单独引一次。
// 该文件每条规则都带 .settings-view 前缀，不会污染 HUD 其它部分。
import '../settings/shared.css'
import SettingsView from '../SettingsView.vue'

/** 从外侧指定打开哪一类（暂不传 = 默认首项） */
const props = defineProps<{ initialSection?: string; tab?: 'system' | 'island' }>()
const emit = defineEmits<{ (e: 'update:tab', v: 'system' | 'island'): void }>()

/** 原版某些子面板异步分包，给宿主一个底高，避免首帧塌成一条 */
const ready = ref(false)
onMounted(() => {
  ready.value = true
})
</script>

<template>
  <div class="xhub-host settings-host" :class="{ 'is-ready': ready }" data-settings-host>
    <SettingsView
      :initial-section="props.initialSection"
      :tab="props.tab"
      @update:tab="emit('update:tab', $event)"
    >
      <template #island>
        <slot name="island" />
      </template>
    </SettingsView>
  </div>
</template>