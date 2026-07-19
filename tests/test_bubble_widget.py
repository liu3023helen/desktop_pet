import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from bubble_widget import BubbleWidget


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


if __name__ == "__main__":
    unittest.main()
