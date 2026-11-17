<script setup lang="ts">
/**
 * Helmet · 速达（资源启动器）
 *
 * 这里抄的是 x-hub「速达」的**功能**，不是它的界面：
 *  - 列表/搜索（list_resources）
 *  - 启动 / 以管理员启动（launch_resource / launch_resource_as_admin）
 *  - 在资源管理器里定位（reveal_resource_in_explorer）
 *  - 新增 / 编辑 / 删除（create_resource / update_resource / delete_resource）
 * 全套后端能力 x-hub 本来就有，壳里不该只有「列出来 + 点一下」。
 */
import { computed, onMounted, ref } from 'vue'
import { isTauri, tauriApi, type Resource } from '../../api/tauri'

const emit = defineEmits<{
  (e: 'launched', name: string): void
  (e: 'toast', msg: string): void
}>()

type Kind = Resource['kind']

const items = ref<Resource[]>([])
const kw = ref('')
const err = ref('')
const busyId = ref<number | null>(null)
/** 正在二次确认删除的条目 */
const confirmId = ref<number | null>(null)
/** 正在编辑的条目（null = 新增） */
const formFor = ref<Resource | null>(null)
const form = ref<{ kind: Kind; name: string; target: string }>({ kind: 'app', name: '', target: '' })
const formOpen = ref(false)

const visible = computed(() => {
  const q = kw.value.trim().toLowerCase()
  if (!q) return items.value
  return items.value.filter(
    (r) =>
      r.name.toLowerCase().includes(q) ||
      (r.description || '').toLowerCase().includes(q) ||
      (r.category || '').toLowerCase().includes(q) ||
      (r.target || '').toLowerCase().includes(q),
  )
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

async function launch(r: Resource, asAdmin = false) {
  if (busyId.value != null) return
  busyId.value = r.id
  try {
    if (asAdmin) await tauriApi.launchResourceAsAdmin(r.id)
    else await tauriApi.launchResource(r.id)
    emit('launched', r.name)
  } catch (e) {
    err.value = String(e)
    emit('toast', '启动失败：' + String(e).slice(0, 60))
  } finally {
    busyId.value = null
  }
}

async function reveal(r: Resource) {
  try {
    await tauriApi.revealResourceInExplorer(r.id)
  } catch (e) {
    emit('toast', '定位失败：' + String(e).slice(0, 60))
  }
}

function openAdd() {
  formFor.value = null
  form.value = { kind: 'app', name: '', target: '' }
  formOpen.value = true
}

function openEdit(r: Resource) {
  formFor.value = r
  form.value = { kind: r.kind, name: r.name, target: r.target }
  formOpen.value = true
}

async function submit() {
  const name = form.value.name.trim()
  const target = form.value.target.trim()
  if (!name || !target) {
    emit('toast', '名称和目标都不能空')
    return
  }
  try {
    if (formFor.value) {
      await tauriApi.updateResource({
        id: formFor.value.id,
        kind: form.value.kind,
        name,
        target,
      })
    } else {
      await tauriApi.createResource({ kind: form.value.kind, name, target })
    }
    formOpen.value = false
    await load()
    emit('toast', formFor.value ? '已保存' : '已添加')
    formFor.value = null
  } catch (e) {
    emit('toast', '保存失败：' + String(e).slice(0, 60))
  }
}

async function remove(r: Resource) {
  if (confirmId.value !== r.id) {
    confirmId.value = r.id
    return
  }
  confirmId.value = null
  try {
    await tauriApi.deleteResource(r.id)
    await load()
    emit('toast', '已删除')
  } catch (e) {
    emit('toast', '删除失败：' + String(e).slice(0, 60))
  }
}

onMounted(load)
defineExpose({ load })
</script>

<template>
  <div class="work">
    <div class="work-hd">
      <div class="title">速达 <span class="en">Launch</span></div>
      <button class="btn sm cut-sm" title="新增一条" @click="openAdd">＋ 新增</button>
      <button class="btn sm cut-sm" @click="load">刷新</button>
    </div>
    <div class="work-bd">
      <div v-if="formOpen" class="res-form cut-sm">
        <div class="rf-row">
          <select v-model="form.kind" class="field cut-sm rf-kind">
            <option value="app">应用</option>
            <option value="web">网页</option>
            <option value="file">文件</option>
          </select>
          <input v-model="form.name" class="field cut-sm" placeholder="名称" spellcheck="false" />
        </div>
        <input
          v-model="form.target"
          class="field cut-sm"
          :placeholder="form.kind === 'web' ? 'https://…' : '可执行文件 / 文件路径'"
          spellcheck="false"
        />
        <div class="rf-acts">
          <button class="btn sm cut-sm" @click="formOpen = false">取消</button>
          <button class="btn sm primary cut-sm" @click="submit">
            {{ formFor ? '保存' : '添加' }}
          </button>
        </div>
      </div>

      <input v-model="kw" class="field cut-sm" placeholder="搜应用 / 网页 / 文件…" spellcheck="false" />

      <div class="list">
        <div v-if="!visible.length" class="empty">
          {{ items.length ? '没有匹配项。' : '速达还是空的 —— 点右上「＋ 新增」加一条，或在原版主窗「速达」里批量导入。' }}
        </div>
        <div v-for="r in visible" :key="r.id" class="res-row cut-sm">
          <button class="res-main" :title="r.target" @click="launch(r)">
            <span class="ico">{{ kindLabel(r) }}</span>
            <span class="res-txt">
              <span class="t">{{ r.name }}</span>
              <span class="m">{{ r.description || r.category || r.target }}</span>
            </span>
          </button>
          <div class="res-acts">
            <button class="mini" title="以管理员身份启动" @click.stop="launch(r, true)">管理员</button>
            <button class="mini" title="在资源管理器里定位" @click.stop="reveal(r)">定位</button>
            <button class="mini" title="编辑" @click.stop="openEdit(r)">编辑</button>
            <button
              class="mini danger"
              :title="confirmId === r.id ? '再点一次确认删除' : '删除'"
              @click.stop="remove(r)"
            >
              {{ confirmId === r.id ? '确认删' : '删' }}
            </button>
          </div>
        </div>
      </div>
      <div class="panel-hint">点条目即调起；鼠标移上去有「管理员 / 定位 / 编辑 / 删除」。</div>
      <div v-if="err" class="panel-hint">{{ err }}</div>
    </div>
  </div>
</template>

<style scoped>
.res-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
  margin-bottom: 8px;
  background: rgba(0, 229, 255, 0.04);
  box-shadow: inset 0 0 0 1px rgba(0, 229, 255, 0.18);
}
.rf-row {
  display: flex;
  gap: 6px;
}
.rf-kind {
  width: 72px;
  flex: 0 0 auto;
}
.rf-acts {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
}
.res-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 4px 2px 2px;
  background: rgba(255, 255, 255, 0.02);
}
.res-row:hover {
  background: rgba(0, 229, 255, 0.08);
}
.res-main {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 2px;
  text-align: left;
}
.res-txt {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.res-txt .t {
  font-size: 11.5px;
  color: var(--t1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.res-txt .m {
  font-size: 9px;
  color: var(--t3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.res-acts {
  display: none;
  gap: 2px;
  flex: 0 0 auto;
}
.res-row:hover .res-acts {
  display: flex;
}
.mini {
  padding: 2px 5px;
  border-radius: 4px;
  font-size: 9px;
  color: var(--t2);
  background: rgba(0, 229, 255, 0.08);
  box-shadow: inset 0 0 0 1px rgba(0, 229, 255, 0.18);
}
.mini:hover {
  color: var(--t1);
  background: rgba(0, 229, 255, 0.18);
}
.mini.danger {
  color: var(--magenta);
  box-shadow: inset 0 0 0 1px rgba(255, 46, 151, 0.28);
}
</style>