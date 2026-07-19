import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication

from animation_player import AnimationPlayer, _natural_sort_key


class AnimationPlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_frame_names_use_natural_numeric_order(self):
        frames = [Path("frame_10.png"), Path("frame_2.png"), Path("frame_1.png")]

        ordered = sorted(frames, key=_natural_sort_key)

        self.assertEqual(
            [path.name for path in ordered],
            ["frame_1.png", "frame_2.png", "frame_10.png"],
        )

    def test_replaying_active_animation_updates_rate_and_loop(self):
        player = AnimationPlayer()
        player._frames_cache["test"] = [QPixmap(1, 1), QPixmap(1, 1)]
        self.addCleanup(player.stop)

        self.assertTrue(player.play("test", fps=5, loop=True))
        self.assertTrue(player.play("test", fps=10, loop=False))

        self.assertEqual(player._timer.interval(), 100)
        self.assertEqual(player._fps, 10)
        self.assertFalse(player._loop)


if __name__ == "__main__":
    unittest.main()
