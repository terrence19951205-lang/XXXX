/**
 * shell-hub 功能开关（P1-3）：可见入口的唯一开关处。
 *
 * - extensions：扩展 / 扩展中心 / Skills 的全部可见入口
 * - account：登录 / 账号 / 平台额度（依赖账号登录）的全部可见入口
 *
 * 只隐藏入口，底层代码与数据不删；以后要放回来改这里一处即可。
 * 用法：各处入口统一判 `FEATURES.xxx`，不要散落特判。
 */
export const FEATURES = {
  extensions: false,
  account: false,
} as const

/** 产品显示名（窗口/托盘/文案统一用它；内部标识 x-hub 不动） */
export const PRODUCT_NAME = 'shell hub'

/** 设置页大类 / 分区是否可见 */
export function settingsGroupVisible(id: string): boolean {
  if (id === 'extensions') return FEATURES.extensions
  if (id === 'account') return FEATURES.account
  return true
}

export function settingsSectionVisible(id: string): boolean {
  if (id === 'extensions' || id === 'skills') return FEATURES.extensions
  if (id === 'account' || id === 'credit') return FEATURES.account
  return true
}

/** 设置搜索/使用说明里与隐藏功能相关的条目（按标题关键词） */
export function settingsTitleVisible(title: string): boolean {
  if (!FEATURES.extensions && /扩展|Skills|skill/i.test(title)) return false
  if (!FEATURES.account && /账号|登录|额度|积分|邀请码|平台模型|平台额度/.test(title)) return false
  return true
}
