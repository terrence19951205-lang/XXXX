<script setup lang="ts">
/**
 * Helmet P0 · 完整对话舱（挂在岛下）
 * 复用 x-hub 对话数据层：chat_sessions / chat_messages / 模型配置，
 * 与主窗、独立对话窗共用一套会话，不绑 claw。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  PLATFORM_ENTRY_NAME,
  isPlatformModel,
  isTauri,
  tauriApi,
  type ChatMessage,
  type ChatModelConfig,
  type ChatSession,
  type Snippet,
} from '../../api/tauri'

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'toast', msg: string): void
  /** 对话是顶层入口：从舱里直达任一功能面板 */
  (e: 'open-panel', key: string): void
}>()

/** 对话舱顶部功能区：与左侧导航同一批面板，少的是「聊天」自己 */
const FNS = [
  { k: 'todos', lab: '待办', tip: '待办 / 日历' },
  { k: 'notes', lab: '笔记', tip: '笔记库' },
  { k: 'clipboard', lab: '剪贴板', tip: '剪贴板历史' },
  { k: 'launch', lab: '启动', tip: '常用工具与站点' },
  { k: 'search', lab: '搜索', tip: '全局搜索' },
  { k: 'settings', lab: '设置', tip: '上下班 / 模型' },
] as const

const LS_SESSION = 'rr.hud.chatSession'
const LS_PROMPT = 'rr.hud.chatPromptId'

const sessions = ref<ChatSession[]>([])
const activeId = ref<number | null>(null)
const messages = ref<ChatMessage[]>([])
const models = ref<ChatModelConfig[]>([])
const modelName = ref('')
const input = ref('')
const streaming = ref(false)
const draft = ref('')
const error = ref('')
const msgsEl = ref<HTMLElement | null>(null)
const busy = ref(false)
/** 设置里落的「默认聊天模型」：新建会话优先用它 */
const preferredModel = ref('')

/* ---------------------------------------------------------------- 提示词
 * 只读提示词百宝箱（snippets）：舱内选用 / 切换，不在这里新建、改名、删除。
 * 选中的 id 落 localStorage，重开进程还在；重开时输入框为空则把内容回填，
 * 「选用」= 把提示词放到输入框，发不发由人决定（不替人发消息）。
 */
const snippets = ref<Snippet[]>([])
const promptId = ref<number | null>(null)
const promptOpen = ref(false)
const promptErr = ref('')
const promptBar = ref<HTMLElement | null>(null)

const activePrompt = computed(
  () => snippets.value.find((s) => s.id === promptId.value) ?? null,
)

function persistPrompt(id: number | null) {
  try {
    if (id == null) localStorage.removeItem(LS_PROMPT)
    else localStorage.setItem(LS_PROMPT, String(id))
  } catch {
    /* ignore */
  }
}

function promptPreview(text: string): string {
  const flat = (text || '').replace(/\s+/g, ' ').trim()
  return flat.length > 46 ? flat.slice(0, 46) + '…' : flat || '（空内容）'
}

async function refreshSnippets() {
  if (!isTauri()) return
  try {
    snippets.value = await tauriApi.listSnippets()
  } catch (e) {
    promptErr.value = String(e)
    return
  }
  // 库里那条已被删掉：清掉悬挂的选中态
  if (promptId.value != null && !snippets.value.some((s) => s.id === promptId.value)) {
    promptId.value = null
    persistPrompt(null)
  }
}

async function loadPrompts() {
  await refreshSnippets()
  if (!isTauri()) return
  const saved = Number(localStorage.getItem(LS_PROMPT) || 0)
  const hit = snippets.value.find((s) => s.id === saved)
  if (!hit) {
    promptId.value = null
    persistPrompt(null)
    return
  }
  promptId.value = hit.id
  if (!input.value.trim()) input.value = hit.content
}

/** 每次开面板都重拉一次：主窗刚加的提示词不用重开对话就能看见 */
function togglePrompts() {
  promptOpen.value = !promptOpen.value
  if (promptOpen.value) void refreshSnippets()
}

function applyPrompt(s: Snippet) {
  const prev = activePrompt.value
  const cur = input.value
  // 上一版提示词没被手改过 → 直接换掉；否则保留手写正文，把提示词放到前面
  const untouched = prev ? cur.trim() === prev.content.trim() : !cur.trim()
  const base = untouched ? '' : cur
  input.value = base ? `${s.content}\n${base}` : s.content
  promptId.value = s.id
  persistPrompt(s.id)
  promptOpen.value = false
  void nextTick(() => document.querySelector<HTMLTextAreaElement>('.composer textarea')?.focus())
}

function clearPrompt() {
  const prev = activePrompt.value
  if (prev && input.value.trim() === prev.content.trim()) input.value = ''
  promptId.value = null
  persistPrompt(null)
}

function onDocPointer(e: MouseEvent) {
  if (!promptOpen.value) return
  if (promptBar.value && e.target instanceof Node && promptBar.value.contains(e.target)) return
  promptOpen.value = false
}

const modelOptions = computed(() => {
  const opts: { value: string; label: string }[] = []
  if (models.value.some((m) => isPlatformModel(m))) {
    opts.push({ value: PLATFORM_ENTRY_NAME, label: PLATFORM_ENTRY_NAME })
  }
  for (const m of models.value) {
    if (isPlatformModel(m)) continue
    opts.push({ value: m.name, label: m.name + (m.has_api_key ? '' : '（未配 Key）') })
  }
  return opts
})

function displayModel(name: string): string {
  const m = models.value.find((x) => x.name === name)
  return m && isPlatformModel(m) ? PLATFORM_ENTRY_NAME : name
}

async function scrollBottom() {
  await nextTick()
  const el = msgsEl.value
  if (el) el.scrollTop = el.scrollHeight
}

async function selectSession(id: number) {
  if (streaming.value) return
  activeId.value = id
  try {
    localStorage.setItem(LS_SESSION, String(id))
  } catch {
    /* ignore */
  }
  const s = sessions.value.find((x) => x.id === id)
  modelName.value = s ? displayModel(s.model_name) : modelName.value
  try {
    messages.value = await tauriApi.listChatMessages(id)
    await scrollBottom()
  } catch (e) {
    error.value = String(e)
  }
}

async function load() {
  if (!isTauri()) return
  try {
    models.value = await tauriApi.getChatModels()
    try {
      const cfg = await tauriApi.getUiConfig()
      preferredModel.value = cfg.chat_selected_model || ''
    } catch {
      /* 老版本无该字段时静默：仍按模型 is_default 兜底 */
    }
    sessions.value = await tauriApi.listChatSessions()
    const remembered = Number(localStorage.getItem(LS_SESSION) || 0)
    const pick =
      sessions.value.find((s) => s.id === remembered)?.id ??
      sessions.value[0]?.id ??
      null
    if (pick != null) {
      await selectSession(pick)
    } else {
      await newSession()
    }
  } catch (e) {
    error.value = String(e)
  }
}

async function newSession() {
  if (streaming.value) return
  try {
    const named = preferredModel.value
      ? models.value.find((m) => displayModel(m.name) === preferredModel.value)
      : undefined
    const fallback = named || models.value.find((m) => m.is_default) || models.value[0]
    const s = await tauriApi.createChatSession({
      modelName: fallback ? (isPlatformModel(fallback) ? PLATFORM_ENTRY_NAME : fallback.name) : undefined,
    })
    sessions.value = [s, ...sessions.value]
    activeId.value = s.id
    modelName.value = displayModel(s.model_name)
    messages.value = []
    error.value = ''
    try {
      localStorage.setItem(LS_SESSION, String(s.id))
    } catch {
      /* ignore */
    }
  } catch (e) {
    error.value = String(e)
  }
}

async function onModelChange() {
  if (activeId.value == null || !modelName.value) return
  try {
    const s = await tauriApi.setChatSessionModel(activeId.value, modelName.value)
    const i = sessions.value.findIndex((x) => x.id === s.id)
    if (i >= 0) sessions.value[i] = s
    await tauriApi.setChatSelectedModel(modelName.value)
  } catch (e) {
    error.value = String(e)
  }
}

async function send() {
  const text = input.value.trim()
  if (!text || streaming.value || busy.value) return
  if (activeId.value == null) await newSession()
  const sid = activeId.value
  if (sid == null) return

  busy.value = true
  error.value = ''
  input.value = ''
  streaming.value = true
  draft.value = ''
  const now = new Date().toISOString()
  messages.value.push({
    id: -1,
    session_id: sid,
    role: 'user',
    content: text,
    created_at: now,
  })
  messages.value.push({
    id: -2,
    session_id: sid,
    role: 'assistant',
    content: '',
    created_at: now,
  })
  await scrollBottom()

  try {
    await tauriApi.sendChatMessage(sid, text, (ev) => {
      if (ev.type === 'chunk') {
        draft.value += ev.content
        const last = messages.value[messages.value.length - 1]
        if (last && last.id === -2) last.content = draft.value
        void scrollBottom()
      } else if (ev.type === 'done') {
        const last = messages.value[messages.value.length - 1]
        if (last && last.id === -2) {
          last.id = ev.message.id
          last.content = ev.message.content
        }
        const i = sessions.value.findIndex((x) => x.id === ev.session.id)
        if (i >= 0) sessions.value[i] = ev.session
      } else if (ev.type === 'error') {
        error.value = ev.message
      }
    })
    // 以落库结果为准（后端可能改名/裁剪）
    messages.value = await tauriApi.listChatMessages(sid)
    const fresh = await tauriApi.listChatSessions()
    sessions.value = fresh
  } catch (e) {
    error.value = String(e)
    const last = messages.value[messages.value.length - 1]
    if (last && last.id === -2 && !last.content) messages.value.pop()
  } finally {
    streaming.value = false
    busy.value = false
    await scrollBottom()
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault()
    void send()
  }
}

onMounted(() => {
  document.addEventListener('click', onDocPointer, true)
  void load()
  void loadPrompts()
})
onBeforeUnmount(() => document.removeEventListener('click', onDocPointer, true))
defineExpose({ load, loadPrompts })
</script>

<template>
  <div class="island-chat" @click.stop>
    <div class="chat-top">
      <select
        v-model="modelName"
        class="cut-sm"
        :disabled="!modelOptions.length"
        title="选择模型（与主窗共用模型配置）"
        @change="onModelChange"
      >
        <option v-if="!modelOptions.length" value="">未配置模型</option>
        <option v-for="o in modelOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
      <button class="btn sm cut-sm" :disabled="streaming" @click="newSession">新会话</button>
      <button class="btn sm cut-sm" @click="$emit('close')">收起</button>
    </div>

    <!-- 功能直达条：AI 对话在所有功能之上，从舱里一步切到任一面板 -->
    <div class="fn-bar">
      <button
        v-for="f in FNS"
        :key="f.k"
        class="fn cut-sm"
        :title="f.tip"
        @click="$emit('open-panel', f.k)"
      >
        {{ f.lab }}
      </button>
    </div>

    <div class="sess-list">
      <button
        v-for="s in sessions"
        :key="s.id"
        class="sess cut-sm"
        :class="{ 'is-on': s.id === activeId }"
        :title="s.title"
        @click="selectSession(s.id)"
      >
        {{ s.title || '新对话' }}
      </button>
    </div>

    <div ref="msgsEl" class="msgs">
      <div v-if="!messages.length" class="chat-empty">
        <b>小岛已上线</b>
        我是通用 AI，问答、起草、记事都行。<br />
        会话落在本机 SQLite，关掉进程再回来还在。
      </div>
      <div
        v-for="m in messages"
        :key="m.id"
        class="msg"
        :class="m.role === 'user' ? 'user' : 'ai'"
      >
        <div class="who">{{ m.role === 'user' ? '我' : 'AI' }}</div>
        <span :class="{ typing: streaming && m.id === -2 }">{{ m.content }}</span>
      </div>
    </div>

    <div v-if="error" class="chat-err">{{ error }}</div>

    <div ref="promptBar" class="prompt-bar">
      <button
        type="button"
        class="prompt-open"
        :class="{ 'is-on': promptOpen }"
        data-prompt-open
        :title="snippets.length ? '从提示词百宝箱选用' : '提示词库为空'"
        :aria-expanded="promptOpen"
        @click="togglePrompts"
      >
        提示词<em v-if="snippets.length">{{ snippets.length }}</em>
      </button>
      <span
        v-if="activePrompt"
        class="prompt-chip"
        data-prompt-chip
        :data-prompt-id="activePrompt.id"
        :title="activePrompt.content"
      >
        {{ activePrompt.title || '未命名提示词' }}
        <button type="button" class="pc-x" data-prompt-clear title="取消选用（不改提示词库）" @click.stop="clearPrompt">×</button>
      </span>
      <div v-if="promptOpen" class="prompt-pop" data-prompt-pop>
        <div v-if="!snippets.length" class="prompt-empty">
          提示词库为空。在主窗「提示词百宝箱」里加条目后，这里就能直接选用。
        </div>
        <button
          v-for="s in snippets"
          :key="s.id"
          type="button"
          class="prompt-item"
          :class="{ 'is-on': s.id === promptId }"
          :data-prompt-item="s.id"
          :title="s.content"
          @click="applyPrompt(s)"
        >
          <span class="pi-t">
            {{ s.title || '未命名提示词' }}
            <i v-if="s.id === promptId">✓ 已选用</i>
          </span>
          <span class="pi-p">{{ promptPreview(s.content) }}</span>
        </button>
      </div>
    </div>
    <div v-if="promptErr" class="chat-err">{{ promptErr }}</div>

    <div class="composer">
      <textarea
        v-model="input"
        class="cut-sm"
        placeholder="输入消息，Ctrl+Enter 发送"
        spellcheck="false"
        @keydown="onKeydown"
      />
      <button class="btn primary cut-sm" :disabled="streaming || !input.trim()" @click="send">
        {{ streaming ? '生成中' : '发送' }}
      </button>
    </div>
  </div>
</template>