import os
import shutil
import subprocess
from pathlib import Path


def main() -> int:
    ps = """
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'KyMoRem.exe|kymorem_server.py|kymorem_client.py' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
"""
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], check=False)

    shutil.rmtree(Path(os.environ["LOCALAPPDATA"]) / "KyMoRem", ignore_errors=True)
    shutil.rmtree(Path(os.environ["APPDATA"]) / "KyMoRem", ignore_errors=True)
    shutil.rmtree(
        Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "KyMoRem",
        ignore_errors=True,
    )
    desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop" / "KyMoRem.lnk"
    try:
        desktop.unlink()
    except FileNotFoundError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
