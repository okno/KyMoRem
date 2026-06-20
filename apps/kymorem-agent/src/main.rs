use std::net::SocketAddr;
use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::{anyhow, Context, Result};
use clap::{Parser, Subcommand};
use kymorem_input::{InputSink, LoggingInputSink};
use kymorem_protocol::{
    decode_frame, encode_frame, Button, ButtonEvent, ButtonState, CapabilitySet, Frame, Hello,
    KeyEvent, KeyState, Modifiers, PairAccepted, PairRejected, PairRequest, Platform, PointerMove,
    Role, WheelEvent, DEFAULT_PORT, PROTOCOL_VERSION,
};
use tokio::io::{AsyncBufReadExt, AsyncWrite, AsyncWriteExt, BufReader};
use tokio::net::{TcpListener, TcpStream};
use tracing::{error, info, warn};

#[derive(Debug, Parser)]
#[command(name = "kymorem-agent")]
#[command(about = "KyMoRem LAN keyboard/mouse sharing prototype")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    Host {
        #[arg(long, default_value = "0.0.0.0:54865")]
        bind: String,
        #[arg(long)]
        token: Option<String>,
    },
    Device {
        #[arg(long)]
        host: String,
        #[arg(long)]
        token: String,
        #[arg(long)]
        name: Option<String>,
        #[arg(long)]
        demo: bool,
    },
    SampleFrame,
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter("kymorem_agent=info,kymorem=info")
        .init();

    let cli = Cli::parse();

    match cli.command {
        Command::Host { bind, token } => run_host(&bind, token).await,
        Command::Device {
            host,
            token,
            name,
            demo,
        } => run_device(&host, &token, name, demo).await,
        Command::SampleFrame => {
            let frame = Frame::Hello(hello_for(Role::Device, Some("sample".to_owned())));
            print!("{}", String::from_utf8(encode_frame(&frame)?)?);
            Ok(())
        }
    }
}

async fn run_host(bind: &str, expected_token: Option<String>) -> Result<()> {
    let listener = TcpListener::bind(bind)
        .await
        .with_context(|| format!("failed to bind host listener on {bind}"))?;

    info!("KyMoRem host listening on {bind}");
    if expected_token.is_some() {
        info!("pairing token enabled");
    } else {
        warn!("no pairing token set; accept only on trusted LANs");
    }

    loop {
        let (stream, peer) = listener.accept().await?;
        let expected_token = expected_token.clone();
        tokio::spawn(async move {
            if let Err(err) = handle_device(stream, peer, expected_token).await {
                error!(%peer, error = %err, "device session ended with error");
            }
        });
    }
}

async fn handle_device(stream: TcpStream, peer: SocketAddr, expected_token: Option<String>) -> Result<()> {
    info!(%peer, "device connected");

    let (reader, mut writer) = stream.into_split();
    let mut lines = BufReader::new(reader).lines();
    let mut accepted = false;
    let mut input = LoggingInputSink;

    while let Some(line) = lines.next_line().await? {
        let frame = decode_frame(line.as_bytes()).context("decode frame")?;

        match &frame {
            Frame::Hello(hello) => {
                validate_hello(hello)?;
                info!(
                    %peer,
                    device = %hello.device_name,
                    id = %hello.device_id,
                    platform = ?hello.platform,
                    role = ?hello.role,
                    "hello"
                );
            }
            Frame::PairRequest(PairRequest { token }) => {
                if expected_token
                    .as_deref()
                    .is_some_and(|expected| expected != token.as_str())
                {
                    write_frame(
                        &mut writer,
                        &Frame::PairRejected(PairRejected {
                            reason: "pairing token mismatch".to_owned(),
                        }),
                    )
                    .await?;
                    return Err(anyhow!("pairing token mismatch from {peer}"));
                }

                accepted = true;
                let session_id = make_session_id(peer);
                write_frame(
                    &mut writer,
                    &Frame::PairAccepted(PairAccepted {
                        session_id,
                        host_name: local_name(),
                    }),
                )
                .await?;
                info!(%peer, "pairing accepted");
            }
            Frame::Heartbeat(event) => {
                info!(%peer, sequence = event.sequence, "heartbeat");
            }
            _ if accepted => {
                let handled = input.dispatch(&frame)?;
                if !handled {
                    info!(%peer, frame = ?frame, "non-input frame");
                }
            }
            _ => {
                write_frame(
                    &mut writer,
                    &Frame::PairRejected(PairRejected {
                        reason: "input before pairing".to_owned(),
                    }),
                )
                .await?;
                return Err(anyhow!("input received before pairing"));
            }
        }
    }

    info!(%peer, "device disconnected");
    Ok(())
}

async fn run_device(host: &str, token: &str, name: Option<String>, demo: bool) -> Result<()> {
    let stream = TcpStream::connect(host)
        .await
        .with_context(|| format!("failed to connect to host {host}"))?;

    let (reader, mut writer) = stream.into_split();
    let mut lines = BufReader::new(reader).lines();

    write_frame(&mut writer, &Frame::Hello(hello_for(Role::Device, name))).await?;
    write_frame(
        &mut writer,
        &Frame::PairRequest(PairRequest {
            token: token.to_owned(),
        }),
    )
    .await?;

    let response = lines
        .next_line()
        .await?
        .ok_or_else(|| anyhow!("host disconnected during pairing"))?;
    match decode_frame(response.as_bytes())? {
        Frame::PairAccepted(accepted) => {
            info!(session = %accepted.session_id, host = %accepted.host_name, "paired");
        }
        Frame::PairRejected(rejected) => {
            return Err(anyhow!("pairing rejected: {}", rejected.reason));
        }
        other => {
            return Err(anyhow!("unexpected pairing response: {other:?}"));
        }
    }

    if demo {
        send_demo_events(&mut writer).await?;
        return Ok(());
    }

    interactive_loop(&mut writer).await
}

async fn send_demo_events<W>(writer: &mut W) -> Result<()>
where
    W: AsyncWrite + Unpin,
{
    for sequence in 1..=8 {
        write_frame(
            writer,
            &Frame::PointerMove(PointerMove {
                dx: 24,
                dy: if sequence % 2 == 0 { 8 } else { -8 },
                sequence,
            }),
        )
        .await?;
    }

    write_frame(
        writer,
        &Frame::Button(ButtonEvent {
            button: Button::Left,
            state: ButtonState::Down,
            sequence: 9,
        }),
    )
    .await?;
    write_frame(
        writer,
        &Frame::Button(ButtonEvent {
            button: Button::Left,
            state: ButtonState::Up,
            sequence: 10,
        }),
    )
    .await?;
    write_frame(
        writer,
        &Frame::Wheel(WheelEvent {
            dx: 0,
            dy: -120,
            sequence: 11,
        }),
    )
    .await?;
    write_frame(
        writer,
        &Frame::Key(KeyEvent {
            code: "KeyK".to_owned(),
            state: KeyState::Down,
            modifiers: Modifiers {
                control: true,
                ..Modifiers::default()
            },
            sequence: 12,
        }),
    )
    .await?;
    write_frame(
        writer,
        &Frame::Key(KeyEvent {
            code: "KeyK".to_owned(),
            state: KeyState::Up,
            modifiers: Modifiers {
                control: true,
                ..Modifiers::default()
            },
            sequence: 13,
        }),
    )
    .await?;

    Ok(())
}

async fn interactive_loop<W>(writer: &mut W) -> Result<()>
where
    W: AsyncWrite + Unpin,
{
    println!("commands: move <dx> <dy> | wheel <dy> | click left | key <code> | quit");
    let mut lines = BufReader::new(tokio::io::stdin()).lines();
    let mut sequence = 1;

    while let Some(line) = lines.next_line().await? {
        let parts = line.split_whitespace().collect::<Vec<_>>();
        match parts.as_slice() {
            ["quit"] | ["exit"] => break,
            ["move", dx, dy] => {
                write_frame(
                    writer,
                    &Frame::PointerMove(PointerMove {
                        dx: dx.parse()?,
                        dy: dy.parse()?,
                        sequence,
                    }),
                )
                .await?;
            }
            ["wheel", dy] => {
                write_frame(
                    writer,
                    &Frame::Wheel(WheelEvent {
                        dx: 0,
                        dy: dy.parse()?,
                        sequence,
                    }),
                )
                .await?;
            }
            ["click", "left"] => {
                write_frame(
                    writer,
                    &Frame::Button(ButtonEvent {
                        button: Button::Left,
                        state: ButtonState::Down,
                        sequence,
                    }),
                )
                .await?;
                sequence += 1;
                write_frame(
                    writer,
                    &Frame::Button(ButtonEvent {
                        button: Button::Left,
                        state: ButtonState::Up,
                        sequence,
                    }),
                )
                .await?;
            }
            ["key", code] => {
                write_frame(
                    writer,
                    &Frame::Key(KeyEvent {
                        code: (*code).to_owned(),
                        state: KeyState::Down,
                        modifiers: Modifiers::default(),
                        sequence,
                    }),
                )
                .await?;
                sequence += 1;
                write_frame(
                    writer,
                    &Frame::Key(KeyEvent {
                        code: (*code).to_owned(),
                        state: KeyState::Up,
                        modifiers: Modifiers::default(),
                        sequence,
                    }),
                )
                .await?;
            }
            [] => continue,
            _ => println!("unknown command"),
        }
        sequence += 1;
    }

    Ok(())
}

async fn write_frame<W>(writer: &mut W, frame: &Frame) -> Result<()>
where
    W: AsyncWrite + Unpin,
{
    writer.write_all(&encode_frame(frame)?).await?;
    writer.flush().await?;
    Ok(())
}

fn validate_hello(hello: &Hello) -> Result<()> {
    if hello.protocol_version != PROTOCOL_VERSION {
        return Err(anyhow!(
            "protocol mismatch: got {}, expected {}",
            hello.protocol_version,
            PROTOCOL_VERSION
        ));
    }
    Ok(())
}

fn hello_for(role: Role, name: Option<String>) -> Hello {
    let mut hello = Hello::new(make_device_id(), name.unwrap_or_else(local_name), role);
    hello.platform = Platform::current();
    hello.capabilities = CapabilitySet::desktop_mvp();
    hello
}

fn make_device_id() -> String {
    format!("{}-{}", local_name(), now_millis())
}

fn make_session_id(peer: SocketAddr) -> String {
    format!("session-{}-{}", peer.port(), now_millis())
}

fn now_millis() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis())
        .unwrap_or_default()
}

fn local_name() -> String {
    std::env::var("COMPUTERNAME")
        .or_else(|_| std::env::var("HOSTNAME"))
        .unwrap_or_else(|_| "kymorem-device".to_owned())
}
