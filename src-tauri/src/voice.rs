//! P1-3 录音转文字：HUD 前端（笔记编辑器 / 对话舱输入框）录好的一段音频，
//! 经这里送到用户在「设置 → AI 助手 → 供应商」里配好的 OpenAI 兼容服务：
//! `POST {base_url}/audio/transcriptions`（multipart：file + model）。
//!
//! 底座没有本地语音识别能力，所以只走「设置里配置的模型 API」这一条路：
//! - 优先挑模型名像转写模型的条目（whisper / transcribe / asr / sensevoice / paraformer）；
//! - 否则用默认对话模型的同一供应商地址 + `whisper-1`；
//! - 平台模型（依赖账号登录）不参与——本轮账号入口已隐藏。
//! 服务不支持该接口时把状态码和原因原样说清楚，不吞错、不假装成功。

use base64::Engine;
use serde::Serialize;

use crate::models::ChatModelConfig;

#[derive(Debug, Serialize)]
pub struct TranscribeResult {
    pub text: String,
    /// 实际用的转写模型名与供应商（前端提示用）
    pub model: String,
    pub provider: String,
}

fn looks_like_stt(model: &str) -> bool {
    let m = model.to_ascii_lowercase();
    ["whisper", "transcri", "asr", "sensevoice", "paraformer", "speech"]
        .iter()
        .any(|k| m.contains(k))
}

/// 选一个转写端点：(base_url, api_key, 转写模型名, 供应商显示名)
fn pick_endpoint(models: &[ChatModelConfig]) -> Result<(String, String, String, String), String> {
    let keyed: Vec<(&ChatModelConfig, String)> = models
        .iter()
        .filter(|m| !crate::chat::is_platform_model(m) && !m.base_url.trim().is_empty())
        .filter_map(|m| crate::chat::get_api_key(&m.id).filter(|k| !k.trim().is_empty()).map(|k| (m, k)))
        .collect();
    if keyed.is_empty() {
        return Err("NO_API: 还没有可用的模型 API（设置 → AI 助手 → 供应商 里至少配一个带 Key 的模型）".into());
    }
    let label = |m: &ChatModelConfig| {
        if m.provider_name.trim().is_empty() { m.name.clone() } else { m.provider_name.clone() }
    };
    if let Some((m, k)) = keyed.iter().find(|(m, _)| looks_like_stt(&m.model)) {
        return Ok((m.base_url.trim().to_string(), k.clone(), m.model.clone(), label(m)));
    }
    let (m, k) = keyed.iter().find(|(m, _)| m.is_default).unwrap_or(&keyed[0]);
    Ok((m.base_url.trim().to_string(), k.clone(), "whisper-1".into(), label(m)))
}

fn ext_for(mime: &str) -> &'static str {
    let m = mime.to_ascii_lowercase();
    if m.contains("webm") {
        "webm"
    } else if m.contains("ogg") {
        "ogg"
    } else if m.contains("wav") {
        "wav"
    } else if m.contains("mp4") || m.contains("m4a") || m.contains("aac") {
        "m4a"
    } else if m.contains("mpeg") || m.contains("mp3") {
        "mp3"
    } else {
        "webm"
    }
}

#[tauri::command]
pub async fn transcribe_audio(audio_b64: String, mime: String) -> Result<TranscribeResult, String> {
    let bytes = base64::engine::general_purpose::STANDARD
        .decode(audio_b64.trim())
        .map_err(|e| format!("音频数据无效: {e}"))?;
    if bytes.len() < 512 {
        return Err("EMPTY: 录音太短或没有声音".into());
    }
    if bytes.len() > 24 * 1024 * 1024 {
        return Err("TOO_LONG: 录音超过 24MB，请分段录".into());
    }
    let cfg = crate::config::load();
    let (base, key, model, provider) = pick_endpoint(&cfg.chat_models)?;
    let url = format!("{}/audio/transcriptions", base.trim_end_matches('/'));
    let ext = ext_for(&mime);
    let part = reqwest::multipart::Part::bytes(bytes)
        .file_name(format!("voice.{ext}"))
        .mime_str(if mime.trim().is_empty() { "audio/webm" } else { mime.split(';').next().unwrap_or("audio/webm") })
        .map_err(|e| e.to_string())?;
    let form = reqwest::multipart::Form::new()
        .part("file", part)
        .text("model", model.clone())
        .text("response_format", "json");
    // 第三方服务：跟随系统代理（与对话请求同口径，见 net.rs 约定）
    let client = reqwest::Client::builder()
        .connect_timeout(std::time::Duration::from_secs(15))
        .timeout(std::time::Duration::from_secs(120))
        .build()
        .map_err(|e| e.to_string())?;
    log::info!("[voice] 转写请求 provider={provider} model={model}");
    let resp = client
        .post(&url)
        .bearer_auth(key.trim())
        .multipart(form)
        .send()
        .await
        .map_err(|e| format!("NET: 连接转写服务失败（{provider}）: {e}"))?;
    let status = resp.status();
    let body = resp.text().await.unwrap_or_default();
    if !status.is_success() {
        let snippet: String = body.chars().take(160).collect();
        if status.as_u16() == 404 || status.as_u16() == 405 {
            return Err(format!(
                "UNSUPPORTED: 「{provider}」不支持语音转写接口（HTTP {}）。请在 设置 → AI 助手 → 供应商 添加一个转写模型（如 whisper-1 / SenseVoice）",
                status.as_u16()
            ));
        }
        return Err(format!("HTTP {}: {snippet}", status.as_u16()));
    }
    let text = serde_json::from_str::<serde_json::Value>(&body)
        .ok()
        .and_then(|v| v.get("text").and_then(|t| t.as_str()).map(|s| s.to_string()))
        .unwrap_or_else(|| body.trim().to_string());
    Ok(TranscribeResult { text: text.trim().to_string(), model, provider })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn stt_name_detection() {
        assert!(looks_like_stt("whisper-1"));
        assert!(looks_like_stt("FunAudioLLM/SenseVoiceSmall"));
        assert!(!looks_like_stt("deepseek-chat"));
        assert_eq!(ext_for("audio/webm;codecs=opus"), "webm");
    }
}
