<script setup lang="ts">
/**
 * Helmet · 剪贴板（挂 x-hub 原版 ClipboardOverlay，嵌入模式）
 *
 * 原版这个组件本来是独立浮层窗口的页面（clipboard.html），功能是整个剪贴板历史：
 * 搜索、种类筛选、图片缩略与放大预览、置顶/取消置顶、单条删除、清空、
 * 存为速记、加入提示词、键盘上下选择与回车。
 * 手写那版只有「列出来 + 复制」。
 *
 * 它原生带窗口级行为（失焦自动收起 / 拖动窗口 / Esc 收窗 / 点条目粘贴到上个窗口），
 * 在面板里都有害，所以给原组件加了一个 embedded 开关，只保留本体功能。
 */
import ClipboardOverlay from '../ClipboardOverlay.vue'
</script>

<template>
  <div class="work clip-host xhub-host">
    <ClipboardOverlay embedded />
  </div>
</template>

<style scoped>
.clip-host {
  min-height: 0;
}
/* 原版根节点按浮层窗口写成 100vw×100vh，嵌入面板时改成跟随宿主尺寸 */
.clip-host :deep(.clipboard-overlay) {
  width: 100% !important;
  height: 100% !important;
}
</style>