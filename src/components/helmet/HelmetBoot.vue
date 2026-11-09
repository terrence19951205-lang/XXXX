<script setup lang="ts">
/**
 * 开场 · ASCII 鲨鱼海洋（**探索稿 v3 原样**）
 *
 * 视觉与逻辑逐条对齐 `.refs/reality-raid-hud-v08-ascii-explore-v3.html`
 * 的 startBoot / endBoot / AsciiSharks.OceanEngine：
 *  - 引擎 new AsciiSharks.OceanEngine(canvas, [classic 1, mako .86, hammerhead .78, thresher .7])
 *    —— 就是探索稿那套鱼群 boids + 鲨鱼捕食 + 字符栅格化，不是另写的字符雨
 *  - 5.6s 自动结束；prefers-reduced-motion 走 1.6s 短版，只画一张静止剪影
 *  - Enter / Esc / 空格 / 「跳过」按钮 可跳过
 *  - 结束：先 destroy() 卸掉引擎与全部 window 监听，再淡出，然后卸载组件（桌面不留 rAF）
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { AsciiSharks } from './ascii-sharks.js'

const emit = defineEmits<{ (e: 'done'): void }>()

/** 探索稿 v3 原样：四条鲨、四种体型 */
const SHARK_SPECS = [
  { kind: 'classic', size: 1 },
  { kind: 'mako', size: 0.86 },
  { kind: 'hammerhead', size: 0.78 },
  { kind: 'thresher', size: 0.7 },
]

const RM = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches
const TOTAL = RM ? 1600 : 5600

const rootEl = ref<HTMLDivElement | null>(null)
const canvasEl = ref<HTMLCanvasElement | null>(null)
const barEl = ref<HTMLElement | null>(null)
const skipEl = ref<HTMLButtonElement | null>(null)
const ready = ref(false)
const out = ref(false)

let ocean: { destroy(): void } | null = null
let timers: number[] = []
let raf = 0
let frames = 0
let ink = 0
let inkTimer = 0
let ended = false
let emitTimer = 0

/** 探索稿 v3 的 reduced-motion 兜底剪影（README silhouette，56 列） */
const ART = [
  "                            ;'",
  "                             %%'",
  '                              .t;.               .oooo',
  '                               S;:S%              %8S8.',
  "                                ;:tt%t '..        XX%%S",
  "t'                            ''XSSS8SSX%XX8#.    %XSX%",
  " :;'               ;.''X8%8XX%%S%%S%SStt%tSX8S#X8't%ttt.",
  "  ::%'       ''8XXXSSt%Stttttt%8@%%@%8@8%Sttt%%%%SSSSS%tt.",
  "  'SXXtt%t%%%S%:;StS%ttSS%tSXSt88@@%8%@8%tStS%%X%SS%%S%;;t",
  " .@##88#@...'@@@@#@8@88X88#XXXSX8SX88SX8%SS%S%%S88St%t%%%.",
  "  %;%t             :.    '.'##@###@X#888XX##8@@@#.X%XS%.",
  ' .%t                            ;%%%#@@##@@@.     SXS%%',
  ' t.                            .%;%%%.            %%XXS',
  "                              '%t:t              .SXSS'",
  "                             '::.                ooooo",
  "                            .S'",
  '                            .',
]

/** 静止剪影（reduced-motion：一帧，起动画循环之前就画好） */
function drawStill() {
  const cv = canvasEl.value
  if (!cv) return
  const ctx = cv.getContext('2d')
  if (!ctx) return
  const r = cv.getBoundingClientRect()
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  cv.width = Math.max(1, Math.round(r.width * dpr))
  cv.height = Math.max(1, Math.round(r.height * dpr))
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.fillStyle = '#01060c'
  ctx.fillRect(0, 0, r.width, r.height)
  ctx.fillStyle = '#6ee9ff'
  ctx.font = '600 11px ui-monospace, Menlo, Consolas, monospace'
  ctx.textBaseline = 'top'
  const x0 = Math.max(12, (r.width - 56 * 7) / 2)
  const y0 = Math.max(40, r.height * 0.28)
  ART.forEach((line, i) => ctx.fillText(line, x0, y0 + i * 13))
}

/** 取证口：证明真在跑帧、真在出墨（引擎类名即上游压缩类的名字，不是我们的组件） */
function publish() {
  const w = window as unknown as { __helmetBoot?: Record<string, unknown> }
  w.__helmetBoot = {
    active: !ended,
    engine: 'AsciiSharks.OceanEngine',
    engineClass: ocean ? (ocean as unknown as object).constructor.name : null,
    sharkKinds: SHARK_SPECS.map((s) => s.kind),
    sharks: ocean ? SHARK_SPECS.length : 0,
    frames,
    ink,
    total: TOTAL,
    reduced: RM,
    ended,
  }
}

/** 只数帧 + 采样墨量，不干扰引擎自己的 rAF */
function probe() {
  if (ended) return
  frames++
  raf = requestAnimationFrame(probe)
}

function sampleInk() {
  const cv = canvasEl.value
  if (!cv || ended) return
  try {
    const off = document.createElement('canvas')
    off.width = 160
    off.height = 90
    const octx = off.getContext('2d')
    if (!octx) return
    octx.drawImage(cv, 0, 0, 160, 90)
    const d = octx.getImageData(0, 0, 160, 90).data
    let lit = 0
    for (let i = 0; i < d.length; i += 4) {
      if (d[i] + d[i + 1] + d[i + 2] > 36) lit++
    }
    ink = Math.round((lit / (160 * 90)) * 1000) / 1000
  } catch {
    /* 取不到像素（极少见）不影响开场 */
  }
  publish()
}

/** 结束：先卸引擎（含 window 监听），再淡出，淡完才通知父级卸载 */
function endBoot() {
  if (ended) return
  ended = true
  timers.forEach((t) => window.clearTimeout(t))
  timers = []
  if (raf) cancelAnimationFrame(raf)
  raf = 0
  if (inkTimer) window.clearInterval(inkTimer)
  inkTimer = 0
  if (ocean) {
    try {
      ocean.destroy()
    } catch {
      /* ignore */
    }
    ocean = null
  }
  out.value = true
  publish()
  emitTimer = window.setTimeout(() => emit('done'), 500)
}

function startBoot() {
  const b = rootEl.value
  const bar = barEl.value
  const cv = canvasEl.value
  if (!b || !cv) return
  timers.forEach((t) => window.clearTimeout(t))
  timers = []
  ready.value = false
  out.value = false
  // 探索稿 v3：开场一出现就把焦点放到「跳过」，键盘用户第一下 Tab/Enter 即退出
  skipEl.value?.focus({ preventScroll: true })

  // 进度条：宽度 0 → 100%，时长就是开场时长（探索稿同款 CSS transition）
  if (bar) {
    bar.style.transition = 'none'
    bar.style.width = '0'
    void bar.offsetWidth
    bar.style.transition = `width ${TOTAL}ms linear`
    bar.style.width = '100%'
  }

  timers.push(window.setTimeout(() => (ready.value = true), RM ? 80 : 420))

  if (!RM) {
    ocean = new AsciiSharks.OceanEngine(cv, SHARK_SPECS)
    inkTimer = window.setInterval(sampleInk, 700)
    raf = requestAnimationFrame(probe)
  } else {
    drawStill()
  }
  publish()

  timers.push(window.setTimeout(endBoot, TOTAL))
}

function onKey(e: KeyboardEvent) {
  if (ended) return
  if (e.key === 'Enter' || e.key === 'Escape' || e.key === ' ') {
    e.preventDefault()
    e.stopPropagation()
    endBoot()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKey, true)
  // 引擎构造前让 canvas 先拿到真实尺寸（窗口可能刚被铺满）
  requestAnimationFrame(() => startBoot())
})

onBeforeUnmount(() => {
  ended = true
  window.removeEventListener('keydown', onKey, true)
  timers.forEach((t) => window.clearTimeout(t))
  timers = []
  if (emitTimer) window.clearTimeout(emitTimer)
  emitTimer = 0
  if (raf) cancelAnimationFrame(raf)
  raf = 0
  if (inkTimer) window.clearInterval(inkTimer)
  inkTimer = 0
  if (ocean) {
    try {
      ocean.destroy()
    } catch {
      /* ignore */
    }
    ocean = null
  }
  const w = window as unknown as { __helmetBoot?: Record<string, unknown> }
  w.__helmetBoot = {
    active: false,
    engine: 'AsciiSharks.OceanEngine',
    engineClass: null,
    sharkKinds: SHARK_SPECS.map((s) => s.kind),
    sharks: 0,
    frames,
    ink,
    total: TOTAL,
    reduced: RM,
    ended: true,
    tornDown: true,
  }
})
</script>

<template>
  <div
    ref="rootEl"
    class="rra-boot"
    :class="{ 'is-ready': ready, 'is-out': out }"
    role="dialog"
    aria-modal="true"
    aria-label="启动开场 · ASCII 鲨鱼 · 可跳过"
  >
    <canvas ref="canvasEl" class="rra-boot-ocean" aria-hidden="true" />
    <div class="rra-boot-title" aria-hidden="true">
      <div class="cn">shell-hub</div>
      <div class="en">Shell Hub · ASCII Ocean</div>
      <div class="hint">移动指针搅动洋流 · 点击溅起尾流</div>
    </div>
    <div class="rra-boot-foot">
      <div class="rra-boot-cap">
        <b>shell-hub</b>
        <span>ASCII 鲨鱼开机 · 中央保持桌面穿透</span>
      </div>
      <div
        class="rra-boot-bar"
        role="progressbar"
        aria-label="开场进度"
      >
        <i ref="barEl" />
      </div>
      <button ref="skipEl" type="button" class="btn sm cut-sm rra-skip" @click="endBoot">
        跳过 <kbd>Enter</kbd> <kbd>Esc</kbd>
      </button>
    </div>
  </div>
</template>