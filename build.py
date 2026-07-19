"""
PyInstaller 打包脚本 - 将 main.py 编译为独立 exe
输出文件：dist/DesktopPet.exe
"""
import subprocess
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
MAIN = ROOT / "main.py"
ICON = ROOT / "resources" / "icon.ico"
SPEC = ROOT / "DesktopPet.spec"

def main() -> int:
    # 清理旧构建
    for directory in (DIST_DIR, BUILD_DIR):
        if directory.exists():
            print(f"[Build] 清理: {directory}")
            shutil.rmtree(directory)

    if SPEC.exists():
        SPEC.unlink()

    # Windows 下 --add-data 格式: "源路径;目标路径"
    datas = [
        (str(ROOT / "assets"), "assets"),
        (str(ROOT / "config.yaml"), "."),
    ]
    add_data_args = [f"--add-data={src};{dst}" for src, dst in datas]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--console",                    # 开启控制台用于调试
        f"--icon={ICON}",
        "--name=DesktopPet",
    ] + add_data_args + [
        "--collect-all=PyQt5",
        "--hidden-import=yaml",
        "--hidden-import=config_manager",
        "--hidden-import=dingtalk_handler",
        "--hidden-import=utils",
        "--hidden-import=startup_utils",
        "--hidden-import=pet_window",
        "--hidden-import=diagnostics",
        "--hidden-import=reminder_engine",
        "--hidden-import=reminder_dialog",
        "--hidden-import=snooze_handler",
        "--hidden-import=workday_utils",
        "--hidden-import=time_sync",
        "--hidden-import=weather_service",
        "--clean",
        str(MAIN),
    ]

    print("[Build] 开始打包...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout[-2000:])

    if result.returncode != 0:
        print("[Build] 打包失败！")
        if result.stderr:
            print(result.stderr[-2000:])
        return 1

    print("[Build] 打包成功！")
    for exe in DIST_DIR.rglob("*.exe"):
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"  -> {exe.relative_to(ROOT)} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
