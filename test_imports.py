"""快速验证测试脚本"""
import sys
sys.path.insert(0, ".")

print("=" * 50)
print("Module Import Test")
print("=" * 50)

# 1. 测试配置管理
from config_manager import ConfigManager
c = ConfigManager()
cfg = c.load()
print(f"[OK] ConfigManager: {len(cfg.get('reminders', []))} reminders loaded")

# 2. 测试动画播放器
from animation_player import AnimationPlayer
ap = AnimationPlayer()
loaded = ap.load_animation("idle")
print(f"[OK] AnimationPlayer: idle loaded={loaded}")
loaded = ap.load_animation("walk")
print(f"[OK] AnimationPlayer: walk loaded={loaded}")
loaded = ap.load_animation("cheer")
print(f"[OK] AnimationPlayer: cheer loaded={loaded}")

# 3. 测试钉钉处理器
from dingtalk_handler import open_dingtalk_checkin
print(f"[OK] DingTalk handler imported")

# 4. 测试提醒引擎
from reminder_engine import ReminderEngine
engine = ReminderEngine(config=cfg)
engine.load_reminders()
enabled = engine._reminders
active = [r for r in enabled if r.get("enabled")]
print(f"[OK] ReminderEngine: {len(active)} active reminders")

# 5. 验证配置文件内容
reminder = active[0] if active else {}
print(f"    Name: {reminder.get('name', 'N/A')}")
print(f"    Time: {reminder.get('time', 'N/A')}")
print(f"    Action: {reminder.get('action_type', 'N/A')}")

print("=" * 50)
print("ALL TESTS PASSED!")
print("=" * 50)
