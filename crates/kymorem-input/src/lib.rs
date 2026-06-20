use kymorem_protocol::{
    ButtonEvent, ClipboardOffer, Frame, KeyEvent, PointerAbs, PointerMove, WheelEvent,
};

#[derive(Debug, thiserror::Error)]
pub enum InputError {
    #[error("input backend failed: {0}")]
    Backend(String),
}

pub trait InputSink: Send {
    fn pointer_move(&mut self, event: &PointerMove) -> Result<(), InputError>;
    fn pointer_abs(&mut self, event: &PointerAbs) -> Result<(), InputError>;
    fn button(&mut self, event: &ButtonEvent) -> Result<(), InputError>;
    fn wheel(&mut self, event: &WheelEvent) -> Result<(), InputError>;
    fn key(&mut self, event: &KeyEvent) -> Result<(), InputError>;
    fn clipboard_offer(&mut self, event: &ClipboardOffer) -> Result<(), InputError>;

    fn dispatch(&mut self, frame: &Frame) -> Result<bool, InputError> {
        match frame {
            Frame::PointerMove(event) => {
                self.pointer_move(event)?;
                Ok(true)
            }
            Frame::PointerAbs(event) => {
                self.pointer_abs(event)?;
                Ok(true)
            }
            Frame::Button(event) => {
                self.button(event)?;
                Ok(true)
            }
            Frame::Wheel(event) => {
                self.wheel(event)?;
                Ok(true)
            }
            Frame::Key(event) => {
                self.key(event)?;
                Ok(true)
            }
            Frame::ClipboardOffer(event) => {
                self.clipboard_offer(event)?;
                Ok(true)
            }
            _ => Ok(false),
        }
    }
}

#[derive(Debug, Default)]
pub struct LoggingInputSink;

impl InputSink for LoggingInputSink {
    fn pointer_move(&mut self, event: &PointerMove) -> Result<(), InputError> {
        println!("input:pointer_move dx={} dy={} seq={}", event.dx, event.dy, event.sequence);
        Ok(())
    }

    fn pointer_abs(&mut self, event: &PointerAbs) -> Result<(), InputError> {
        println!("input:pointer_abs x={} y={} seq={}", event.x, event.y, event.sequence);
        Ok(())
    }

    fn button(&mut self, event: &ButtonEvent) -> Result<(), InputError> {
        println!(
            "input:button button={:?} state={:?} seq={}",
            event.button, event.state, event.sequence
        );
        Ok(())
    }

    fn wheel(&mut self, event: &WheelEvent) -> Result<(), InputError> {
        println!("input:wheel dx={} dy={} seq={}", event.dx, event.dy, event.sequence);
        Ok(())
    }

    fn key(&mut self, event: &KeyEvent) -> Result<(), InputError> {
        println!(
            "input:key code={} state={:?} shift={} ctrl={} alt={} meta={} seq={}",
            event.code,
            event.state,
            event.modifiers.shift,
            event.modifiers.control,
            event.modifiers.alt,
            event.modifiers.meta,
            event.sequence
        );
        Ok(())
    }

    fn clipboard_offer(&mut self, event: &ClipboardOffer) -> Result<(), InputError> {
        println!(
            "input:clipboard_offer mime={} chars={} seq={}",
            event.mime,
            event.text.chars().count(),
            event.sequence
        );
        Ok(())
    }
}
