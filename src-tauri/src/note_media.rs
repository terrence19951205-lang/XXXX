//! P1-3 笔记拖入图片：HUD 窗口开着 Tauri 原生文件拖放拦截（速达拖入程序要用），
//! WebView 收不到 HTML5 的文件 drop。笔记面板改听 onDragDropEvent 拿到文件路径，
//! 经这里读出图片字节交还前端，前端再走编辑器原有的「粘贴图片」路径
//! （saveNoteImageFile → import_note_image 落盘 notes/images），与粘贴完全同一条链路。

use base64::Engine;
use serde::Serialize;

const EXTS: &[&str] = &["png", "jpg", "jpeg", "webp", "bmp", "gif"];
const MAX_BYTES: u64 = 10 * 1024 * 1024;

#[derive(Debug, Serialize)]
pub struct DropImage {
    pub b64: String,
    pub mime: String,
    pub name: String,
}

#[tauri::command]
pub fn read_drop_image(path: String) -> Result<DropImage, String> {
    let p = std::path::Path::new(&path);
    let ext = p
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| e.to_ascii_lowercase())
        .unwrap_or_default();
    if !EXTS.contains(&ext.as_str()) {
        return Err("仅支持拖入 png/jpg/webp/bmp/gif 图片".into());
    }
    let meta = std::fs::metadata(p).map_err(|e| format!("读取文件失败: {e}"))?;
    if meta.len() > MAX_BYTES {
        return Err("图片超过 10MB，请压缩后再试".into());
    }
    let bytes = std::fs::read(p).map_err(|e| format!("读取文件失败: {e}"))?;
    let mime = match ext.as_str() {
        "jpg" | "jpeg" => "image/jpeg",
        "webp" => "image/webp",
        "bmp" => "image/bmp",
        "gif" => "image/gif",
        _ => "image/png",
    }
    .to_string();
    Ok(DropImage {
        b64: base64::engine::general_purpose::STANDARD.encode(bytes),
        mime,
        name: p.file_name().and_then(|n| n.to_str()).unwrap_or("image").to_string(),
    })
}
