/**
 * 笔记缩略图（P1-3）：取正文里第一张图片的地址。
 * 笔记图片落盘在 数据根/notes/images，正文里写的是 `![](http://xhub-note.localhost/<hash>.<ext>)`
 *（协议名是内部标识，界面不显示）；也兼容 <img src> 与 data:/https 图片。
 */
const MD_IMG = /!\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)/
const HTML_IMG = /<img[^>]+src=["']([^"']+)["']/i

export function noteThumb(content: string | null | undefined): string {
  if (!content) return ''
  const a = MD_IMG.exec(content)
  const b = HTML_IMG.exec(content)
  const pick = a && b ? (a.index <= b.index ? a[1] : b[1]) : a ? a[1] : b ? b[1] : ''
  if (!pick) return ''
  if (/^(https?:|data:image\/|blob:|asset:)/i.test(pick)) return pick
  return ''
}

/** 纯文本摘要：去掉图片 / 链接 / Markdown 记号 */
export function noteSnippet(content: string | null | undefined, max = 240): string {
  if (!content) return ''
  return content
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '［图片］')
    .replace(/<img[^>]*>/gi, '［图片］')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[#>*_`~-]{1,3}\s?/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, max)
}
