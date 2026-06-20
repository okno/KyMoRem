use serde::{Deserialize, Serialize};

pub const PROTOCOL_VERSION: u16 = 1;
pub const DEFAULT_PORT: u16 = 54865;
pub const SERVICE_NAME: &str = "_kymorem._tcp.local";
pub const MAX_FRAME_BYTES: usize = 64 * 1024;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Role {
    Host,
    Device,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Platform {
    Windows,
    Macos,
    Linux,
    Android,
    Unknown,
}

impl Platform {
    pub fn current() -> Self {
        if cfg!(target_os = "windows") {
            Self::Windows
        } else if cfg!(target_os = "macos") {
            Self::Macos
        } else if cfg!(target_os = "linux") {
            Self::Linux
        } else if cfg!(target_os = "android") {
            Self::Android
        } else {
            Self::Unknown
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CapabilitySet {
    pub pointer_relative: bool,
    pub pointer_absolute: bool,
    pub keyboard: bool,
    pub clipboard_text: bool,
    pub heartbeat: bool,
}

impl CapabilitySet {
    pub fn desktop_mvp() -> Self {
        Self {
            pointer_relative: true,
            pointer_absolute: false,
            keyboard: true,
            clipboard_text: false,
            heartbeat: true,
        }
    }

    pub fn android_mvp() -> Self {
        Self {
            pointer_relative: true,
            pointer_absolute: true,
            keyboard: true,
            clipboard_text: false,
            heartbeat: true,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScreenInfo {
    pub width: u32,
    pub height: u32,
    pub scale_milli: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Hello {
    pub protocol_version: u16,
    pub device_id: String,
    pub device_name: String,
    pub role: Role,
    pub platform: Platform,
    pub capabilities: CapabilitySet,
    pub screen: Option<ScreenInfo>,
}

impl Hello {
    pub fn new(device_id: impl Into<String>, device_name: impl Into<String>, role: Role) -> Self {
        Self {
            protocol_version: PROTOCOL_VERSION,
            device_id: device_id.into(),
            device_name: device_name.into(),
            role,
            platform: Platform::current(),
            capabilities: CapabilitySet::desktop_mvp(),
            screen: None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PairRequest {
    pub token: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PairAccepted {
    pub session_id: String,
    pub host_name: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PairRejected {
    pub reason: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PointerMove {
    pub dx: i32,
    pub dy: i32,
    pub sequence: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PointerAbs {
    pub x: i32,
    pub y: i32,
    pub sequence: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Button {
    Left,
    Right,
    Middle,
    Back,
    Forward,
    Other(u16),
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ButtonState {
    Down,
    Up,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ButtonEvent {
    pub button: Button,
    pub state: ButtonState,
    pub sequence: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WheelEvent {
    pub dx: i32,
    pub dy: i32,
    pub sequence: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum KeyState {
    Down,
    Up,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct Modifiers {
    pub shift: bool,
    pub control: bool,
    pub alt: bool,
    pub meta: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct KeyEvent {
    pub code: String,
    pub state: KeyState,
    pub modifiers: Modifiers,
    pub sequence: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ClipboardOffer {
    pub mime: String,
    pub text: String,
    pub sequence: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Heartbeat {
    pub sequence: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ErrorFrame {
    pub code: String,
    pub message: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", content = "payload", rename_all = "snake_case")]
pub enum Frame {
    Hello(Hello),
    PairRequest(PairRequest),
    PairAccepted(PairAccepted),
    PairRejected(PairRejected),
    PointerMove(PointerMove),
    PointerAbs(PointerAbs),
    Button(ButtonEvent),
    Wheel(WheelEvent),
    Key(KeyEvent),
    ClipboardOffer(ClipboardOffer),
    Heartbeat(Heartbeat),
    Error(ErrorFrame),
}

#[derive(Debug, thiserror::Error)]
pub enum CodecError {
    #[error("frame is too large: {0} bytes")]
    TooLarge(usize),
    #[error("invalid json frame: {0}")]
    Json(#[from] serde_json::Error),
}

pub fn encode_frame(frame: &Frame) -> Result<Vec<u8>, CodecError> {
    let mut bytes = serde_json::to_vec(frame)?;
    if bytes.len() > MAX_FRAME_BYTES {
        return Err(CodecError::TooLarge(bytes.len()));
    }
    bytes.push(b'\n');
    Ok(bytes)
}

pub fn decode_frame(line: &[u8]) -> Result<Frame, CodecError> {
    if line.len() > MAX_FRAME_BYTES {
        return Err(CodecError::TooLarge(line.len()));
    }

    let trimmed = line
        .strip_suffix(b"\n")
        .unwrap_or(line)
        .strip_suffix(b"\r")
        .unwrap_or_else(|| line.strip_suffix(b"\n").unwrap_or(line));

    Ok(serde_json::from_slice(trimmed)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frame_round_trip() {
        let frame = Frame::PointerMove(PointerMove {
            dx: 12,
            dy: -3,
            sequence: 42,
        });

        let encoded = encode_frame(&frame).expect("encode");
        let decoded = decode_frame(&encoded).expect("decode");

        assert_eq!(frame, decoded);
    }

    #[test]
    fn hello_uses_current_protocol_version() {
        let hello = Hello::new("dev-1", "test-device", Role::Device);

        assert_eq!(hello.protocol_version, PROTOCOL_VERSION);
        assert_eq!(hello.role, Role::Device);
    }
}
