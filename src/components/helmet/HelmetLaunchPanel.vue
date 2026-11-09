<script setup lang="ts">
/**
 * Helmet P0 · 启动常用工具
 * 复用 x-hub `resources`（速达：应用 / 网页 / 文件）+ `launch_resource`。
 * 调起后收起头盔（回到穿透区），不在头盔里重造启动器数据。
 */
import { computed, onMounted, ref } from 'vue'
import { isTauri, tauriApi, type Resource } from '../../api/tauri'

const emit = defineEmits<{
  (e: 'launched', name: string): void
  (e: 'toast', msg: string): void
}>()

const items = ref<Resource[]>([])
const kw = ref('')
const err = ref('')
const busyId = ref<number | null>(null)

const visible = computed(() => {
  const q = kw.value.trim().toLowerCase()
  const list = q
    ? items.value.filter(
        (r) =>
          r.name.toLowerCase().includes(q) ||
          (r.description || '').toLowerCase().includes(q) ||
          (r.category || '').toLowerCase().includes(q),
      )
    : items.value
  return list.slice(0, 40)
})

function kindLabel(r: Resource) {
  return r.kind === 'app' ? 'APP' : r.kind === 'web' ? 'WEB' : 'FILE'
}

async function load() {
  if (!isTauri()) return
  try {
    items.value = await tauriApi.listResources()
    err.value = ''
  } catch (e) {
    err.value = String(e)
  }
}

async function launch(r: Resource) {
  if (busyId.value != null) return
  busyId.value = r.id
  try {
    await tauriApi.launchResource(r.id)
    emit('launched', r.name)
  } catch (e) {
    err.value = String(e)
    emit('toast', '启动失败：' + String(e).slice(0, 60))
  } finally {
    busyId.value = null
  }
}

onMounted(load)
defineExpose({ load })
</script>

<template>
  <div class="work">
    <div class="work-hd">
      <div class="title">速达 <span class="en">Launch</span></div>
      <button class="btn sm cut-sm" @click="load">刷新</button>
    </div>
    <div class="work-bd">
      <div class="row-add">
        <input v-model="kw" class="field cut-sm" placeholder="搜应用 / 网页 / 文件…" spellcheck="false" />
      </div>
      <div class="list">
        <div v-if="!visible.length" class="empty">
          {{ items.length ? '没有匹配项。' : '速达还是空的。在主窗「速达」里添加常用应用 / 网页 / 文件，这里会同步出现。' }}
        </div>
        <button v-for="r in visible" :key="r.id" class="launch-item cut-sm" @click="launch(r)">
          <span class="ico">{{ kindLabel(r) }}</span>
          <span>
            <span class="t">{{ r.name }}</span>
            <span class="m">{{ r.description || r.category || r.target }}</span>
          </span>
        </button>
      </div>
      <div class="panel-hint">点一条即调起，并收起 shell-hub 回到穿透区。</div>
      <div v-if="err" class="panel-hint">{{ err }}</div>
    </div>
  </div>
</template>