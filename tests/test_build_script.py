import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


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

    def test_command_uses_current_data_syntax_and_dynamic_imports(self):
        module = importlib.import_module("build")

        command = module.build_command(console=True)

        self.assertIn("--console", command)
        self.assertNotIn("--windowed", command)
        self.assertTrue(any(arg.startswith("--add-data=") for arg in command))
        for source, destination in module.DATA_FILES:
            self.assertIn(f"--add-data={source}:{destination}", command)
        for dynamic_import in module.DYNAMIC_IMPORTS:
            self.assertIn(f"--hidden-import={dynamic_import}", command)
        self.assertFalse(any(arg == "--collect-all=PyQt5" for arg in command))

    def test_release_command_is_windowed(self):
        module = importlib.import_module("build")

        command = module.build_command()

        self.assertIn("--windowed", command)
        self.assertNotIn("--console", command)

    def test_preflight_failure_preserves_existing_build_outputs(self):
        module = importlib.import_module("build")
        with patch.object(
            module, "validate_build_environment", return_value=["missing"]
        ), patch("shutil.rmtree") as remove_tree, patch(
            "subprocess.run"
        ) as run_process:
            result = module.main([])

        self.assertEqual(result, 2)
        remove_tree.assert_not_called()
        run_process.assert_not_called()

    def test_preflight_reports_missing_inputs_and_pyinstaller(self):
        module = importlib.import_module("build")
        missing_main = Path("missing-main.py")
        with patch.object(module, "MAIN", missing_main), patch.object(
            module.importlib.util, "find_spec", return_value=None
        ):
            errors = module.validate_build_environment()

        self.assertTrue(any(str(missing_main) in error for error in errors))
        self.assertTrue(any("PyInstaller" in error for error in errors))

    def test_success_promotes_executable_and_removes_temporary_build(self):
        module = importlib.import_module("build")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            build_dir = root / "build"
            staged_dist = build_dir / "dist"
            backup_dist = build_dir / "previous-dist"
            dist_dir = root / "dist"
            stale_data = dist_dir / "data"
            stale_data.mkdir(parents=True)
            (stale_data / "pending_reminders.yaml").write_text(
                "stale reminder",
                encoding="utf-8",
            )

            def complete_build(*args, **kwargs):
                staged_dist.mkdir(parents=True)
                (staged_dist / "DesktopPet.exe").write_bytes(b"executable")
                return Mock(returncode=0)

            with patch.object(module, "ROOT", root), patch.object(
                module, "BUILD_DIR", build_dir
            ), patch.object(module, "STAGING_DIST_DIR", staged_dist), patch.object(
                module, "WORK_DIR", build_dir / "work"
            ), patch.object(module, "SPEC_DIR", build_dir / "spec"), patch.object(
                module, "BACKUP_DIST_DIR", backup_dist
            ), patch.object(
                module, "DIST_DIR", dist_dir
            ), patch.object(
                module, "validate_build_environment", return_value=[]
            ), patch(
                "subprocess.run", side_effect=complete_build
            ):
                result = module.main([])

            self.assertEqual(result, 0)
            self.assertEqual(
                (dist_dir / "DesktopPet.exe").read_bytes(),
                b"executable",
            )
            self.assertFalse(build_dir.exists())
            self.assertFalse((dist_dir / "data").exists())


if __name__ == "__main__":
    unittest.main()
