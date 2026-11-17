// Helmet 座舱壳 POC-1 轻量入口：旁路全屏透明窗，不挂完整 SPA。
// 视觉 tokens / 切角几何只读复制自 reality-raid-hud-v05.html（不改原文件）。
import { createApp } from 'vue'
import HelmetShell from '../components/HelmetShell.vue'

createApp(HelmetShell).mount('#app')
