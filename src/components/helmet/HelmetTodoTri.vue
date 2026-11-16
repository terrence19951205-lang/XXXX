<script setup lang="ts">
/**
 * Helmet · 待办三栏（P1-3）：左轨 | 列表 | 详情
 *
 * - 列表栏顶部筛选：今日 / 周期 / 日历日期 / 全部（功能内分组 → 筛选，不开第四栏）
 * - 详情栏：标题、备注、截止、周期设置、子待办
 * - 窄屏（与对话舱并存）：详情收进列表，点条目 push 出详情，「‹ 返回」回列表
 *
 * 数据全走原版 store（create/toggle/update/schedule/setTodoRepeat/completeTodoRecurring），
 * 与主窗待办、待办浮窗是同一份；P1-2 的子待办（parent_id）与周期（repeat_mode）沿用。
 */
import { computed, inject, nextTick, onMounted, ref, watch, type Ref } from 'vue'
import { useStore } from '../../stores/workbench'
import { isTauri, tauriApi, type RepeatMode, type Todo } from '../../api/tauri'
import { pendingTodoId } from './hudBus'

const store = useStore()
const toast = inject<((m: string) => void) | null>('hudToast', null)
const narrow = inject<Ref<boolean>>('hudNarrow', ref(false))

type Filter = 'today' | 'repeat' | 'date' | 'all'
const filter = ref<Filter>('today')
const pickDate = ref(dayKey(Date.now()))
const calOpen = ref(false)
const calMonth = ref(startOfMonth(Date.now()))
const showDone = ref(false)
const activeId = ref<number | null>(null)
const draft = ref('')
const ready = ref(false)

onMounted(async () => {
  if (!store.state.loaded) {
    try {
      await store.loadInitialData()
    } catch {
      /* 后端未就绪：空态 */
    }
  }
  ready.value = true
  consumePending()
})

/** 搜索「打开待办」：切到能看到它的筛选并选中 */
function consumePending() {
  const id = pendingTodoId.value
  if (id == null || !ready.value) return
  pendingTodoId.value = null
  const t = store.state.todos.find((x) => x.id === id)
  if (!t) return
  const top = t.parent_id != null ? store.state.todos.find((x) => x.id === t.parent_id) ?? t : t
  filter.value = 'all'
  if (top.done) showDone.value = true
  activeId.value = top.id
}
watch(pendingTodoId, consumePending)

/* ---------- 日期工具 ---------- */
function dayKey(ms: number): string {
  const d = new Date(ms)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
function startOfDay(ms: number): number {
  const d = new Date(ms)
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}
function startOfMonth(ms: number): number {
  const d = new Date(ms)
  return new Date(d.getFullYear(), d.getMonth(), 1).getTime()
}
function keyToMs(key: string, h = 18, m = 0): number {
  const [y, mo, d] = key.split('-').map((x) => parseInt(x, 10))
  return new Date(y, mo - 1, d, h, m, 0, 0).getTime()
}
function createdMs(t: Todo): number {
  const v = Date.parse(t.created_at.replace(' ', 'T'))
  return Number.isFinite(v) ? v : 0
}
function dueLabel(t: Todo): string {
  if (t.due_at == null) return ''
  const today = startOfDay(Date.now())
  const day = startOfDay(t.due_at)
  const d = new Date(t.due_at)
  const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  const diff = Math.round((day - today) / 86400000)
  const head =
    diff === 0 ? '今天' : diff === 1 ? '明天' : diff === -1 ? '昨天' : `${d.getMonth() + 1}/${d.getDate()}`
  return `${head} ${hm}`
}
const REPEAT_LABEL: Record<string, string> = {
  daily: '每天',
  weekdays: '工作日',
  weekly: '每周',
  monthly: '每月',
  yearly: '每年',
  custom: '自定义',
}

/* ---------- 列表 ---------- */
const tops = computed(() => store.state.todos.filter((t) => t.parent_id == null))
const kids = (id: number) => store.state.todos.filter((t) => t.parent_id === id)

function inFilter(t: Todo, f: Filter): boolean {
  const endToday = startOfDay(Date.now()) + 86400000
  if (f === 'today') {
    if (t.done) return !!t.completed_at && startOfDay(Date.parse(t.completed_at.replace(' ', 'T'))) === startOfDay(Date.now())
    if (t.due_at != null) return t.due_at < endToday
    return startOfDay(createdMs(t)) === startOfDay(Date.now())
  }
  if (f === 'repeat') return t.repeat_mode !== 'once'
  if (f === 'date') return t.due_at != null && dayKey(t.due_at) === pickDate.value
  return true
}

const counts = computed(() => ({
  today: tops.value.filter((t) => !t.done && inFilter(t, 'today')).length,
  repeat: tops.value.filter((t) => !t.done && inFilter(t, 'repeat')).length,
  date: tops.value.filter((t) => !t.done && inFilter(t, 'date')).length,
  all: tops.value.filter((t) => !t.done).length,
}))

const rows = computed(() => {
  const list = tops.value.filter((t) => inFilter(t, filter.value) && (showDone.value || !t.done))
  return list.sort((a, b) => {
    if (a.done !== b.done) return a.done ? 1 : -1
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
    const ad = a.due_at ?? Infinity
    const bd = b.due_at ?? Infinity
    if (ad !== bd) return ad - bd
    return createdMs(b) - createdMs(a)
  })
})

const active = computed(() => store.state.todos.find((t) => t.id === activeId.value) ?? null)
const activeKids = computed(() => (active.value ? kids(active.value.id) : []))

watch(rows, (r) => {
  // 当前条目被筛掉/删掉时，宽屏自动落到第一条；窄屏保持在列表
  if (activeId.value != null && !store.state.todos.some((t) => t.id === activeId.value)) activeId.value = null
  if (activeId.value == null && !narrow.value && r.length) activeId.value = r[0].id
})

function select(t: Todo) {
  activeId.value = t.id
}
function back() {
  activeId.value = null
}

async function add() {
  const title = draft.value.trim()
  if (!title) return
  draft.value = ''
  try {
    const t = await store.createTodo(title)
    if (filter.value === 'date') await store.scheduleTodo(t.id, keyToMs(pickDate.value), null)
    if (filter.value === 'repeat') await setRepeat(t, 'daily')
    activeId.value = t.id
  } catch (e) {
    toast?.('新建失败：' + String(e).slice(0, 60))
  }
}

async function toggle(t: Todo) {
  try {
    if (!t.done && t.repeat_mode !== 'once' && t.parent_id == null) {
      await store.completeTodoRecurring(t.id)
      toast?.('已完成本轮，已排到下一次')
    } else {
      await store.toggleTodo(t.id)
    }
  } catch (e) {
    toast?.(String(e).slice(0, 80))
  }
}

/* ---------- 日历筛选 ---------- */
const calCells = computed(() => {
  const first = new Date(calMonth.value)
  const lead = (first.getDay() + 6) % 7
  const days = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate()
  const dueDays = new Set(tops.value.filter((t) => t.due_at != null && !t.done).map((t) => dayKey(t.due_at as number)))
  const cells: { key: string; d: number; has: boolean }[] = []
  for (let i = 0; i < lead; i++) cells.push({ key: '', d: 0, has: false })
  for (let d = 1; d <= days; d++) {
    const key = dayKey(new Date(first.getFullYear(), first.getMonth(), d).getTime())
    cells.push({ key, d, has: dueDays.has(key) })
  }
  return cells
})
const calTitle = computed(() => {
  const d = new Date(calMonth.value)
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月`
})
function shiftMonth(n: number) {
  const d = new Date(calMonth.value)
  calMonth.value = new Date(d.getFullYear(), d.getMonth() + n, 1).getTime()
}
function choose(key: string) {
  if (!key) return
  pickDate.value = key
  filter.value = 'date'
  calOpen.value = false
}
const dateChipLabel = computed(() => {
  const [, m, d] = pickDate.value.split('-')
  return `${parseInt(m, 10)}/${parseInt(d, 10)}`
})

/* ---------- 详情 ---------- */
const titleDraft = ref('')
const descDraft = ref('')
const dueDay = ref('')
/** 详情日期框展示文案（年/月/日数字，如 2026/11/16）；空时显示占位「年/月/日」 */
const dueDayText = ref('')
const dueTime = ref('18:00')
const subDraft = ref('')
const confirmDel = ref(false)

watch(
  active,
  (t) => {
    confirmDel.value = false
    titleDraft.value = t?.title ?? ''
    descDraft.value = t?.description ?? ''
    if (t?.due_at != null) {
      const d = new Date(t.due_at)
      dueDay.value = dayKey(t.due_at)
      dueDayText.value = dueDay.value.replaceAll('-', '/')
      dueTime.value = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
    } else {
      dueDay.value = ''
      dueDayText.value = ''
      dueTime.value = '18:00'
    }
  },
  { immediate: true },
)

/** 把输入解析成 YYYY-MM-DD；支持 2026/11/16、2026-11-16、2026年11月16日。失败返回 null。 */
function parseDueDay(raw: string): string | null {
  const s = raw
    .trim()
    .replace(/[年./]/g, '-')
    .replace(/月/g, '-')
    .replace(/日/g, '')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
  const m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/)
  if (!m) return null
  const y = Number(m[1])
  const mo = Number(m[2])
  const d = Number(m[3])
  const dt = new Date(y, mo - 1, d)
  if (dt.getFullYear() !== y || dt.getMonth() !== mo - 1 || dt.getDate() !== d) return null
  return `${y}-${String(mo).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

function formatDueDay(key: string): string {
  return key.replaceAll('-', '/')
}

function commitDueDay() {
  const parsed = parseDueDay(dueDayText.value)
  if (!parsed) {
    dueDayText.value = dueDay.value ? formatDueDay(dueDay.value) : ''
    return
  }
  dueDay.value = parsed
  dueDayText.value = formatDueDay(parsed)
  void setDue(parsed)
}

async function saveTitle() {
  const t = active.value
  const v = titleDraft.value.trim()
  if (!t || !v || v === t.title) return
  await store.updateTodo(t.id, v, t.priority)
}
async function saveDesc() {
  const t = active.value
  if (!t || descDraft.value === (t.description ?? '')) return
  await store.setTodoDescription(t.id, descDraft.value)
}
async function setDue(key: string | null) {
  const t = active.value
  if (!t) return
  if (key == null) {
    await store.scheduleTodo(t.id, null, t.remind_at)
    return
  }
  const [h, m] = (dueTime.value || '18:00').split(':').map((x) => parseInt(x, 10))
  await store.scheduleTodo(t.id, keyToMs(key, h || 0, m || 0), t.remind_at)
}
function quickDue(offsetDays: number) {
  void setDue(dayKey(Date.now() + offsetDays * 86400000))
}

const REPEATS: { mode: RepeatMode; label: string }[] = [
  { mode: 'once', label: '不重复' },
  { mode: 'daily', label: '每天' },
  { mode: 'weekdays', label: '工作日' },
  { mode: 'weekly', label: '每周' },
  { mode: 'monthly', label: '每月' },
]

async function setRepeat(t: Todo, mode: RepeatMode) {
  // 周期要有锚点：没截止时间先按今天 18:00 排上（与原版编辑弹层同口径：规则按 due_at 推下一次）
  let due = t.due_at
  if (mode !== 'once' && due == null) {
    due = keyToMs(dayKey(Date.now()))
    await store.scheduleTodo(t.id, due, t.remind_at)
  }
  const d = new Date(due ?? Date.now())
  await store.setTodoRepeat(t.id, {
    mode,
    every: null,
    unit: null,
    weekdays: mode === 'weekly' ? 1 << ((d.getDay() + 6) % 7) : null,
    month_day: mode === 'monthly' ? d.getDate() : null,
    month_nth: null,
    end_mode: null,
    end_at: null,
    count: null,
  })
}

async function addSub() {
  const t = active.value
  const v = subDraft.value.trim()
  if (!t || !v) return
  subDraft.value = ''
  await store.createTodo(v, t.id)
}

async function togglePin() {
  const t = active.value
  if (t) await store.setTodoPinned(t.id, !t.pinned)
}

async function remove() {
  const t = active.value
  if (!t) return
  if (!confirmDel.value) {
    confirmDel.value = true
    return
  }
  await store.deleteTodo(t.id)
  activeId.value = null
  toast?.('已删除')
}

async function toggleFloat() {
  if (!isTauri()) return
  try {
    await tauriApi.toggleTodoFloat()
  } catch (e) {
    toast?.(String(e))
  }
}

const listInput = ref<HTMLInputElement | null>(null)
defineExpose({ focusNew: () => nextTick(() => listInput.value?.focus()) })
</script>

<template>
  <div
    class="tri tri-todo"
    :class="{ 'is-narrow': narrow, 'has-detail': narrow && active }"
    data-tri="todos"
  >
    <section class="tri-list">
      <div class="tri-hd">
        <div class="tri-title">待办 <span class="en">Todo</span></div>
        <button class="hud-btn is-sm" type="button" data-todo-float title="桌面常驻小窗，再点一次收回" @click="toggleFloat">
          ⧉ 浮到桌面
        </button>
      </div>
      <div class="tri-filter" data-tri-filter>
        <button class="hud-chip" :class="{ 'is-on': filter === 'today' }" data-filter="today" @click="filter = 'today'">
          今日 <span class="n">{{ counts.today }}</span>
        </button>
        <button class="hud-chip" :class="{ 'is-on': filter === 'repeat' }" data-filter="repeat" @click="filter = 'repeat'">
          周期 <span class="n">{{ counts.repeat }}</span>
        </button>
        <button
          class="hud-chip"
          :class="{ 'is-on': filter === 'date' }"
          data-filter="date"
          @click="calOpen = !calOpen"
        >
          ▦ {{ filter === 'date' ? dateChipLabel : '日历' }}
          <span v-if="filter === 'date'" class="n">{{ counts.date }}</span>
        </button>
        <button class="hud-chip" :class="{ 'is-on': filter === 'all' }" data-filter="all" @click="filter = 'all'">
          全部 <span class="n">{{ counts.all }}</span>
        </button>
        <label class="done-sw" title="列表里显示已完成">
          <input v-model="showDone" type="checkbox" />
          已完成
        </label>
        <div v-if="calOpen" class="cal-pop" data-cal-pop>
          <div class="cal-hd">
            <button class="hud-btn is-sm is-icon" type="button" aria-label="上个月" @click="shiftMonth(-1)">‹</button>
            <span>{{ calTitle }}</span>
            <button class="hud-btn is-sm is-icon" type="button" aria-label="下个月" @click="shiftMonth(1)">›</button>
          </div>
          <div class="cal-grid">
            <span v-for="w in ['一', '二', '三', '四', '五', '六', '日']" :key="w" class="cal-w">{{ w }}</span>
            <button
              v-for="(c, i) in calCells"
              :key="i"
              type="button"
              class="cal-d"
              :class="{ 'is-on': c.key === pickDate, 'has-due': c.has, 'is-today': c.key === dayKey(Date.now()), 'is-blank': !c.key }"
              :disabled="!c.key"
              @click="choose(c.key)"
            >
              {{ c.d || '' }}
            </button>
          </div>
        </div>
      </div>
      <div class="new-row">
        <input
          ref="listInput"
          v-model="draft"
          class="hud-input"
          data-todo-new
          :placeholder="filter === 'date' ? `新建待办（截止 ${dateChipLabel}），回车保存` : '新建待办，回车保存'"
          @keydown.enter.prevent="add"
        />
      </div>
      <div class="tri-scroll">
        <div v-if="!ready" class="hud-loading">正在载入待办…</div>
        <div v-else-if="!rows.length" class="hud-empty">
          <b>{{ filter === 'today' ? '今天没有待办' : filter === 'repeat' ? '还没有周期待办' : filter === 'date' ? '这天没有待办' : '还没有待办' }}</b>
          在上面输入一条，回车即可
        </div>
        <button
          v-for="t in rows"
          :key="t.id"
          type="button"
          class="tri-row todo-tri-row"
          :class="{ 'is-on': t.id === activeId, 'is-done': t.done }"
          :data-todo-id="t.id"
          @click="select(t)"
        >
          <span
            class="chk"
            role="checkbox"
            :aria-checked="t.done"
            :title="t.repeat_mode !== 'once' && !t.done ? '完成本轮' : t.done ? '取消完成' : '完成'"
            @click.stop="toggle(t)"
            >{{ t.done ? '✓' : '' }}</span
          >
          <span class="main">
            <span class="t">{{ t.pinned ? '📌 ' : '' }}{{ t.title }}</span>
            <span class="s">
              <template v-if="dueLabel(t)">{{ dueLabel(t) }}</template>
              <template v-if="t.repeat_mode !== 'once'"> · ⟳ {{ REPEAT_LABEL[t.repeat_mode] || '周期' }}</template>
              <template v-if="kids(t.id).length">
                · 子项 {{ kids(t.id).filter((k) => k.done).length }}/{{ kids(t.id).length }}</template
              >
              <template v-if="!dueLabel(t) && t.repeat_mode === 'once' && !kids(t.id).length">无截止</template>
            </span>
          </span>
        </button>
      </div>
    </section>

    <section class="tri-detail" data-tri-detail>
      <template v-if="active">
        <div class="tri-hd">
          <button class="hud-btn is-sm tri-back" type="button" data-tri-back @click="back">‹ 返回</button>
          <div class="tri-title">详情 <span class="en">Detail</span></div>
          <button class="hud-btn is-sm" type="button" :class="{ 'is-on': active.pinned }" @click="togglePin">
            {{ active.pinned ? '取消置顶' : '置顶' }}
          </button>
        </div>
        <div class="tri-body">
          <div class="tri-field">
            <label>标题</label>
            <input
              v-model="titleDraft"
              class="hud-input"
              data-todo-title
              @blur="saveTitle"
              @keydown.enter.prevent="($event.target as HTMLInputElement).blur()"
            />
          </div>
          <div class="tri-field">
            <label>备注</label>
            <textarea v-model="descDraft" class="hud-textarea" rows="3" placeholder="补充说明（可选）" @blur="saveDesc" />
          </div>
          <div class="tri-field">
            <label>截止</label>
            <div class="chips">
              <button class="hud-chip" type="button" @click="quickDue(0)">今天</button>
              <button class="hud-chip" type="button" @click="quickDue(1)">明天</button>
              <button class="hud-chip" type="button" @click="quickDue(7)">一周后</button>
              <button class="hud-chip" type="button" :disabled="active.due_at == null" @click="setDue(null)">清除</button>
            </div>
            <div class="due-row">
              <!-- 不用原生 type=date：Chromium zh-CN 空值占位会变成 yyyy/mm/日，且露出系统控件 -->
              <input
                v-model="dueDayText"
                class="hud-input due-day-input"
                type="text"
                inputmode="numeric"
                placeholder="年/月/日"
                data-todo-due-day
                autocomplete="off"
                spellcheck="false"
                @change="commitDueDay"
                @keydown.enter.prevent="commitDueDay"
              />
              <input v-model="dueTime" class="hud-input due-time-input" type="time" step="60" @change="dueDay && setDue(dueDay)" />
            </div>
          </div>
          <div class="tri-field" data-todo-repeat>
            <label>周期</label>
            <div class="chips">
              <button
                v-for="r in REPEATS"
                :key="r.mode"
                type="button"
                class="hud-chip"
                :class="{ 'is-on': active.repeat_mode === r.mode }"
                :data-repeat="r.mode"
                @click="setRepeat(active, r.mode)"
              >
                {{ r.label }}
              </button>
              <span v-if="!REPEATS.some((r) => r.mode === active!.repeat_mode)" class="hud-chip is-on">
                {{ REPEAT_LABEL[active.repeat_mode] }}
              </span>
            </div>
            <span v-if="active.repeat_mode !== 'once'" class="tri-label">
              勾选完成 = 完成本轮，自动排到下一次{{ active.due_at != null ? `（当前 ${dueLabel(active)}）` : '' }}
            </span>
          </div>
          <div class="tri-field" data-todo-subs>
            <label>子待办 {{ activeKids.filter((k) => k.done).length }}/{{ activeKids.length }}</label>
            <div v-for="k in activeKids" :key="k.id" class="sub-row" :class="{ 'is-done': k.done }">
              <span class="chk" role="checkbox" :aria-checked="k.done" @click="store.toggleTodo(k.id)">{{ k.done ? '✓' : '' }}</span>
              <span class="st">{{ k.title }}</span>
              <button class="hud-btn is-sm is-icon is-danger" type="button" aria-label="删除子待办" @click="store.deleteTodo(k.id)">✕</button>
            </div>
            <input v-model="subDraft" class="hud-input" data-todo-sub-new placeholder="＋ 子待办，回车添加" @keydown.enter.prevent="addSub" />
          </div>
        </div>
        <div class="tri-acts">
          <button class="hud-btn is-primary" type="button" data-todo-done @click="toggle(active)">
            {{ active.done ? '取消完成' : active.repeat_mode !== 'once' ? '完成本轮' : '完成' }}
          </button>
          <span class="sp" />
          <button class="hud-btn is-danger" type="button" data-todo-del @click="remove">
            {{ confirmDel ? '再点一次删除' : '删除' }}
          </button>
        </div>
      </template>
      <div v-else class="hud-empty"><b>选一条待办</b>右侧显示标题、子待办和周期设置</div>
    </section>
  </div>
</template>

<style scoped>
.tri-todo {
  --tri-list-w: 320px;
}
.tri-filter {
  position: relative;
  align-items: center;
}
.done-sw {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: var(--hud-fs-xs);
  color: var(--hud-t3);
  cursor: pointer;
}
.new-row {
  flex: 0 0 auto;
  padding: 8px 12px 2px;
}
.chk {
  flex: 0 0 auto;
  width: 15px;
  height: 15px;
  margin-top: 2px;
  display: grid;
  place-items: center;
  font-size: 10px;
  color: var(--hud-ink-on-accent);
  border: 1px solid rgba(0, 229, 255, 0.45);
  border-radius: 3px;
  cursor: pointer;
}
.is-done > .chk,
.chk[aria-checked='true'] {
  background: var(--hud-accent);
  border-color: var(--hud-accent);
}
.todo-tri-row.is-done .t,
.sub-row.is-done .st {
  color: var(--hud-t3);
  text-decoration: line-through;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.due-row {
  display: grid;
  grid-template-columns: 1fr 110px;
  gap: 6px;
}
.due-day-input {
  flex: 1 1 9.5em;
  min-width: 9.5em;
}
.due-time-input {
  flex: 0 0 auto;
  width: 8em;
}

.sub-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 0;
}
.sub-row .st {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sub-row .chk {
  margin-top: 0;
}
.cal-pop {
  position: absolute;
  z-index: 5;
  top: 100%;
  left: 12px;
  width: 252px;
  padding: 10px;
  background: #0b0f16;
  border: 1px solid rgba(0, 229, 255, 0.28);
  border-radius: var(--hud-r-lg);
  box-shadow: 0 14px 36px rgba(0, 0, 0, 0.6);
}
.cal-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: var(--hud-fs-sm);
}
.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
}
.cal-w {
  text-align: center;
  font-size: var(--hud-fs-xs);
  color: var(--hud-t3);
}
.cal-d {
  height: 28px;
  font-size: var(--hud-fs-sm);
  font-family: var(--mono);
  color: var(--hud-t1);
  background: transparent;
  border: 0;
  border-radius: var(--hud-r-sm);
  cursor: pointer;
  position: relative;
}
.cal-d:hover:not(:disabled) {
  background: var(--hud-fill-hover);
}
.cal-d.is-today {
  box-shadow: inset 0 0 0 1px rgba(0, 229, 255, 0.4);
}
.cal-d.is-on {
  color: var(--hud-ink-on-accent);
  background: var(--hud-accent);
}
.cal-d.has-due::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: 3px;
  width: 3px;
  height: 3px;
  margin-left: -1.5px;
  border-radius: 50%;
  background: #ff2e97;
}
.cal-d.is-blank {
  cursor: default;
}
</style>
