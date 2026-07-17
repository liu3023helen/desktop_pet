"""
Nuitka 打包脚本 - Pygame 版本
生成单文件exe，无控制台窗口
"""
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent
OUTPUT = BASE / "dist"
OUTPUT.mkdir(exist_ok=True)

cmd = [
    sys.executable, "-m", "nuitka",
    "--onefile",                    # 单文件
    "--windows-disable-console",    # 无控制台窗口
    "--windows-icon-from-ico=" + str(BASE / "assets" / "icon.ico"),
    "--product-name=DesktopPet",
    "--file-description=Desktop Pet",
    "--company-name=DesktopPet",
    "--output-dir=" + str(OUTPUT),
    "--include-package=pygame",
    "--include-package=yaml",
    "--include-package=schedule",
    "--include-data-dir=" + str(BASE / "assets") + "=assets",
    "--enable-plugin=pyside6",      # Nuitka对pygame的支持
    str(BASE / "main.py"),
]

print("Building Desktop Pet...")
print("Command:", " ".join(cmd))

result = subprocess.run(cmd, capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print(result.stderr)

if result.returncode == 0:
    print(f"\nBuild success! Output in: {OUTPUT}")
else:
    print(f"\nBuild failed with code {result.returncode}")
