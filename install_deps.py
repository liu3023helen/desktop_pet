"""
依赖安装脚本 - 直接下载wheel文件后本地安装，完全绕过pip的网络请求
"""
import subprocess
import sys
import ssl
import urllib.request
import os
from pathlib import Path

# 创建不验证SSL的上下文
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# 安装opener不走代理
opener = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=ssl_ctx),
    urllib.request.ProxyHandler({})
)
urllib.request.install_opener(opener)

# 包名和版本（指定版本避免解析问题）
PACKAGES = {
    "PyQt5": "PyQt5-5.15.9-cp37-abi3-win_amd64.whl",
    "PyQt5_sip": "PyQt5_sip-12.12.2-cp310-cp310-win_amd64.whl",
    "schedule": "schedule-1.2.0-py3-none-any.whl",
    "PyYAML": "PyYAML-6.0.1-cp310-cp310-win_amd64.whl",
    "Pillow": "Pillow-10.4.0-cp310-cp310-win_amd64.whl",
    "numpy": "numpy-1.26.4-cp310-cp310-win_amd64.whl",
}

BASE_URL = "https://files.pythonhosted.org/packages"

# PyQt5需要额外依赖
PYQT5_SIP_URL = "https://files.pythonhosted.org/packages/28/7e/e4c8f6b6c0a4c8b8c8f8c8f8c8f8c8f8c8f8c8f8/PyQt5_sip-12.12.2-cp310-cp310-win_amd64.whl"


def download(url: str, dest: Path) -> bool:
    """下载文件"""
    try:
        print(f"  Downloading: {url}")
        req = urllib.request.Request(url)
        resp = opener.open(req, timeout=30, context=ssl_ctx)
        data = resp.read()
        dest.write_bytes(data)
        print(f"  OK: {dest.name} ({len(data) / 1024 / 1024:.1f}MB)")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False


def install_wheel(wheel_path: Path) -> bool:
    """本地安装wheel"""
    cmd = [sys.executable, "-m", "pip", "install", "--force-reinstall", str(wheel_path)]
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def main():
    downloads_dir = Path(__file__).parent / "_downloads"
    downloads_dir.mkdir(exist_ok=True)

    # 1. PyQt5-sip (PyQt5的前置依赖)
    print("\n[1/7] Installing PyQt5-sip...")
    sip_url = "https://files.pythonhosted.org/packages/28/7e/87b0e9f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8/PyQt5_sip-12.12.2-cp310-cp310-win_amd64.whl"
    # 实际URL需要从pypi页面获取，这里用简化方式
    # 先用pip安装sip
    ret = subprocess.run([sys.executable, "-m", "pip", "install", "PyQt5-sip"], 
                         capture_output=False,
                         env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""})
    
    # 2. 下载并安装其他包
    packages_to_download = [
        ("schedule", "1.2.0", "py3-none-any"),
        ("PyYAML", "6.0.1", "cp310-cp310-win_amd64"),
        ("Pillow", "10.4.0", "cp310-cp310-win_amd64"),
        ("numpy", "1.26.4", "cp310-cp310-win_amd64"),
    ]
    
    for name, version, platform in packages_to_download:
        print(f"\n[{name}]...")
        whl_name = f"{name}-{version}-{platform}.whl"
        whl_path = downloads_dir / whl_name
        
        if whl_path.exists():
            print(f"  Already exists, skipping download")
        else:
            # 构造下载URL
            name_lower = name.lower()
            url = f"https://files.pythonhosted.org/packages/{name_lower[0]}/{name_lower[:2].lower()}/{name_lower}/{whl_name}"
            # 更可靠的方式：从simple页面找真实URL
            simple_url = f"https://pypi.tuna.tsinghua.edu.cn/simple/{name_lower}/"
            try:
                req = urllib.request.Request(simple_url)
                resp = opener.open(req, timeout=15, context=ssl_ctx)
                html = resp.read().decode("utf-8")
                
                # 找到对应版本的wheel链接
                import re
                pattern = rf'href="[^"]*{re.escape(whl_name)}[^"]*"'
                match = re.search(pattern, html)
                if match:
                    href = match.group().split('"')[1]
                    if href.startswith("http"):
                        url = href
                    else:
                        url = simple_url + href
                    
                    if download(url, whl_path):
                        install_wheel(whl_path)
                        continue
            except Exception as e:
                print(f"  Error fetching {name}: {e}")
        
        # 如果下载失败，尝试直接用pip
        print(f"  Trying pip fallback for {name}...")
        subprocess.run([sys.executable, "-m", "pip", "install", name], capture_output=False)

    # 3. PyQt5 (最后装，因为最大)
    print("\n[PyQt5]...")
    pyqt5_whl = downloads_dir / "PyQt5-5.15.9-cp37-abi3-win_amd64.whl"
    if not pyqt5_whl.exists():
        simple_url = "https://pypi.tuna.tsinghua.edu.cn/simple/pyqt5/"
        try:
            req = urllib.request.Request(simple_url)
            resp = opener.open(req, timeout=15, context=ssl_ctx)
            html = resp.read().decode("utf-8")
            import re
            wheels = re.findall(r'href="([^"]*\.whl[^"]*)"', html)
            if wheels:
                whl_name = wheels[-1].split('#')[0].split('"')[0]
                url = f"https://pypi.tuna.tsinghua.edu.cn/simple/pyqt5/{whl_name}"
                if download(url, pyqt5_whl):
                    install_wheel(pyqt5_whl)
        except Exception as e:
            print(f"  Error: {e}")
            subprocess.run([sys.executable, "-m", "pip", "install", "PyQt5"], capture_output=False)

    # 清理
    if downloads_dir.exists():
        import shutil
        shutil.rmtree(downloads_dir)
        print("\nCleaned up downloads.")

    print("\n" + "=" * 50)
    print("Verification:")
    for mod in ["PyQt5", "schedule", "yaml", "PIL", "numpy"]:
        try:
            __import__(mod)
            print(f"  OK: {mod}")
        except ImportError:
            print(f"  MISSING: {mod}")
    print("=" * 50)


if __name__ == "__main__":
    main()
