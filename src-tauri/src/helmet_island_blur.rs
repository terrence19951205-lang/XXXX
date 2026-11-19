//! 仅灵动岛本体的原生磨砂层（Windows）。
//!
//! 整窗 Acrylic 会把中央可点桌面一起糊掉，CSS backdrop-filter 在透明 WebView2
//! 里也糊不到原生桌面。这里用一扇独立的、始终点击穿透、不抢焦点的小 HWND，
//! 只铺在岛脸（`.island-face`）下面：Win11 走系统 Acrylic 背景，Win10 走
//! SetWindowCompositionAttribute。主 Helmet 窗仍是全屏透明 + 动态点击穿透，
//! 磨砂窗永远叠在它正下方，不扩大命中面。

#![allow(non_snake_case)]

use std::sync::Mutex;

use serde::Deserialize;
use tauri::WebviewWindow;

#[derive(Clone, Copy, Debug, PartialEq, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IslandBlurRect {
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
    pub radius_top: f64,
    pub radius_bottom: f64,
}

#[derive(Clone, Copy, PartialEq)]
struct Phys {
    x: i32,
    y: i32,
    w: i32,
    h: i32,
    r_top: i32,
    r_bot: i32,
}

static BLUR_HWND: Mutex<Option<isize>> = Mutex::new(None);
static LAST: Mutex<Option<Phys>> = Mutex::new(None);

pub fn hide() {
    #[cfg(target_os = "windows")]
    hide_impl();
}

pub fn set(window: &WebviewWindow, rect: Option<IslandBlurRect>) {
    #[cfg(target_os = "windows")]
    set_impl(window, rect);
    #[cfg(not(target_os = "windows"))]
    {
        let _ = (window, rect);
    }
}

#[cfg(target_os = "windows")]
fn hide_impl() {
    use windows_sys::Win32::UI::WindowsAndMessaging::{ShowWindow, SW_HIDE};
    let hwnd = match BLUR_HWND.lock() {
        Ok(g) => *g,
        Err(e) => *e.into_inner(),
    };
    if let Some(raw) = hwnd {
        unsafe { ShowWindow(raw as _, SW_HIDE) };
    }
    if let Ok(mut g) = LAST.lock() {
        *g = None;
    }
}

#[cfg(target_os = "windows")]
fn set_impl(window: &WebviewWindow, rect: Option<IslandBlurRect>) {
    use windows_sys::Win32::Foundation::HWND;
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        SetWindowPos, HWND_TOPMOST, SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE, SWP_SHOWWINDOW,
    };

    let Some(rect) = rect else {
        hide_impl();
        return;
    };

    let Ok(pos) = window.outer_position() else {
        return;
    };
    let scale = window.scale_factor().unwrap_or(1.0);
    if scale <= 0.0 {
        return;
    }
    let phys = Phys {
        x: pos.x + (rect.x * scale).round() as i32,
        y: pos.y + (rect.y * scale).round() as i32,
        w: (rect.width * scale).round() as i32,
        h: (rect.height * scale).round() as i32,
        r_top: (rect.radius_top * scale).round().max(0.0) as i32,
        r_bot: (rect.radius_bottom * scale).round().max(0.0) as i32,
    };
    if phys.w < 4 || phys.h < 2 {
        hide_impl();
        return;
    }
    if let Ok(g) = LAST.lock() {
        if *g == Some(phys) {
            // 位置没变也要重新压一遍 Z 序：避免其它置顶窗把磨砂层抬到 Helmet 上面。
            if let (Ok(helmet), Ok(guard)) = (window.hwnd(), BLUR_HWND.lock()) {
                if let Some(raw) = *guard {
                    unsafe {
                        restack(raw as HWND, helmet.0);
                    }
                }
            }
            return;
        }
    }

    let blur = match ensure_blur_hwnd() {
        Some(h) => h,
        None => return,
    };
    apply_shape(blur, phys.w, phys.h, phys.r_top, phys.r_bot);
    unsafe {
        SetWindowPos(
            blur,
            HWND_TOPMOST,
            phys.x,
            phys.y,
            phys.w,
            phys.h,
            SWP_NOACTIVATE | SWP_SHOWWINDOW,
        );
        if let Ok(helmet) = window.hwnd() {
            restack(blur, helmet.0);
        }
    }
    if let Ok(mut g) = LAST.lock() {
        *g = Some(phys);
    }
}

#[cfg(target_os = "windows")]
unsafe fn restack(
    blur: windows_sys::Win32::Foundation::HWND,
    helmet: windows_sys::Win32::Foundation::HWND,
) {
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        SetWindowPos, HWND_TOPMOST, SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE,
    };
    // 先把磨砂层置顶，再把 Helmet 置到它上面：磨砂永远在岛后、桌面之上，
    // 且不会盖住 WebView 的点击面。
    SetWindowPos(
        blur,
        HWND_TOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
    );
    SetWindowPos(
        helmet,
        HWND_TOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
    );
}

#[cfg(target_os = "windows")]
fn ensure_blur_hwnd() -> Option<windows_sys::Win32::Foundation::HWND> {
    use windows_sys::Win32::Foundation::{GetLastError, ERROR_CLASS_ALREADY_EXISTS, HWND};
    use windows_sys::Win32::Graphics::Gdi::GetStockObject;
    use windows_sys::Win32::System::LibraryLoader::GetModuleHandleW;
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        CreateWindowExW, RegisterClassW, CS_HREDRAW, CS_VREDRAW, CW_USEDEFAULT, WNDCLASSW,
        WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_EX_TRANSPARENT, WS_POPUP,
    };

    if let Ok(g) = BLUR_HWND.lock() {
        if let Some(raw) = *g {
            return Some(raw as HWND);
        }
    }

    const CLASS: &[u16] = &[
        b's' as u16, b'h' as u16, b'e' as u16, b'l' as u16, b'l' as u16, b'-' as u16,
        b'h' as u16, b'u' as u16, b'b' as u16, b'-' as u16, b'i' as u16, b's' as u16,
        b'l' as u16, b'a' as u16, b'n' as u16, b'd' as u16, b'-' as u16, b'b' as u16,
        b'l' as u16, b'u' as u16, b'r' as u16, 0,
    ];

    unsafe {
        let hinst = GetModuleHandleW(std::ptr::null());
        let class = WNDCLASSW {
            style: CS_HREDRAW | CS_VREDRAW,
            lpfnWndProc: Some(blur_wnd_proc),
            cbClsExtra: 0,
            cbWndExtra: 0,
            hInstance: hinst,
            hIcon: std::ptr::null_mut(),
            hCursor: std::ptr::null_mut(),
            hbrBackground: GetStockObject(windows_sys::Win32::Graphics::Gdi::BLACK_BRUSH) as _,
            lpszMenuName: std::ptr::null(),
            lpszClassName: CLASS.as_ptr(),
        };
        let atom = RegisterClassW(&class);
        if atom == 0 {
            let err = GetLastError();
            if err != ERROR_CLASS_ALREADY_EXISTS {
                log::warn!("[helmet] 注册岛磨砂窗类失败: {err}");
                return None;
            }
        }

        let hwnd = CreateWindowExW(
            WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT | WS_EX_TOPMOST,
            CLASS.as_ptr(),
            CLASS.as_ptr(),
            WS_POPUP,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            8,
            8,
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            hinst,
            std::ptr::null_mut(),
        );
        if hwnd.is_null() {
            log::warn!("[helmet] 创建岛磨砂窗失败: {}", GetLastError());
            return None;
        }
        apply_native_frost(hwnd);
        if let Ok(mut g) = BLUR_HWND.lock() {
            *g = Some(hwnd as isize);
        }
        Some(hwnd)
    }
}

#[cfg(target_os = "windows")]
fn apply_shape(hwnd: windows_sys::Win32::Foundation::HWND, w: i32, h: i32, r_top: i32, r_bot: i32) {
    use windows_sys::Win32::Graphics::Gdi::{
        CombineRgn, CreateRectRgn, CreateRoundRectRgn, DeleteObject, RGN_OR, SetWindowRgn,
    };

    let w = w.max(1);
    let h = h.max(1);
    let rt = r_top.clamp(0, w.min(h));
    let rb = r_bot.clamp(0, w.min(h));
    unsafe {
        let rgn = if rt == 0 && rb == 0 {
            CreateRectRgn(0, 0, w, h)
        } else if rt == rb {
            CreateRoundRectRgn(0, 0, w + 1, h + 1, rt * 2, rt * 2)
        } else if rb == 0 {
            // 上圆下直：对话展开时岛脸是舱顶一条，不能用整颗药丸把舱顶切掉。
            let rounded = CreateRoundRectRgn(0, 0, w + 1, h + 1, rt * 2, rt * 2);
            let square = CreateRectRgn(0, rt, w + 1, h + 1);
            CombineRgn(rounded, rounded, square, RGN_OR);
            DeleteObject(square as _);
            rounded
        } else {
            let rounded = CreateRoundRectRgn(0, 0, w + 1, h + 1, rt * 2, rt * 2);
            let bot = CreateRoundRectRgn(0, 0, w + 1, h + 1, rb * 2, rb * 2);
            CombineRgn(rounded, rounded, bot, RGN_OR);
            DeleteObject(bot as _);
            rounded
        };
        SetWindowRgn(hwnd, rgn, 1);
        // SetWindowRgn 接管 rgn，不再 DeleteObject(rgn)
    }
}

#[cfg(target_os = "windows")]
fn apply_native_frost(hwnd: windows_sys::Win32::Foundation::HWND) {
    use windows_sys::Win32::Graphics::Dwm::DwmExtendFrameIntoClientArea;
    use windows_sys::Win32::Graphics::Dwm::DwmSetWindowAttribute;

    #[repr(C)]
    struct Margins {
        cx_left_width: i32,
        cx_right_width: i32,
        cy_top_height: i32,
        cy_bottom_height: i32,
    }
    // 整块客户区并入 DWM 边框，系统背景才能铺满小窗。
    let margins = Margins {
        cx_left_width: -1,
        cx_right_width: -1,
        cy_top_height: -1,
        cy_bottom_height: -1,
    };
    unsafe {
        let _ = DwmExtendFrameIntoClientArea(hwnd, &margins as *const Margins as _);
        let dark: i32 = 1;
        // DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        let _ = DwmSetWindowAttribute(hwnd, 20, &dark as *const i32 as _, 4);
        // 自定义圆角由 SetWindowRgn 负责，禁止系统再套一层标准圆角。
        // DWMWA_WINDOW_CORNER_PREFERENCE = 33, DWMWCP_DONOTROUND = 1
        let no_round: i32 = 1;
        let _ = DwmSetWindowAttribute(hwnd, 33, &no_round as *const i32 as _, 4);
    }

    if windows_build() >= 22000 {
        // DWMWA_SYSTEMBACKDROP_TYPE = 38, DWMSBT_TRANSIENTWINDOW = 3（Acrylic）
        let acrylic: i32 = 3;
        unsafe {
            let _ = DwmSetWindowAttribute(hwnd, 38, &acrylic as *const i32 as _, 4);
        }
        return;
    }
    apply_accent_acrylic(hwnd);
}

/// Win10 / 未提供系统背景的机器：用未文档化的 AccentPolicy 开亚克力模糊。
/// 颜色走深色座舱，不搬浅色皮肤。
#[cfg(target_os = "windows")]
fn apply_accent_acrylic(hwnd: windows_sys::Win32::Foundation::HWND) {
    use std::ffi::c_void;
    use windows_sys::Win32::Foundation::BOOL;
    use windows_sys::Win32::System::LibraryLoader::{GetModuleHandleW, GetProcAddress};

    #[repr(C)]
    struct AccentPolicy {
        accent_state: u32,
        accent_flags: u32,
        gradient_color: u32,
        animation_id: u32,
    }
    #[repr(C)]
    struct AttrData {
        attrib: u32,
        data: *mut c_void,
        size: usize,
    }
    type FnSet = unsafe extern "system" fn(
        windows_sys::Win32::Foundation::HWND,
        *mut AttrData,
    ) -> BOOL;

    // user32.dll
    const USER32: [u16; 11] = [
        b'u' as u16, b's' as u16, b'e' as u16, b'r' as u16, b'3' as u16, b'2' as u16,
        b'.' as u16, b'd' as u16, b'l' as u16, b'l' as u16, 0,
    ];
    unsafe {
        let module = GetModuleHandleW(USER32.as_ptr());
        if module.is_null() {
            return;
        }
        let Some(proc) = GetProcAddress(module, windows_sys::core::PCSTR(b"SetWindowCompositionAttribute\0".as_ptr())) else {
            return;
        };
        let set: FnSet = std::mem::transmute(proc);
        // ACCENT_ENABLE_ACRYLICBLURBEHIND = 4；gradient 为 ABGR，深色半透明。
        let mut policy = AccentPolicy {
            accent_state: 4,
            accent_flags: 2,
            gradient_color: 0xC018100C,
            animation_id: 0,
        };
        let mut data = AttrData {
            attrib: 19, // WCA_ACCENT_POLICY
            data: &mut policy as *mut _ as *mut c_void,
            size: std::mem::size_of::<AccentPolicy>(),
        };
        let _ = set(hwnd, &mut data);
    }
}

#[cfg(target_os = "windows")]
fn windows_build() -> u32 {
    use windows_sys::Win32::System::LibraryLoader::{GetModuleHandleW, GetProcAddress};

    #[repr(C)]
    struct OsVersionInfoW {
        size: u32,
        major: u32,
        minor: u32,
        build: u32,
        platform: u32,
        csd: [u16; 128],
    }
    type RtlGetVersion = unsafe extern "system" fn(*mut OsVersionInfoW) -> i32;
    const NTDLL: [u16; 10] = [
        b'n' as u16, b't' as u16, b'd' as u16, b'l' as u16, b'l' as u16, b'.' as u16,
        b'd' as u16, b'l' as u16, b'l' as u16, 0,
    ];
    unsafe {
        let module = GetModuleHandleW(NTDLL.as_ptr());
        if module.is_null() {
            return 0;
        }
        let proc = GetProcAddress(module, windows_sys::core::PCSTR(b"RtlGetVersion\0".as_ptr()));
        let Some(proc) = proc else {
            return 0;
        };
        let rtl: RtlGetVersion = std::mem::transmute(proc);
        let mut info = OsVersionInfoW {
            size: std::mem::size_of::<OsVersionInfoW>() as u32,
            major: 0,
            minor: 0,
            build: 0,
            platform: 0,
            csd: [0; 128],
        };
        if rtl(&mut info) != 0 {
            return 0;
        }
        info.build
    }
}

#[cfg(target_os = "windows")]
unsafe extern "system" fn blur_wnd_proc(
    hwnd: windows_sys::Win32::Foundation::HWND,
    msg: u32,
    wparam: windows_sys::Win32::Foundation::WPARAM,
    lparam: windows_sys::Win32::Foundation::LPARAM,
) -> windows_sys::Win32::Foundation::LRESULT {
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        DefWindowProcW, HTTRANSPARENT, WM_NCHITTEST,
    };
    if msg == WM_NCHITTEST {
        return HTTRANSPARENT as _;
    }
    DefWindowProcW(hwnd, msg, wparam, lparam)
}
