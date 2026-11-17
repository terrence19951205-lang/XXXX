/**
 * HUD 面板之间的轻量通道（P1-3）：搜索「打开」→ 跳到对应功能的三栏并选中那一条。
 * 只放一次性的「待选中」意图，面板挂载/变化时取走即清。
 */
import { ref } from 'vue'

export const pendingTodoId = ref<number | null>(null)

export function takePendingTodo(): number | null {
  const v = pendingTodoId.value
  pendingTodoId.value = null
  return v
}

export const pendingNoteId = ref<number | null>(null)
