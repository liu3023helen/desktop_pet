"""
Nuitka 打包脚本 - 将 main.py 编译为独立 exe
输出目录：dist/DesktopPet/
"""
import subprocess
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
DIST_DIR = ROOT / "dist"
MAIN = ROOT / "main.py"
ICON = ROOT / "assets" / "icon.png"

# 清理旧构建
if DIST_DIR.exists():
    print(f"[Build] 清理旧构建: {DIST_DIR}")
    shutil.rmtree(DIST_DIR)

# 构建命令
cmd = [
    sys.executable, "-m", "nuitka",
    "--onefile",                    # 单文件 exe
    "--windows-disable-console",    # 无控制台窗口
    "--windows-icon-from-ico=" + str(ICON.with_suffix(".ico")) if ICON.with_suffix(".ico").exists() else "",
    "--product-name=DesktopPet",
    "--company-name=DesktopPet",
    "--file-description=Desktop Pet",
    f"--output-dir={DIST_DIR}",
    "--include-package=PyQt5",
    "--include-module=yaml",
    "--include-module=schedule",
    str(MAIN),
]

# 过滤空参数（图标不存在时）
cmd = [c for c in cmd if c]

print(f"[Build] 开始打包: {' '.join(cmd)}")
result = subprocess.run(cmd, capture_output=True, text=True)

if result.returncode == 0:
    print("[Build] 打包成功！")
    # 列出产物
    for exe in DIST_DIR.rglob("*.exe"):
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"  -> {exe.relative_to(ROOT)} ({size_mb:.1f} MB)")
else:
    print("[Build] 打包失败！")
    print(result.stderr)
    sys.exit(1)
