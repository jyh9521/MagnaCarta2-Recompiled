import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/verify_stage.py"


class VerifyStageTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("git") and shutil.which("bash"), "requires Git and bash")
    def test_isolated_source_transaction(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"; base = Path(temp) / "baseline"
            root.mkdir(); (root / "tests").mkdir()
            (root / ".gitignore").write_text("local/\n", encoding="utf-8")
            original = "import unittest\nclass Check(unittest.TestCase):\n def test_one(self): self.assertEqual(1,1)\n"
            source = root / "tests/test_fixture.py"; source.write_text(original, encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
            manifest = {}
            for rel in (".gitignore", "tests/test_fixture.py"):
                dest = base / rel; dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root / rel, dest)
                manifest[rel] = hashlib.sha256(dest.read_bytes()).hexdigest()
            manifest_path = Path(temp) / "manifest.json"; manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            source.write_text(original + " def test_two(self): self.assertEqual(2,2)\n", encoding="utf-8")
            (root / "added.txt").write_text("synthetic new file\n", encoding="utf-8")
            output = root / "local/evidence"
            command = [sys.executable, str(SCRIPT), "--baseline-dir", str(base), "--baseline-manifest", str(manifest_path),
                       "--output-dir", str(output), "--modified-file", "tests/test_fixture.py"]
            result = subprocess.run(command, cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS source transaction", result.stdout)
            self.assertIn("test_two", source.read_text(encoding="utf-8"))
            self.assertEqual((output / "rollback-copy/tests/test_fixture.py").read_bytes(), (base / "tests/test_fixture.py").read_bytes())
            self.assertFalse((output / "rollback-copy/added.txt").exists())
            self.assertTrue((root / "added.txt").exists())
            for name in ("MODIFIED_FILE.py", "DIFF_FILE.patch", "VERIFICATION.txt", "ROLLBACK.sh"):
                self.assertTrue((output / name).read_bytes())
            second = subprocess.run(command, cwd=root, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
