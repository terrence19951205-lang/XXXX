/**
 * `ascii-sharks.js`（探索稿 v3 原样搬入的上游压缩代码）的类型声明。
 * 只声明产品用到的表面：构造 OceanEngine → destroy()。
 */
export interface SharkSpec {
  kind: string
  size: number
}

export declare class OceanEngine {
  constructor(canvas: HTMLCanvasElement, sharks?: SharkSpec[])
  destroy(): void
}

export declare class World {
  [key: string]: unknown
}

export declare class AsciiRenderer {
  [key: string]: unknown
}

export declare const AsciiSharks: {
  OceanEngine: typeof OceanEngine
  World: typeof World
  AsciiRenderer: typeof AsciiRenderer
  paintGrid: (...args: unknown[]) => void
}
