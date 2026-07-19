import importlib
import sys
import unittest
from unittest.mock import patch


class BuildScriptTests(unittest.TestCase):
    def test_import_has_no_build_or_cleanup_side_effects(self):
        sys.modules.pop("build", None)
        with patch("shutil.rmtree") as remove_tree, patch(
            "subprocess.run"
        ) as run_process:
            module = importlib.import_module("build")

        self.assertTrue(callable(module.main))
        remove_tree.assert_not_called()
        run_process.assert_not_called()


if __name__ == "__main__":
    unittest.main()
