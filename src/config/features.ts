/**
 * shell-hub 功能开关：可见入口的唯一开关处。
 *
 * 只隐藏入口，底层代码与数据不删；以后要放回来改这里一处即可。
 * 用法：各处入口统一判 `FEATURES.xxx`，不要散落特判。
 */
export const FEATURES = {
  extensions: false,
  account: false,
  /** 原版主窗外观（主题 / 壁纸 / 侧栏 / 模糊等）；HUD 已是固定深色壳 */
  appearance: false,
  /** 原版工作台布局 / 语录 / 名言来源（倒计时提示音已挪到小岛） */
  workbench: false,
  /** 桌面悬浮球及环形菜单 */
  floatingBall: false,
  /** AI 独立窗口面板（对话已在岛下舱里） */
  aiPanel: false,
  /** 联网、天气城市 */
  onlineWeather: false,
  /** 启动「内嵌面板（主窗口内）」及工具栏、右键「在内嵌面板打开」 */
  embedPanel: false,
  /** 关于页指向上游仓库的「版本历史 / 开源许可」外链 */
  upstreamLinks: false,
} as const

/** 产品显示名（窗口/托盘/文案统一用它；内部标识 x-hub 不动） */
export const PRODUCT_NAME = 'shell hub'

/** 设置页大类是否可见 */
export function settingsGroupVisible(id: string): boolean {
  if (id === 'extensions') return FEATURES.extensions
  if (id === 'account') return FEATURES.account
  if (id === 'appearance') return FEATURES.appearance
  if (id === 'workbench') return FEATURES.workbench
  return true
}

/** 设置页分区是否可见 */
export function settingsSectionVisible(id: string): boolean {
  if (id === 'extensions' || id === 'skills') return FEATURES.extensions
  if (id === 'account' || id === 'credit') return FEATURES.account
  if (id === 'appearance') return FEATURES.appearance
  if (id === 'workbench') return FEATURES.workbench
  if (id === 'ball') return FEATURES.floatingBall
  if (id === 'ai') return FEATURES.aiPanel
  if (id === 'online') return FEATURES.onlineWeather
  return true
}

/** 设置搜索/使用说明里与隐藏功能相关的条目（按标题关键词） */
export function settingsTitleVisible(title: string): boolean {
  if (!FEATURES.extensions && /扩展|Skills|skill/i.test(title)) return false
  if (!FEATURES.account && /账号|登录|额度|积分|邀请码|平台模型|平台额度/.test(title)) return false
  if (!FEATURES.floatingBall && /悬浮球|环形菜单/.test(title)) return false
  if (!FEATURES.appearance && /主题模式|主题配色|强调色|应用壁纸|壁纸蒙版|沉浸模式|背景模糊|卡片玻璃|侧边栏|标题栏小部件/.test(title)) return false
  if (!FEATURES.workbench && /自定义布局|时钟卡片语录|名言来源|工作台/.test(title)) return false
  if (!FEATURES.aiPanel && /独立窗口打开 AI|AI 对话面板/.test(title)) return false
  if (!FEATURES.onlineWeather && /联网功能|天气城市/.test(title)) return false
  if (!FEATURES.embedPanel && /内嵌面板/.test(title)) return false
  if (!FEATURES.upstreamLinks && /开源许可|版本历史/.test(title)) return false
  return true
}

/**
 * 把仍会显示给用户的文案里的旧名换成 shell-hub 口径。
 * 不改数据目录路径（如 AppData\\Roaming\\x-hub）和内部标识。
 */
export function rewriteVisibleCopy(text: string): string {
  return text
    .replace(/设置\s*→\s*功能\s*→\s*速达/g, '设置 → 功能 → 启动')
    .replace(/速达/g, '启动')
    .replace(/速记/g, '笔记')
    .replace(/X-Hub/g, 'shell-hub')
    .replace(/x-hub/gi, (match, offset, src: string) => {
      const prev = src.slice(Math.max(0, offset - 32), offset)
      if (/Roaming\\?$|AppData\\(?:Roaming\\)?$/i.test(prev)) return match
      if (/[\\/]$/.test(prev)) return match
      return 'shell-hub'
    })
}
