"""
依赖安装脚本 - 简化为直接调用 pip install -r requirements.txt
"""
import os
import subprocess
import sys


def main():
    print("=" * 50)
    print("Desktop Pet - 依赖安装")
    print("=" * 50)

    # 升级 pip
    print("\n[1/2] 升级 pip...")
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
                   capture_output=False)

    # 安装 requirements.txt
    print("\n[2/2] 安装项目依赖...")
    req_path = os.path.join(os.path.dirname(__file__) or ".", "requirements.txt")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", req_path],
        capture_output=False
    )

    print("\n" + "=" * 50)
    if result.returncode == 0:
        print("依赖安装成功！")
        print("Verification:")
        for mod in ["PyQt5", "yaml", "PIL"]:
            try:
                __import__(mod)
                print(f"  OK: {mod}")
            except ImportError:
                print(f"  MISSING: {mod}")
    else:
        print("依赖安装失败，请检查网络连接或手动执行：")
        print(f"  {sys.executable} -m pip install -r {req_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
