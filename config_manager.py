"""
配置管理器 - 负责读取和解析 YAML 配置文件
支持热重载：配置文件修改后自动重新加载
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigManager:
    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config_path = Path(config_path)
        else:
            # 默认路径：%APPDATA%\DesktopPet\config.yaml
            appdata = Path(os.environ.get("APPDATA", ""))
            self.config_path = appdata / "DesktopPet" / "config.yaml"

    def load(self) -> Dict[str, Any]:
        """加载配置文件并返回字典"""
        if not self.config_path.exists():
            return self._default_config()

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            return self._merge_defaults(config)
        except Exception as e:
            print(f"[Config] 加载配置失败: {e}，使用默认配置")
            return self._default_config()

    def _merge_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """合并默认值"""
        defaults = self._default_config()
        
        if "pet" not in config:
            config["pet"] = defaults["pet"]
        if "reminders" not in config:
            config["reminders"] = defaults["reminders"]
            
        return config

    def _default_config(self) -> Dict[str, Any]:
        return {
            "pet": {
                "name": "小新",
                "style": "shinchan",
                "default_animation": "idle"
            },
            "reminders": []
        }

    def get_enabled_reminders(self) -> list:
        """获取所有启用的提醒"""
        config = self.load()
        reminders = config.get("reminders", [])
        return [r for r in reminders if r.get("enabled", False)]
