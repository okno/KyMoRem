import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def shortcut(path: Path, target: Path, working_dir: Path) -> None:
    ps = f"""
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{str(path)}')
$s.TargetPath = '{str(target)}'
$s.WorkingDirectory = '{str(working_dir)}'
$s.Description = 'KyMoRem Keyboard Mouse Remote'
$s.Save()
"""
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], check=False)


def main() -> int:
    client_host = os.environ.get("KYMOREM_CLIENT_HOST", "127.0.0.1")
    token = os.environ.get("KYMOREM_TOKEN", "kymorem-local-default-change-me")
    install_dir = Path(os.environ["LOCALAPPDATA"]) / "KyMoRem"
    install_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(resource_path("KyMoRem.exe"), install_dir / "KyMoRem.exe")

    config_dir = Path(os.environ["APPDATA"]) / "KyMoRem"
    config_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "language": "it",
        "theme": "cyber_noir",
        "server_name": "Windows Host",
        "token": token,
        "edge": "right",
        "security": {
            "required": True,
            "preferred_suite": "ml-kem-768+psk-hkdf-sha256+aes-256-gcm",
            "fallback_suite": "psk-hkdf-sha256+aes-256-gcm",
        },
        "discovery": {
            "enabled": True,
            "auto_connect": True,
            "udp_port": 54866,
        },
        "email_relay": {
            "enabled": False,
            "smtp_host": "",
            "smtp_port": 587,
            "smtp_starttls": True,
            "smtp_username": "",
            "smtp_password_env": "KYMOREM_SMTP_PASSWORD",
            "from": "kymorem@example.invalid",
            "to": [],
            "events": ["client_connected", "client_disconnected", "security_error"],
        },
        "clients": [
            {
                "name": "right-side-linux",
                "host": client_host,
                "port": 54865,
                "position": "right",
            }
        ],
    }
    (config_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    start_menu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "KyMoRem"
    start_menu.mkdir(parents=True, exist_ok=True)
    desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    shortcut(start_menu / "KyMoRem.lnk", install_dir / "KyMoRem.exe", install_dir)
    shortcut(desktop / "KyMoRem.lnk", install_dir / "KyMoRem.exe", install_dir)

    subprocess.Popen([str(install_dir / "KyMoRem.exe")], cwd=str(install_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
