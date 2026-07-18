"""
一键自检模块 - 诊断素材完整性、配置文件有效性、网络连通性
结果通过托盘通知展示，详细日志写入日志文件
"""
import logging
import socket
import threading
from pathlib import Path
from typing import Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)

# 需要检查的动画目录（至少 cheer 必须存在）
REQUIRED_ANIMATIONS = ["cheer"]

# 天气 API 域名白名单 + 探测端口
WEATHER_HOSTS = {
    "openmeteo": ("geocoding-api.open-meteo.com", 443),
    "openmeteo_api": ("api.open-meteo.com", 443),
    "qweather_dev": ("devapi.qweather.com", 443),
    "qweather": ("geoapi.qweather.com", 443),
    "openweathermap": ("api.openweathermap.org", 443),
}

# NTP 服务器探测
NTP_SERVERS = [
    ("ntp.aliyun.com", 123),
    ("time.windows.com", 123),
    ("pool.ntp.org", 123),
]


def check_assets(base_dir: Path = None) -> Tuple[bool, List[str], List[str]]:
    """
    检查素材完整性。

    Returns:
        (all_ok, missing_list, details_list)
    """
    if base_dir is None:
        base_dir = Path(__file__).parent

    assets_dir = base_dir / "assets"
    missing = []
    details = []

    # 1. 检查 assets 根目录
    if not assets_dir.exists():
        return False, ["assets/ 目录不存在"], ["assets/ 目录缺失"]

    # 2. 检查 icon.png
    icon_path = assets_dir / "icon.png"
    if not icon_path.exists():
        missing.append("assets/icon.png")
        details.append("图标文件缺失: icon.png")

    # 3. 检查动画目录
    anim_dir = assets_dir / "animations"
    if not anim_dir.exists():
        missing.append("assets/animations/")
        details.append("动画目录缺失: animations/")
    else:
        for anim_name in REQUIRED_ANIMATIONS:
            anim_path = anim_dir / anim_name
            if not anim_path.exists():
                missing.append(f"assets/animations/{anim_name}/")
                details.append(f"必需动画缺失: {anim_name}/")
            elif not any(anim_path.iterdir()):
                missing.append(f"assets/animations/{anim_name}/ (空目录)")
                details.append(f"动画目录为空: {anim_name}/")

        # 列出所有可用动画
        available_anims = [d.name for d in anim_dir.iterdir() if d.is_dir()]
        if available_anims:
            details.append(f"可用动画: {', '.join(available_anims)}")

    # 4. 检查音效目录
    sound_dir = assets_dir / "sounds"
    if not sound_dir.exists():
        details.append("提示: 音效目录缺失 (可选)")
    else:
        sound_files = [f.name for f in sound_dir.iterdir() if f.suffix in {".wav", ".mp3"}]
        if sound_files:
            details.append(f"可用音效: {len(sound_files)} 个")
        else:
            details.append("提示: 音效目录为空 (可选)")

    all_ok = len(missing) == 0
    return all_ok, missing, details


def check_config(config_mgr) -> Tuple[bool, List[str], List[str]]:
    """
    检查配置文件有效性。

    Args:
        config_mgr: ConfigManager 实例

    Returns:
        (all_ok, warnings, details)
    """
    warnings = []
    details = []

    try:
        config = config_mgr.load()
        details.append("配置文件读取成功")
    except Exception as e:
        return False, [f"配置文件读取失败: {e}"], ["无法读取 config.yaml"]

    # 检查必要字段
    pet_cfg = config.get("pet", {})
    if not pet_cfg:
        warnings.append("配置缺少 [pet] 节，使用默认值")
    else:
        details.append(f"宠物名称: {pet_cfg.get('name', '未命名')}")

    # 检查 reminders
    reminders = config.get("reminders", [])
    if not reminders:
        warnings.append("未配置任何提醒项")
    else:
        enabled_count = sum(1 for r in reminders if r.get("enabled", False))
        details.append(f"提醒项: {len(reminders)} 个 (已启用: {enabled_count})")

    # 检查 UI 配置
    ui_cfg = config.get("ui", {})
    if ui_cfg:
        details.append(f"窗口尺寸: {ui_cfg.get('window_size', 256)}px")

    # 检查时间同步配置
    time_cfg = config.get("time_sync", {})
    if time_cfg.get("enabled", True):
        ntp_server = time_cfg.get("ntp_server", "ntp.aliyun.com")
        details.append(f"NTP 服务器: {ntp_server}")

    # 检查天气配置
    weather_cfg = config.get("weather", {})
    if weather_cfg.get("enabled", False):
        provider = weather_cfg.get("api_provider", "openmeteo")
        city = weather_cfg.get("city", "北京")
        details.append(f"天气: {provider} / 城市: {city}")
        api_key = weather_cfg.get("api_key", "")
        if provider in {"qweather", "openweathermap"} and not api_key:
            warnings.append(f"天气提供商 [{provider}] 需要 API Key，当前为空")

    all_ok = len(warnings) == 0
    return all_ok, warnings, details


def probe_tcp(host: str, port: int, timeout: float = 3.0) -> bool:
    """尝试 TCP 连接探测（非 NTP 协议，仅测试可达性）"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except socket.error:
        return False


def check_ntp_servers(servers: List[Tuple[str, int]] = None) -> Tuple[str, bool]:
    """
    检查 NTP 服务器可达性。

    Returns:
        (server_name, reachable)
    """
    if servers is None:
        servers = NTP_SERVERS

    for host, port in servers:
        if probe_tcp(host, port):
            logger.info(f"NTP 探测成功: {host}:{port}")
            return f"{host}:{port}", True

    logger.warning(f"所有 NTP 服务器不可达: {[s[0] for s in servers]}")
    return servers[0][0], False


def check_weather_api(provider: str = "openmeteo") -> Tuple[str, bool]:
    """
    检查天气 API 可达性。

    Returns:
        (host, reachable)
    """
    host_port = WEATHER_HOSTS.get(provider) or WEATHER_HOSTS.get("openmeteo")
    host, port = host_port
    reachable = probe_tcp(host, port)
    if reachable:
        logger.info(f"天气 API 探测成功: {host}:{port}")
    else:
        logger.warning(f"天气 API 不可达: {host}:{port}")
    return f"{host}:{port}", reachable


def run_diagnostics(config_mgr=None, callback: Callable[[str, bool, list], None] = None) -> None:
    """
    运行完整自检，在后台线程执行网络探测，避免阻塞主线程。

    Args:
        config_mgr: ConfigManager 实例（可选）
        callback: 完成回调 (title, success, lines) -> None，在主线程调用
    """
    results = []
    all_ok = True

    # 1. 素材检查（快速，不依赖网络）
    ok, missing, details = check_assets()
    results.extend(details)
    if not ok:
        all_ok = False
        results.insert(0, f"[!] 素材问题: {', '.join(missing[:3])}")
    else:
        results.insert(0, "[OK] 素材完整性检查通过")

    # 2. 配置检查
    if config_mgr is not None:
        ok, warnings, details = check_config(config_mgr)
        results.extend(details)
        if warnings:
            for w in warnings:
                results.append(f"[!] {w}")
            all_ok = False
        else:
            results.append("[OK] 配置文件有效")
    else:
        results.append("[跳过] 配置管理器未提供")

    # 3. NTP 服务器探测（网络）
    ntp_host, ntp_ok = check_ntp_servers()
    if ntp_ok:
        results.append(f"[OK] NTP 服务器可达: {ntp_host}")
    else:
        results.append(f"[!] NTP 服务器不可达: {ntp_host}")
        all_ok = False

    # 4. 天气 API 探测（网络）
    if config_mgr is not None:
        cfg = config_mgr.load()
        weather_cfg = cfg.get("weather", {})
        if weather_cfg.get("enabled", False):
            provider = weather_cfg.get("api_provider", "openmeteo")
            weather_host, weather_ok = check_weather_api(provider)
            if weather_ok:
                results.append(f"[OK] 天气 API 可达: {weather_host}")
            else:
                results.append(f"[!] 天气 API 不可达: {weather_host}")
                all_ok = False
        else:
            results.append("[跳过] 天气功能未启用")
    else:
        results.append("[跳过] 天气检查需要配置管理器")

    # 汇总
    title = "自检完成 - 全部正常" if all_ok else "自检完成 - 发现问题"
    summary = f"{'全部通过' if all_ok else '存在问题'} - {'; '.join(results[:4])}"

    logger.info(f"自检完成: {'OK' if all_ok else 'WARN'}, 详情: {results}")

    # 回调（在主线程执行）
    if callback:
        callback(title, all_ok, results)


def run_diagnostics_async(config_mgr=None, callback: Callable[[str, bool, list], None] = None) -> None:
    """异步运行自检（推荐方式，不阻塞主线程）"""
    thread = threading.Thread(
        target=run_diagnostics,
        args=(config_mgr, callback),
        daemon=True,
        name="DiagnosticsThread"
    )
    thread.start()
    logger.info("自检已在后台启动")
