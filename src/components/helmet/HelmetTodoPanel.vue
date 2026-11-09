<script setup lang="ts">
/**
 * Helmet P0 · 今日待办
 * 复用 x-hub `todos` 表（create_todo / update_todo / toggle_todo / delete_todo），
 * 不做平行数据；杀进程后从 SQLite 原样恢复。
 */
import { computed, onMounted, ref } from 'vue'
import { isTauri, tauriApi, type Todo } from '../../api/tauri'

const emit = defineEmits<{
  (e: 'count', n: number): void
  (e: 'toast', msg: string): void
  (e: 'close'): void
}>()

const todos = ref<Todo[]>([])
const draft = ref('')
const filter = ref<'open' | 'done'>('open')
const busy = ref(false)
const err = ref('')

const shown = computed(() => {
  const list = todos.value.filter((t) => (filter.value === 'open' ? !t.done : t.done))
  return list.sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
})
const openCount = computed(() => todos.value.filter((t) => !t.done).length)

async function load() {
  if (!isTauri()) return
  try {
    todos.value = await tauriApi.listTodos()
    emit('count', openCount.value)
    err.value = ''
  } catch (e) {
    err.value = String(e)
  }
}

async function add() {
  const title = draft.value.trim()
  if (!title || busy.value) return
  busy.value = true
  try {
    const t = await tauriApi.createTodo(title)
    todos.value = [t, ...todos.value]
    draft.value = ''
    emit('count', openCount.value)
    emit('toast', '待办已落盘')
  } catch (e) {
    err.value = String(e)
  } finally {
    busy.value = false
  }
}

async function toggle(t: Todo) {
  try {
    const next = await tauriApi.toggleTodo(t.id)
    const i = todos.value.findIndex((x) => x.id === t.id)
    if (i >= 0) todos.value[i] = next
    emit('count', openCount.value)
  } catch (e) {
    err.value = String(e)
  }
}

async function rename(t: Todo) {
  const title = t.title.trim()
  if (!title) {
    await load()
    return
  }
  try {
    await tauriApi.updateTodo(t.id, title, t.priority)
  } catch (e) {
    err.value = String(e)
  }
}

async function remove(t: Todo) {
  try {
    await tauriApi.deleteTodo(t.id)
    todos.value = todos.value.filter((x) => x.id !== t.id)
    emit('count', openCount.value)
  } catch (e) {
    err.value = String(e)
  }
}

onMounted(load)
defineExpose({ load })
</script>

<template>
  <div class="work">
    <div class="work-hd">
      <div class="title">待办 <span class="en">Ops · Todo</span></div>
      <button class="close cut-sm" title="收起 shell-hub" @click="$emit('close')">✕</button>
    </div>
    <div class="work-bd">
      <div class="row-add">
        <input
          v-model="draft"
          class="field cut-sm"
          placeholder="新增待办，回车添加"
          @keydown.enter.prevent="add"
        />
        <button class="btn primary sm cut-sm" :disabled="busy" @click="add">添加</button>
      </div>
      <div class="row-add">
        <button
          class="btn sm cut-sm"
          :class="{ primary: filter === 'open' }"
          @click="filter = 'open'"
        >
          未完成 {{ openCount }}
        </button>
        <button
          class="btn sm cut-sm"
          :class="{ primary: filter === 'done' }"
          @click="filter = 'done'"
        >
          已完成 {{ todos.length - openCount }}
        </button>
      </div>
      <div class="list">
        <div v-if="!shown.length" class="empty">
          {{ filter === 'open' ? '今天还没有待办。写一条，回车即落盘。' : '还没有完成的待办。' }}
        </div>
        <div
          v-for="t in shown"
          :key="t.id"
          class="todo-row"
          :class="{ 'is-done': t.done }"
        >
          <span class="chk" :title="t.done ? '标记未完成' : '完成'" @click="toggle(t)">
            {{ t.done ? '✓' : '' }}
          </span>
          <input
            v-model="t.title"
            class="tt"
            spellcheck="false"
            @keydown.enter.prevent="($event.target as HTMLInputElement).blur()"
            @blur="rename(t)"
          />
          <button class="del" title="删除" @click="remove(t)">✕</button>
        </div>
      </div>
      <div v-if="err" class="panel-hint">{{ err }}</div>
    </div>
  </div>
</template>