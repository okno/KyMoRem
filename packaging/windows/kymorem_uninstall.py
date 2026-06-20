import os
import shutil
import subprocess
from pathlib import Path


def safe_rmtree(path: Path, expected_name: str) -> None:
    resolved = path.resolve(strict=False)
    if resolved.name != expected_name:
        raise RuntimeError(f"refusing to remove unexpected path: {resolved}")
    shutil.rmtree(resolved, ignore_errors=True)


def main() -> int:
    ps = """
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'KyMoRem.exe|kymorem_server.py|kymorem_client.py' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
"""
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], check=False)

    safe_rmtree(Path(os.environ["LOCALAPPDATA"]) / "KyMoRem", "KyMoRem")
    safe_rmtree(Path(os.environ["APPDATA"]) / "KyMoRem", "KyMoRem")
    safe_rmtree(
        Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "KyMoRem",
        "KyMoRem",
    )
    desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop" / "KyMoRem.lnk"
    try:
        desktop.unlink()
    except FileNotFoundError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
