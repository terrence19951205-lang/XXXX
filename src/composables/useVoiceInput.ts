/**
 * 录音转文字（P1-3）：笔记编辑器与对话舱输入框共用。
 *
 * - 录音：WebView 的 getUserMedia + MediaRecorder（webm/opus），只在用户按下按钮后开始；
 *   第一次会由 WebView2 弹系统麦克风授权，拒绝给出明确提示、按钮复位，不卡死。
 * - 转写：Rust `transcribe_audio` → 设置里配置的 OpenAI 兼容服务 `/audio/transcriptions`
 *   （底座没有本地语音识别）。
 * - 不做后台录音：宿主组件卸载（收起对话 / 收起 HUD / 切走面板）时立即停录并丢弃，
 *   提示「录音已停止」，不留幽灵录音；单次最长 120 秒自动结束。
 */
import { onBeforeUnmount, ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { isTauri } from '../api/tauri'

export type VoiceState = 'idle' | 'asking' | 'recording' | 'transcribing'

const MAX_MS = 120_000

/** 全局只允许一路在录（笔记和对话舱不会同时抢麦） */
let activeOwner: symbol | null = null

interface VoiceDebug {
  state: VoiceState
  owner: string
  lastError: string
  lastText: string
  lastBytes: number
  startedAt: number
}
function dbg(): VoiceDebug {
  const w = window as unknown as { __voice?: VoiceDebug }
  if (!w.__voice) w.__voice = { state: 'idle', owner: '', lastError: '', lastText: '', lastBytes: 0, startedAt: 0 }
  return w.__voice
}

function explain(err: unknown): string {
  const name = (err as { name?: string })?.name || ''
  const msg = String((err as { message?: string })?.message ?? err)
  if (name === 'NotAllowedError' || name === 'SecurityError')
    return '麦克风权限被拒绝：没有录音。要用语音输入，请在弹窗里允许，或到 Windows 设置 → 隐私 → 麦克风 打开桌面应用访问'
  if (name === 'NotFoundError' || name === 'OverconstrainedError') return '没有检测到麦克风设备'
  if (name === 'NotReadableError') return '麦克风被其他程序占用，暂时无法录音'
  if (msg.startsWith('NO_API')) return '还没有可用的模型 API：设置 → AI 助手 → 供应商 里配一个带 Key 的模型后再试'
  if (msg.startsWith('UNSUPPORTED')) return msg.replace(/^UNSUPPORTED:\s*/, '')
  if (msg.startsWith('EMPTY')) return '录音太短或没有声音，没有转出文字'
  if (msg.startsWith('NET')) return msg.replace(/^NET:\s*/, '')
  return '转写失败：' + msg.slice(0, 120)
}

function blobToB64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => {
      const s = String(r.result || '')
      resolve(s.slice(s.indexOf(',') + 1))
    }
    r.onerror = () => reject(new Error('读取录音失败'))
    r.readAsDataURL(blob)
  })
}

export function useVoiceInput(opts: {
  owner: string
  onText: (text: string) => void
  toast?: (msg: string) => void
}) {
  const me = Symbol(opts.owner)
  const state = ref<VoiceState>('idle')
  const elapsed = ref(0)
  let stream: MediaStream | null = null
  let rec: MediaRecorder | null = null
  let chunks: Blob[] = []
  let discard = false
  let tick: number | null = null
  let cap: number | null = null

  function setState(s: VoiceState) {
    state.value = s
    const d = dbg()
    d.state = s
    d.owner = s === 'idle' ? '' : opts.owner
  }

  function release() {
    if (tick != null) window.clearInterval(tick)
    if (cap != null) window.clearTimeout(cap)
    tick = cap = null
    stream?.getTracks().forEach((t) => t.stop())
    stream = null
    rec = null
    if (activeOwner === me) activeOwner = null
  }

  async function start() {
    if (state.value !== 'idle') return
    if (activeOwner && activeOwner !== me) {
      opts.toast?.('另一处正在录音，先结束那边')
      return
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      opts.toast?.('当前环境不支持录音')
      return
    }
    activeOwner = me
    setState('asking')
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
    } catch (e) {
      const m = explain(e)
      dbg().lastError = m
      release()
      setState('idle')
      opts.toast?.(m)
      return
    }
    if ((state.value as VoiceState) !== 'asking') {
      // 授权期间宿主已卸载 / 被取消
      release()
      return
    }
    const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : ''
    rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream)
    chunks = []
    discard = false
    rec.ondataavailable = (ev) => {
      if (ev.data && ev.data.size) chunks.push(ev.data)
    }
    rec.onstop = () => void finish(rec?.mimeType || mime || 'audio/webm')
    rec.start(250)
    elapsed.value = 0
    const t0 = Date.now()
    dbg().startedAt = t0
    tick = window.setInterval(() => (elapsed.value = Math.floor((Date.now() - t0) / 1000)), 250)
    cap = window.setTimeout(() => {
      opts.toast?.('单次录音最长 2 分钟，已自动结束')
      stop()
    }, MAX_MS)
    setState('recording')
  }

  function stop() {
    if (state.value === 'asking') {
      // 还在等授权：标记取消，授权回来后直接释放
      setState('idle')
      return
    }
    if (state.value !== 'recording' || !rec) return
    setState('transcribing')
    try {
      rec.stop()
    } catch {
      release()
      setState('idle')
    }
  }

  /** 宿主收起 / 卸载：停录并丢弃，不在后台继续 */
  function cancel(reason = '录音已停止') {
    if (state.value === 'idle') return
    const wasRecording = state.value === 'recording' || state.value === 'asking'
    discard = true
    try {
      rec?.state === 'recording' && rec.stop()
    } catch {
      /* ignore */
    }
    release()
    setState('idle')
    if (wasRecording) opts.toast?.(reason)
  }

  async function finish(mime: string) {
    const blob = new Blob(chunks, { type: mime })
    chunks = []
    const dropped = discard
    release()
    if (dropped) {
      setState('idle')
      return
    }
    const d = dbg()
    d.lastBytes = blob.size
    if (!isTauri()) {
      setState('idle')
      return
    }
    try {
      const b64 = await blobToB64(blob)
      const r = await invoke<{ text: string; model: string; provider: string }>('transcribe_audio', {
        audioB64: b64,
        mime,
      })
      d.lastText = r.text
      d.lastError = ''
      if (!r.text) opts.toast?.('没有听到内容')
      else opts.onText(r.text)
    } catch (e) {
      const m = explain(e)
      d.lastError = m
      opts.toast?.(m)
    } finally {
      setState('idle')
    }
  }

  function toggle() {
    if (state.value === 'idle') void start()
    else if (state.value === 'recording' || state.value === 'asking') stop()
  }

  /** 壳收起 HUD 时广播 hud-voice-stop（面板只是隐藏不卸载，必须显式停） */
  function onStopEvent(e: Event) {
    const d = (e as CustomEvent<{ owner?: string; reason?: string }>).detail || {}
    if (!d.owner || d.owner === opts.owner) cancel(d.reason || '录音已停止')
  }
  window.addEventListener('hud-voice-stop', onStopEvent)

  onBeforeUnmount(() => {
    window.removeEventListener('hud-voice-stop', onStopEvent)
    cancel('录音已停止（面板已收起，未保存这段录音）')
  })

  return { state, elapsed, start, stop, cancel, toggle }
}
