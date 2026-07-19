"""
配置管理器 - 负责读取和解析 YAML 配置文件
支持热重载：配置文件修改后自动重新加载
所有数据存储在 exe 同级 data/ 目录下，完全便携不写 C 盘
"""
import logging
import shutil
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

from utils import get_app_dir, get_resource_path

logger = logging.getLogger(__name__)


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
            # 默认路径：exe 同级 data/config.yaml（完全便携）
            self.config_path = get_app_dir() / "data" / "config.yaml"
        self.last_load_error: Optional[str] = None
        self.recovered_from_backup = False

    @property
    def backup_path(self) -> Path:
        return self.config_path.with_suffix(self.config_path.suffix + ".bak")

    @staticmethod
    def _read_yaml(path: Path) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        if not isinstance(config, dict):
            raise ValueError("配置根节点必须是对象")
        return config

    def load(self) -> Dict[str, Any]:
        """加载配置文件并返回字典"""
        self.last_load_error = None
        self.recovered_from_backup = False
        if not self.config_path.exists():
            return self._default_config()

        try:
            config = self._read_yaml(self.config_path)
            return self._merge_defaults(config)
        except Exception as e:
            self.last_load_error = str(e)
            logger.error(f"加载配置失败: {e}")

        if self.backup_path.exists():
            try:
                config = self._read_yaml(self.backup_path)
                self.recovered_from_backup = True
                logger.warning(f"已从备份恢复配置: {self.backup_path}")
                return self._merge_defaults(config)
            except Exception as backup_error:
                logger.error(f"加载配置备份失败: {backup_error}")

        logger.error("没有可用配置备份，使用默认配置")
        return self._default_config()

    def _merge_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """递归合并默认值，确保嵌套字段也被填充"""
        defaults = self._default_config()
        return _deep_merge(defaults, config)

    def _default_config(self) -> Dict[str, Any]:
        template_path = get_resource_path("config.yaml")
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template = yaml.safe_load(f) or {}
            if isinstance(template, dict):
                return template
            logger.error(f"默认配置模板必须是对象: {template_path}")
        except Exception as e:
            logger.error(f"加载默认配置模板失败: {e}")

        return {
            "pet": {
                "name": "小新",
                "style": "shinchan",
                "default_animation": "cheer"
            },
            "reminders": []
        }

    def save(self, config: Dict[str, Any]) -> bool:
        """保存配置到YAML文件（原子写入，防止并发损坏）"""
        if not isinstance(config, dict):
            logger.error("拒绝保存非对象配置")
            return False

        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.config_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            temp_path.replace(self.config_path)
            try:
                shutil.copy2(self.config_path, self.backup_path)
            except OSError as backup_error:
                logger.warning(f"配置已保存，但备份失败: {backup_error}")
            logger.info(f"配置已保存: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            try:
                temp_path.unlink(missing_ok=True)
            except:
                pass
            return False

    def reload(self) -> Dict[str, Any]:
        """重新加载配置文件（外部修改后调用）"""
        return self.load()

    def get_enabled_reminders(self) -> list:
        """获取所有启用的提醒"""
        config = self.load()
        reminders = config.get("reminders", [])
        return [r for r in reminders if r.get("enabled", False)]
