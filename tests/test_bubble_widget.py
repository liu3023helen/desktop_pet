import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QPushButton

from bubble_widget import BubbleWidget


class _PetStub:
    def __init__(self, geometry):
        self._geometry = geometry

    def geometry(self):
        return self._geometry


class BubbleSizingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.bubble = BubbleWidget(max_width=220)

    def tearDown(self):
        self.bubble.close()

    def test_long_text_grows_vertically_within_max_width(self):
        self.bubble.show_bubble("这是一段需要自动换行的提醒文字" * 12, 1000)

        self.assertLessEqual(self.bubble.width(), 220)
        self.assertGreater(self.bubble.height(), 70)

    def test_short_text_can_shrink_after_long_text(self):
        self.bubble.show_bubble("很长的提醒文字" * 20, 1000)
        long_height = self.bubble.height()

        self.bubble.show_bubble("完成", 1000)

        self.assertLess(self.bubble.height(), long_height)
        self.assertEqual(self.bubble.height(), 70)

    def test_bubble_position_stays_inside_available_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.bubble._pet_window = _PetStub(screen)

        self.bubble.show_bubble("边界", 1000)

        self.assertGreaterEqual(self.bubble.x(), screen.left())
        self.assertGreaterEqual(self.bubble.y(), screen.top())
        self.assertLessEqual(
            self.bubble.x() + self.bubble.width(), screen.right() + 1
        )
        self.assertLessEqual(
            self.bubble.y() + self.bubble.height(), screen.bottom() + 1
        )

    def test_loading_mode_is_persistent_and_has_no_actions(self):
        self.bubble.show_loading("正在获取天气...")

        self.assertEqual(self.bubble.mode, "loading")
        self.assertFalse(self.bubble._hide_timer.isActive())
        self.assertTrue(self.bubble._actions_widget.isHidden())

    def test_result_mode_uses_eight_second_default(self):
        self.bubble.show_result("天气获取成功")

        self.assertEqual(self.bubble.mode, "result")
        self.assertTrue(self.bubble._hide_timer.isActive())
        self.assertEqual(self.bubble._hide_timer.interval(), 8000)
        self.assertTrue(self.bubble._actions_widget.isHidden())

    def test_reminder_mode_is_persistent_and_emits_actions(self):
        emitted = []
        self.bubble.action_triggered.connect(emitted.append)
        self.bubble.show_reminder("该打卡啦~")

        self.assertEqual(self.bubble.mode, "reminder")
        self.assertFalse(self.bubble._hide_timer.isActive())
        self.assertFalse(self.bubble._actions_widget.isHidden())

        self.bubble.findChild(QPushButton, "bubble_snooze_button").click()
        self.bubble.findChild(QPushButton, "bubble_acknowledge_button").click()

        self.assertEqual(emitted, ["snooze_10", "acknowledge"])

    def test_only_interactive_reminder_mode_can_activate(self):
        self.bubble.show_result("状态结果")
        self.assertTrue(self.bubble.testAttribute(Qt.WA_ShowWithoutActivating))

        self.bubble.show_reminder("需要操作")
        self.assertFalse(self.bubble.testAttribute(Qt.WA_ShowWithoutActivating))

    def test_switching_from_reminder_to_result_hides_actions(self):
        self.bubble.show_reminder("提醒")
        self.bubble.show_result("处理完成")

        self.assertEqual(self.bubble.mode, "result")
        self.assertTrue(self.bubble._actions_widget.isHidden())


if __name__ == "__main__":
    unittest.main()
