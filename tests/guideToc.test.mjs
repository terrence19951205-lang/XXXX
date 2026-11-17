/**
 * 内置《使用说明》分章口径单测（直接拿 docs/user-guide.md 跑）：
 *   node --test tests/guideToc.test.mjs
 *
 * 锁三件事：① 现行章节全在、按顺序；② 每章至少有内容；③ 锚点唯一且能对上目录。
 * 文档增删章节时这条会先红，提醒同步面板里的目录（目录是运行时从正文推导的，不会失真）。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { countOccurrences, slugifyHeading, splitGuideDocument } from '../src/utils/guideToc.ts'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const md = readFileSync(join(root, 'docs/user-guide.md'), 'utf8')
const doc = splitGuideDocument(md)

test('文档标题与前言被正确识别', () => {
  assert.equal(doc.title, 'shell hub 使用说明')
  assert.doesNotMatch(doc.preamble, /适用版本|v0\.9\.4/)
  assert.doesNotMatch(doc.preamble, /设置\s*→\s*外观/)
  // 前言里的目录链接列表不应混进第一章正文
  assert.match(doc.preamble, /阅读约定/)
})

test('13 个章节按顺序切出，标题不带 Markdown 标记', () => {
  assert.equal(doc.chapters.length, 13)
  assert.deepEqual(
    doc.chapters.map((c) => c.title),
    [
      '1. 认识 shell hub',
      '2. 全局快捷键',
      '3. 待办',
      '4. 笔记',
      '5. 启动',
      '6. AI 助手',
      '7. 剪贴板历史',
      '8. 全局搜索',
      '9. 系统托盘',
      '10. 设置页逐项地图',
      '11. 数据与维护',
      '12. 应用更新',
      '13. 常见问题',
    ],
  )
  for (const c of doc.chapters) assert.ok(c.title.length > 0)
})

test('每章都有内容（自有正文或三级小节至少其一）', () => {
  for (const c of doc.chapters) {
    const hasOwnBody = c.body.length > 0
    const hasSectionBody = c.sections.length > 0 && c.sections.some((s) => s.body.length > 0)
    assert.ok(hasOwnBody || hasSectionBody, `「${c.title}」正文为空`)
  }
})

test('章节锚点唯一，且能用于同页跳转', () => {
  const ids = doc.chapters.flatMap((c) => [c.id, ...c.sections.map((s) => s.id)])
  assert.equal(new Set(ids).size, ids.length)
  for (const id of ids) {
    assert.match(id, /^[a-z0-9\p{L}_-]+$/u, `锚点形状异常：${id}`)
  }
})

test('slugifyHeading 与 GitHub 口径一致', () => {
  assert.equal(slugifyHeading('1. 认识 shell hub'), '1-认识-shell-hub')
  assert.equal(slugifyHeading('5.8 一键美化与 AI 深度整理'), '58-一键美化与-ai-深度整理')
  assert.equal(slugifyHeading('15. 常见问题'), '15-常见问题')
})

test('四反引号围栏里的伪标题不会被当成章节', () => {
  const sample = ['# T', '', '## A', '', '````md', '## 假标题', '````', '', '## B'].join('\n')
  const parsed = splitGuideDocument(sample)
  assert.deepEqual(parsed.chapters.map((c) => c.title), ['A', 'B'])
})

test('重名标题自动加序号，不产生重复锚点', () => {
  const parsed = splitGuideDocument('# T\n\n## 同一节\n\n## 同一节')
  assert.deepEqual(parsed.chapters.map((c) => c.id), ['同一节', '同一节-2'])
})

test('正文与现行产品一致：不用旧产品名/旧版本号，数据目录仍是真实的 x-hub 路径', () => {
  const parts = [doc.title, doc.preamble, ...doc.chapters.flatMap((c) => [c.title, c.body, ...c.sections.flatMap((s) => [s.title, s.body])])]
  const body = parts.join('\n')
  assert.doesNotMatch(body, /v0\.9\.4/)
  assert.doesNotMatch(body, /认识 x-hub|x-hub 使用说明/)
  assert.doesNotMatch(body, /AppData\\Roaming\\shell-hub|%APPDATA%\\shell-hub/)
  assert.match(body, /AppData\\Roaming\\x-hub/)
  for (const term of ['工作台', 'Bento', '扩展中心', '悬浮球', '环形菜单', '主窗口', '速达', '速记']) {
    assert.equal(body.includes(term), false, `不应再把「${term}」当现行功能来写`)
  }
})

test('目录内搜索按关键词计数（大小写不敏感）', () => {
  assert.equal(countOccurrences('Ctrl+K 与 ctrl+k', 'ctrl+k'), 2)
  assert.equal(countOccurrences('没有命中', '壁纸'), 0)
  assert.equal(countOccurrences('任意文本', '   '), 0)
})
