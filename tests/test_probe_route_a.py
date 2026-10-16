import contextlib
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.research import probe_route_a as probe


class RouteAProbeTests(unittest.TestCase):
    def test_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"file"
            path.write_bytes(b"fixture")
            self.assertEqual(probe.digest(path), hashlib.sha256(b"fixture").hexdigest())

    def test_wrong_sdk_hash_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root/"sdk.zip"
            sdk.write_bytes(b"wrong SDK")
            with self.assertRaisesRegex(ValueError, "SDK ZIP"):
                probe.prepare_input(root/"absent.iso", sdk, root/"absent.exe", root/"output")
            self.assertFalse((root/"output").exists())

    def test_verified_input_extraction_and_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/"disc.iso"
            source.write_bytes(b"PAD!XEX2fixture")
            with patch.object(probe, "digest", side_effect=lambda p: probe.SDK_ZIP_SHA256 if str(p).endswith("zip") else probe.SDK_EXE_SHA256), \
                 patch.object(probe, "XEX_OFFSET", 4), patch.object(probe, "XEX_SIZE", 11), \
                 patch.object(probe, "XEX_SHA256", hashlib.sha256(b"XEX2fixture").hexdigest()):
                output = root/"output"
                result = probe.prepare_input(source, root/"sdk.zip", root/"sdk.exe", output)
                self.assertEqual(result.read_bytes(), b"XEX2fixture")
                with self.assertRaises(FileExistsError):
                    probe.prepare_input(source, root/"sdk.zip", root/"sdk.exe", output)
            self.assertEqual(source.read_bytes(), b"PAD!XEX2fixture")

    def test_wrong_xex_hash_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/"disc.iso"
            source.write_bytes(b"wrong XEX")
            with patch.object(probe, "digest", side_effect=[probe.SDK_ZIP_SHA256, probe.SDK_EXE_SHA256]), \
                 patch.object(probe, "XEX_OFFSET", 0), patch.object(probe, "XEX_SIZE", 9):
                with self.assertRaisesRegex(ValueError, "unsupported original"):
                    probe.prepare_input(source, root/"sdk.zip", root/"sdk.exe", root/"output")
            self.assertFalse((root/"output").exists())

    def test_cli_bad_hash_never_invokes_sdk(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root/"sdk.zip"
            sdk.write_bytes(b"wrong SDK")
            with patch.object(probe, "run_step") as run, contextlib.redirect_stderr(io.StringIO()):
                status = probe.main(["--iso", str(root/"disc.iso"), "--sdk-zip", str(sdk),
                    "--sdk-exe", str(root/"sdk.exe"), "--output", str(root/"output")])
            self.assertEqual(status, 1)
            run.assert_not_called()

    def test_wrong_compiler_hash(self):
        with patch.object(probe, "digest", side_effect=[probe.LLVM_PACKAGE_SHA256, "wrong"]):
            with self.assertRaisesRegex(ValueError, "Clang compiler"):
                probe.verify_compiler(Path("llvm.exe"), Path("clang-cl.exe"))

    def test_compiler_hash_pair(self):
        with patch.object(probe, "digest", side_effect=[probe.LLVM_PACKAGE_SHA256, probe.CLANG_CL_SHA256]):
            probe.verify_compiler(Path("llvm.exe"), Path("clang-cl.exe"))


if __name__ == "__main__":
    unittest.main()
