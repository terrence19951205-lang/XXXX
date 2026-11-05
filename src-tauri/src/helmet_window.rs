//! Helmet 座舱壳 POC-1：旁路全屏透明窗（label=`helmet`），不替换现有仪表盘/浮窗。
//!
//! 约定对齐 recorder / notify：
//! - 启动期 `init` 预创建隐藏常驻；运行期只重定位 + 显隐，绝不 build/destroy（约定 41）
//! - 透明 + 无装饰 + 置顶 + 跳任务栏；铺满主屏 work area
//! - 点击穿透经 `set_ignore_cursor_events`；控件区由前端在命中 `.hit` 时动态关穿透
//!
//! 已知限制（见 docs/helmet-poc1.md）：单窗动态穿透在 Windows 上依赖「穿透开时收不到
//! WebView 指针事件」——前端用光标轮询 + 本模块 `helmet_cursor_local` 兜底，实机仍需验。

use tauri::{AppHandle, Emitter, Manager, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

/// Helmet 窗 label（capabilities / 前端 getCurrentWebview 分流）
pub const HELMET_LABEL: &str = "helmet";

/// 预创建隐藏常驻（lib.rs setup 调用；运行期绝不建窗）
pub fn init(app: &AppHandle) {
    if app.get_webview_window(HELMET_LABEL).is_some() {
        return;
    }
    match build_window(app) {
        Ok(win) => {
            crate::lockdown_webview(&win);
            crate::win_taskbar::apply(&win);
            log::info!("[helmet] 预创建隐藏常驻");
        }
        Err(e) => log::warn!("[helmet] 预创建失败: {e}"),
    }
}

fn build_window(app: &AppHandle) -> Result<WebviewWindow, String> {
    let mut builder = WebviewWindowBuilder::new(
        app,
        HELMET_LABEL,
        // 轻量入口 helmet.html：只挂座舱壳，不加载完整 SPA
        WebviewUrl::App("helmet.html".into()),
    )
    .title("Helmet")
    .inner_size(1280.0, 720.0) // 占位；show 时按主屏 work area 重设
    .decorations(false)
    .transparent(true)
    .always_on_top(true)
    .skip_taskbar(true)
    .resizable(false)
    .maximizable(false)
    .minimizable(false)
    .closable(false)
    .focused(false)
    .visible(false)
    .background_color(tauri::window::Color(0, 0, 0, 0))
    .additional_browser_args(crate::ADDITIONAL_BROWSER_ARGS);

    // 透明窗开系统阴影会出黑描边（notify / recorder 同款）
    #[cfg(target_os = "windows")]
    {
        builder = builder.shadow(false);
    }
    #[cfg(not(target_os = "windows"))]
    {
        builder = builder.shadow(false);
    }

    builder.build().map_err(|e| e.to_string())
}

/// 取主屏工作区（物理 px）；失败则退回 1280×720 @ (0,0)
fn primary_work_area(app: &AppHandle) -> (i32, i32, u32, u32) {
    if let Ok(Some(mon)) = app.primary_monitor() {
        let wa = mon.work_area();
        return (
            wa.position.x,
            wa.position.y,
            wa.size.width,
            wa.size.height,
        );
    }
    (0, 0, 1280, 720)
}

/// 铺满主屏 work area（物理坐标；resizable 临时解锁防 min/max 钳制，同 recorder）
fn fit_primary_work_area(win: &WebviewWindow, app: &AppHandle) {
    let (x, y, w, h) = primary_work_area(app);
    let _ = win.set_resizable(true);
    let _ = win.set_position(tauri::Position::Physical(tauri::PhysicalPosition::new(x, y)));
    let _ = win.set_size(tauri::Size::Physical(tauri::PhysicalSize::new(w, h)));
    let _ = win.set_resizable(false);
}

fn ensure_window(app: &AppHandle) -> Result<WebviewWindow, String> {
    app.get_webview_window(HELMET_LABEL)
        .ok_or_else(|| "Helmet 窗口未就绪，请重启应用".to_string())
}

/// 显示 Helmet：铺满主屏 work area → emit shown → show
pub fn show(app: &AppHandle) -> Result<(), String> {
    let win = ensure_window(app)?;
    fit_primary_work_area(&win, app);
    // 先 emit 再 show：前端据此复位穿透/收起态，避免闪旧帧
    let (x, y, w, h) = primary_work_area(app);
    let _ = app.emit_to(
        HELMET_LABEL,
        "helmet-shown",
        serde_json::json!({ "x": x, "y": y, "width": w, "height": h }),
    );
    crate::webview_mem::on_shown(app, HELMET_LABEL);
    crate::win_taskbar::show(&win);
    log::info!("[helmet] 已显示 {w}x{h} @ ({x},{y})");
    Ok(())
}

/// 隐藏 Helmet：关穿透（避免残留）+ hide
pub fn hide(app: &AppHandle) -> Result<(), String> {
    if let Some(win) = app.get_webview_window(HELMET_LABEL) {
        let _ = win.set_ignore_cursor_events(false);
        let _ = win.hide();
    }
    let _ = app.emit_to(HELMET_LABEL, "helmet-hidden", ());
    crate::webview_mem::on_hidden(app, HELMET_LABEL);
    log::info!("[helmet] 已隐藏");
    Ok(())
}

/// 显隐切换
pub fn toggle(app: &AppHandle) -> Result<bool, String> {
    let win = ensure_window(app)?;
    let visible = win.is_visible().unwrap_or(false);
    if visible {
        hide(app)?;
        Ok(false)
    } else {
        show(app)?;
        Ok(true)
    }
}

/// 设置整窗点击穿透（true = 鼠标穿透到下层桌面/应用）
pub fn set_ignore_cursor_events(app: &AppHandle, ignore: bool) -> Result<(), String> {
    let win = ensure_window(app)?;
    win.set_ignore_cursor_events(ignore)
        .map_err(|e| format!("set_ignore_cursor_events 失败: {e}"))?;
    Ok(())
}

// ---------------------------------------------------------------------------
// 命令
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn helmet_show(app: AppHandle) -> Result<(), String> {
    show(&app)
}

#[tauri::command]
pub async fn helmet_hide(app: AppHandle) -> Result<(), String> {
    hide(&app)
}

#[tauri::command]
pub async fn helmet_toggle(app: AppHandle) -> Result<bool, String> {
    toggle(&app)
}

#[tauri::command]
pub async fn helmet_set_ignore_cursor_events(app: AppHandle, ignore: bool) -> Result<(), String> {
    set_ignore_cursor_events(&app, ignore)
}

/// 系统光标相对本窗客户区的逻辑坐标（CSS px）；在窗外则返回 None。
/// 供前端在整窗穿透开启时轮询命中 `.hit`（穿透开时 WebView 收不到 pointer 事件）。
#[tauri::command]
pub async fn helmet_cursor_local(window: WebviewWindow) -> Result<Option<(f64, f64)>, String> {
    #[cfg(target_os = "windows")]
    {
        use windows_sys::Win32::Foundation::POINT;
        use windows_sys::Win32::UI::WindowsAndMessaging::GetCursorPos;

        let mut pt = POINT { x: 0, y: 0 };
        if unsafe { GetCursorPos(&mut pt) } == 0 {
            return Ok(None);
        }
        let pos = window
            .outer_position()
            .map_err(|e| format!("outer_position: {e}"))?;
        let size = window
            .outer_size()
            .map_err(|e| format!("outer_size: {e}"))?;
        let scale = window.scale_factor().unwrap_or(1.0);
        let px = pt.x;
        let py = pt.y;
        if px < pos.x
            || py < pos.y
            || px >= pos.x + size.width as i32
            || py >= pos.y + size.height as i32
        {
            return Ok(None);
        }
        let lx = (px - pos.x) as f64 / scale;
        let ly = (py - pos.y) as f64 / scale;
        Ok(Some((lx, ly)))
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = window;
        // POC：非 Windows 未接系统光标；前端可退回 mouseenter/leave
        Ok(None)
    }
}
