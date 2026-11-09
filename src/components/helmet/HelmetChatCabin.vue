<script setup lang="ts">
/**
 * Helmet P0 · 完整对话舱（挂在岛下）
 * 复用 x-hub 对话数据层：chat_sessions / chat_messages / 模型配置，
 * 与主窗、独立对话窗共用一套会话，不绑 claw。
 */
import { computed, nextTick, onMounted, ref } from 'vue'
import {
  PLATFORM_ENTRY_NAME,
  isPlatformModel,
  isTauri,
  tauriApi,
  type ChatMessage,
  type ChatModelConfig,
  type ChatSession,
} from '../../api/tauri'

const emit = defineEmits<{ (e: 'close'): void; (e: 'toast', msg: string): void }>()

const LS_SESSION = 'rr.hud.chatSession'

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

onMounted(load)
defineExpose({ load })
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