"""Build DesktopPet as a single Windows executable with PyInstaller."""

import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
STAGING_DIST_DIR = BUILD_DIR / "dist"
WORK_DIR = BUILD_DIR / "work"
SPEC_DIR = BUILD_DIR / "spec"
BACKUP_DIST_DIR = BUILD_DIR / "previous-dist"
MAIN = ROOT / "main.py"
ICON = ROOT / "resources" / "icon.ico"
BUILD_REQUIREMENTS = ROOT / "requirements-build.txt"
APP_NAME = "DesktopPet"

DATA_FILES = (
    (ROOT / "assets", "assets"),
    (ROOT / "config.yaml", "."),
)

# These modules are imported inside callbacks and are not always found by
# PyInstaller's static analysis.
DYNAMIC_IMPORTS = (
    "diagnostics",
    "pomodoro",
    "pomodoro_dialog",
    "reminder_dialog",
    "reminder_engine",
    "time_sync",
    "weather_service",
)


def validate_build_environment() -> List[str]:
    """Return build preflight errors without changing existing artifacts."""
    errors = []
    required_paths = (MAIN, ICON, *(source for source, _ in DATA_FILES))
    for path in required_paths:
        if not path.exists():
            errors.append(f"缺少构建输入: {path}")

    if importlib.util.find_spec("PyInstaller") is None:
        errors.append(
            f"当前 Python 未安装 PyInstaller: {sys.executable}\n"
            f"请运行: {sys.executable} -m pip install -r \"{BUILD_REQUIREMENTS}\""
        )
    return errors


def build_command(console: bool = False) -> List[str]:
    """Create the PyInstaller command for the selected build mode."""
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--console" if console else "--windowed",
        f"--icon={ICON}",
        f"--name={APP_NAME}",
        f"--distpath={STAGING_DIST_DIR}",
        f"--workpath={WORK_DIR}",
        f"--specpath={SPEC_DIR}",
        f"--paths={ROOT}",
        "--noconfirm",
        "--clean",
    ]

    # PyInstaller 6 uses SOURCE:DEST on every platform, including Windows.
    command.extend(
        f"--add-data={source}:{destination}"
        for source, destination in DATA_FILES
    )
    command.extend(
        f"--hidden-import={module}" for module in DYNAMIC_IMPORTS
    )
    command.append(str(MAIN))
    return command


def publish_staged_release() -> None:
    """Replace the complete release directory, restoring it on failure."""
    had_previous_release = DIST_DIR.exists()
    if BACKUP_DIST_DIR.exists():
        shutil.rmtree(BACKUP_DIST_DIR)
    if had_previous_release:
        DIST_DIR.replace(BACKUP_DIST_DIR)

    try:
        STAGING_DIST_DIR.replace(DIST_DIR)
    except OSError:
        if had_previous_release and BACKUP_DIST_DIR.exists():
            BACKUP_DIST_DIR.replace(DIST_DIR)
        raise

    if BACKUP_DIST_DIR.exists():
        shutil.rmtree(BACKUP_DIST_DIR)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build DesktopPet.exe")
    parser.add_argument(
        "--console",
        action="store_true",
        help="keep a console window for startup diagnostics",
    )
    args = parser.parse_args(argv)

    errors = validate_build_environment()
    if errors:
        print("[Build] 预检失败:")
        for error in errors:
            print(f"  - {error}")
        return 2

    if BUILD_DIR.exists():
        print(f"[Build] 清理临时目录: {BUILD_DIR}")
        shutil.rmtree(BUILD_DIR)
    SPEC_DIR.mkdir(parents=True, exist_ok=True)

    mode = "console" if args.console else "windowed"
    print(f"[Build] 开始打包 ({mode})...")
    result = subprocess.run(
        build_command(console=args.console),
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print(f"[Build] 打包失败，退出码: {result.returncode}")
        return result.returncode

    staged_exe = STAGING_DIST_DIR / f"{APP_NAME}.exe"
    if not staged_exe.is_file() or staged_exe.stat().st_size == 0:
        print(f"[Build] PyInstaller 未生成有效产物: {staged_exe}")
        return 3

    try:
        publish_staged_release()
    except OSError as error:
        print(f"[Build] 发布失败，已保留或恢复旧产物: {error}")
        return 4

    final_exe = DIST_DIR / staged_exe.name
    size_mb = final_exe.stat().st_size / (1024 * 1024)
    shutil.rmtree(BUILD_DIR)
    print(f"[Build] 打包成功: {final_exe.relative_to(ROOT)} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
