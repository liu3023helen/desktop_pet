import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

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


if __name__ == "__main__":
    unittest.main()
