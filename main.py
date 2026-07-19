"""
Desktop Pet - 桌面电子宠物 v2
主入口：初始化应用、加载配置、启动提醒引擎和宠物窗口
"""
import sys
import threading
import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from config_manager import ConfigManager
from dingtalk_handler import open_dingtalk_checkin
from startup_utils import setup_logging, ensure_data_dir, cleanup_stale_autostart
from pet_window import PetWindow

logger = logging.getLogger("DesktopPet")


def ensure_config(config_mgr: ConfigManager) -> None:
    """确保配置文件存在，不存在则释放默认配置"""
    if not config_mgr.config_path.exists():
        config_mgr.config_path.parent.mkdir(parents=True, exist_ok=True)
        default_config = config_mgr.config_path.parent / "config.yaml"
        if default_config.exists():
            import shutil
            shutil.copy2(default_config, config_mgr.config_path)
            logger.info(f"已释放默认配置到: {config_mgr.config_path}")


def main():
    # 0. 确保数据目录存在（首次运行创建 data/ 并复制默认配置）
    ensure_data_dir()

    # 1. 初始化配置管理器
    config_mgr = ConfigManager()
    ensure_config(config_mgr)
    config = config_mgr.load()
    logging_cfg = config.get("logging", {})
    setup_logging(
        level=logging_cfg.get("level", "INFO"),
        log_file=logging_cfg.get("file", "logs/pet.log"),
    )
    logger.info("=" * 40)
    logger.info("Desktop Pet 启动")
    logger.info(f"配置加载完成: pet={config.get('pet', {}).get('name', 'unknown')}")

    # 1b. 清理失效的开机自启注册表条目（exe被移动后）
    cleanup_stale_autostart()

    # 高分屏属性必须在 QApplication 创建前设置
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 2. 创建宠物窗口
    pet_window = PetWindow(config=config)
    if config_mgr.last_load_error:
        if config_mgr.recovered_from_backup:
            message = "主配置损坏，已自动使用最近备份。"
        else:
            message = "配置无法读取且没有可用备份，当前使用默认设置。"
        pet_window.tray_icon.showMessage("配置恢复", message)

    # 2b. 检查素材完整性
    from startup_utils import check_assets
    check_assets(pet_window)

    # 3. 创建提醒引擎
    from reminder_engine import ReminderEngine

    engine = ReminderEngine(config=config)

    # 注册动作处理器
    engine.register_handler("open_url", open_dingtalk_checkin)

    # 连接信号到主线程的提醒处理
    engine.reminder_triggered.connect(pet_window.trigger_reminder)

    # --- 设置双向引用 ---
    pet_window._config_mgr = config_mgr
    pet_window._engine = engine

    engine.start()
    logger.info("提醒引擎已启动")

    # --- 自动执行网络时间校准（后台）---
    try:
        from time_sync import TimeSyncService
        time_sync_cfg = config.get("time_sync", {})
        if time_sync_cfg.get("enabled", True):
            def auto_sync():
                service = TimeSyncService(server=time_sync_cfg.get("ntp_server", "ntp.aliyun.com"))
                offset = service.sync_once()
                if offset is not None:
                    engine.set_time_offset(offset)
                    tolerance = time_sync_cfg.get("tolerance_seconds", 30)
                    if abs(offset) > tolerance:
                        logger.warning(f"本地时间偏差过大: {offset:.1f}秒")
            threading.Thread(target=auto_sync, daemon=True).start()
    except ImportError:
        logger.debug("时间同步模块未就绪，跳过自动校准")

    # 4. 显示宠物窗口
    pet_window.show()
    logger.info("宠物窗口已显示")

    exit_code = app.exec_()

    # 清理
    engine.stop()
    logger.info("程序退出")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
