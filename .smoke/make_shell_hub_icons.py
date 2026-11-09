"""从 .refs/shell-hub-icons 的定稿素材生成 Tauri 构建用图标。

只用设计师交付的那一套（深色底 #02040A + 青 #00E5FF 几何 S + hex ring），
不重绘、不改色：PNG 原样复制，ICO/ICNS 只做多尺寸封装（PIL 缩放同一张母版）。
"""
import os
import shutil

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, ".refs", "shell-hub-icons")
DST = os.path.join(ROOT, "src-tauri", "icons")

# 原样复制的定稿位图（尺寸与文件名对齐 Tauri 约定）
COPY = {
    "shell-hub-icon-32.png": "shell-hub-32.png",
    "shell-hub-icon-48.png": "shell-hub-48.png",
    "shell-hub-icon-128.png": "shell-hub-128.png",
    "shell-hub-icon-256.png": "shell-hub-256.png",
    "shell-hub-icon-1024.png": "shell-hub-1024.png",
}

ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
ICNS_SIZES = [(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)]


def main() -> None:
    for src, dst in COPY.items():
        shutil.copyfile(os.path.join(SRC, src), os.path.join(DST, dst))

    master = Image.open(os.path.join(SRC, "shell-hub-icon-1024.png")).convert("RGBA")
    # Windows 资源（exe 图标 + 任务栏 + 托盘 default_window_icon）走这个 ico
    master.resize((256, 256), Image.LANCZOS).save(
        os.path.join(DST, "shell-hub-icon.ico"), format="ICO", sizes=ICO_SIZES
    )

    # macOS 包用（--no-bundle 不参与，但构建入口保持一致）
    try:
        master.save(os.path.join(DST, "shell-hub-icon.icns"), format="ICNS", sizes=ICNS_SIZES)
        icns = "ok"
    except Exception as e:  # noqa: BLE001
        icns = f"skip({e})"

    # 报告封装结果（不打印图像内容）
    for name in ("shell-hub-icon.ico", "shell-hub-32.png", "shell-hub-256.png", "shell-hub-1024.png"):
        p = os.path.join(DST, name)
        print(name, os.path.getsize(p), "bytes")
    ico = Image.open(os.path.join(DST, "shell-hub-icon.ico"))
    print("ico frames:", sorted(ico.info.get("sizes", [])) if ico.info.get("sizes") else "n/a")
    print("icns:", icns)


if __name__ == "__main__":
    main()