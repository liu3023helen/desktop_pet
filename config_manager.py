"""
配置管理器 - 负责读取和解析 YAML 配置文件
支持热重载：配置文件修改后自动重新加载
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """递归深合并两个字典，override 优先，缺失字段用 base 填充"""
    result = base.copy()
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


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
        """递归合并默认值，确保嵌套字段也被填充"""
        defaults = self._default_config()
        return _deep_merge(defaults, config)

    def _default_config(self) -> Dict[str, Any]:
        return {
            "pet": {
                "name": "小新",
                "style": "shinchan",
                "default_animation": "cheer"
            },
            "reminders": []
        }

    def get_enabled_reminders(self) -> list:
        """获取所有启用的提醒"""
        config = self.load()
        reminders = config.get("reminders", [])
        return [r for r in reminders if r.get("enabled", False)]
