"""
PyInstaller 打包脚本 - 将 main.py 编译为独立 exe
输出目录：dist/DesktopPet/
"""
import subprocess
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
MAIN = ROOT / "main.py"
ICON = ROOT / "assets" / "icon.ico"
SPEC = ROOT / "DesktopPet.spec"

# 清理旧构建
for d in [DIST_DIR, BUILD_DIR]:
    if d.exists():
        print(f"[Build] 清理: {d}")
        shutil.rmtree(d)

if SPEC.exists():
    SPEC.unlink()

# 数据文件包含（素材、配置等）
datas = [
    str(ROOT / "assets"),           # 动画帧、图标
    str(ROOT / "config.yaml"),      # 默认配置
]

# 隐藏控制台 + 单文件 + 图标
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--noconsole",                  # 无控制台窗口
    "--windowed",                   # GUI模式
    f"--icon={ICON}",               # 图标
    "--name=DesktopPet",            # exe名称
    "--add-data=" + ";".join(datas),# 包含素材目录
    "--collect-all=PyQt5",         # 包含PyQt5全部资源
    "--hidden-import=yaml",
    "--hidden-import=PyYAML",
    "--clean",                      # 清理临时缓存
    str(MAIN),
]

print(f"[Build] 开始打包...")
result = subprocess.run(cmd, capture_output=True, text=True)

# 输出日志
if result.stdout:
    print(result.stdout[-2000:])  # 只打印最后2000字符

if result.returncode == 0:
    print("[Build] 打包成功！")
    # 列出产物
    for exe in DIST_DIR.rglob("*.exe"):
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"  -> {exe.relative_to(ROOT)} ({size_mb:.1f} MB)")
else:
    print("[Build] 打包失败！")
    if result.stderr:
        print(result.stderr[-2000:])
    sys.exit(1)
