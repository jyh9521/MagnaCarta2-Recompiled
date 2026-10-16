"""自制数据测试，不含原版游戏资源。"""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools.inventory.scan import MAGIC, SECTOR, digest_range, identify, main, scan, xdvdfs_entries


def image():
    data = bytearray(40 * SECTOR)
    data[32 * SECTOR:32 * SECTOR + 20] = MAGIC
    data[33 * SECTOR - 20:33 * SECTOR] = MAGIC
    struct.pack_into("<II", data, 32 * SECTOR + 20, 34, 64)
    name = b"default.xex"
    struct.pack_into("<HHIIBB", data, 34 * SECTOR, 0, 0, 35, 24, 0, len(name))
    data[34 * SECTOR + 14:34 * SECTOR + 14 + len(name)] = name
    data[35 * SECTOR:35 * SECTOR + 24] = b"XEX2" + struct.pack(">5I", 1, 24, 0, 24, 0)
    return data


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.input = self.root / "input"
        self.input.mkdir()

    def put(self, name="a.dat", content=b"abc"):
        p = self.input / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
        return p

    def test_recursive_unicode_and_hash(self):
        self.put("子目录/资源.dat")
        r = scan([self.input], "disc1")
        self.assertEqual(r["files"][0]["sha256"], hashlib.sha256(b"abc").hexdigest())
        self.assertEqual(r["files"][0]["path"], "子目录/资源.dat")
        self.assertEqual(r["files"][0]["disc"], "disc1")

    def test_empty_file(self):
        self.put(content=b"")
        self.assertEqual(scan([self.input])["files"][0]["size"], 0)

    def test_empty_directory(self):
        self.assertEqual(scan([self.input])["summary"]["record_count"], 0)

    def test_missing(self):
        self.assertEqual(len(scan([self.input / "missing"])["errors"]), 1)

    def test_magic_not_extension(self):
        self.put("fake.xex")
        self.assertEqual(scan([self.input])["files"][0]["type"], "unknown")

    def test_signatures(self):
        for head, expected in [(b"XEX2", "xex2"), (bytes.fromhex("9e2a83c1"), "unreal-package-candidate"),
                               (bytes.fromhex("c1832a9e"), "unreal-package-candidate"), (b"BIKi", "bink-candidate"),
                               (b"RIFF", "riff-candidate"), (b"", "unknown")]:
            with self.subTest(head=head):
                self.assertEqual(identify(head)[0], expected)

    def test_deterministic(self):
        self.put("z"); self.put("a")
        self.assertEqual(scan([self.input]), scan([self.input]))

    def test_duplicate_input_label(self):
        p = self.put()
        self.assertTrue(scan([p, p])["errors"])

    def test_digest_range(self):
        self.assertEqual(digest_range(io.BytesIO(b"abcd"), 1, 2, 4), hashlib.sha256(b"bc").hexdigest())

    def test_short_digest(self):
        with self.assertRaises(ValueError):
            digest_range(io.BytesIO(b"a"), 0, 2, 2)

    def test_range(self):
        with self.assertRaises(ValueError):
            digest_range(io.BytesIO(b"a"), -1, 1, 1)

    def test_xdvdfs(self):
        p = self.put("fixture.iso", image())
        r = scan([p], "disc1", True)
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["summary"]["record_count"], 2)
        self.assertEqual(r["files"][1]["xex_header"]["module_flags"], 1)

    def test_extensionless_member(self):
        from tools.inventory.scan import record
        r = record(io.BytesIO(b"abc"), "disc.iso::nxeart", 0, 3, 3, "disc1")
        self.assertEqual(r["extension"], "")

    def test_package_version_candidate(self):
        p = self.put(content=bytes.fromhex("9e2a83c1001901be"))
        r = scan([p])["files"][0]
        self.assertEqual(r["package_version_candidate"], dict(raw_word=0x1901be, version=446, licensee_version=25, byte_order="big"))
        self.assertEqual(r["parse_status"], "magic-only")

    def test_nested_directory(self):
        d = image()
        struct.pack_into("<HHIIBB", d, 34 * SECTOR, 0, 0, 36, 64, 0x10, 3)
        d[34 * SECTOR + 14:34 * SECTOR + 17] = b"dir"
        struct.pack_into("<HHIIBB", d, 36 * SECTOR, 0, 0, 35, 24, 0, 4)
        d[36 * SECTOR + 14:36 * SECTOR + 18] = b"file"
        _, entries = xdvdfs_entries(io.BytesIO(d), len(d))
        self.assertEqual(entries, [("dir/file", 35 * SECTOR, 24)])

    def test_directory_cycle(self):
        d = image()
        struct.pack_into("<HHIIBB", d, 34 * SECTOR, 0, 0, 34, 64, 0x10, 3)
        d[34 * SECTOR + 14:34 * SECTOR + 17] = b"dir"
        self.invalid(d)

    def invalid(self, data):
        with self.assertRaises(ValueError):
            xdvdfs_entries(io.BytesIO(data), len(data))

    def test_missing_descriptor(self):
        self.invalid(bytearray(40 * SECTOR))

    def test_bad_trailing_magic(self):
        d = image(); d[33 * SECTOR - 1] = 0; self.invalid(d)

    def test_directory_outside_image(self):
        d = image(); struct.pack_into("<I", d, 32 * SECTOR + 20, 99); self.invalid(d)

    def test_member_outside_image(self):
        d = image(); struct.pack_into("<I", d, 34 * SECTOR + 4, 99); self.invalid(d)

    def test_tree_cycle(self):
        d = image(); struct.pack_into("<H", d, 34 * SECTOR, 1)
        struct.pack_into("<HHIIBB", d, 34 * SECTOR + 4, 1, 0, 35, 1, 0, 1)
        d[34 * SECTOR + 18] = 65; self.invalid(d)

    def test_tree_pointer_outside(self):
        d = image(); struct.pack_into("<H", d, 34 * SECTOR, 65535); self.invalid(d)

    def test_path_traversal(self):
        d = image(); d[34 * SECTOR + 14] = 47; self.invalid(d)

    def test_long_name(self):
        d = image(); d[34 * SECTOR + 13] = 255; self.invalid(d)

    def test_permission_error(self):
        self.put()
        with patch.object(Path, "open", side_effect=PermissionError("fixture denied")):
            self.assertTrue(scan([self.input])["errors"])

    def test_detect_changed_input(self):
        p = self.put()
        from tools.inventory import scan as module
        original = module.record
        def mutate(*args):
            r = original(*args)
            p.write_bytes(b"changed")
            return r
        with patch.object(module, "record", side_effect=mutate):
            self.assertTrue(scan([p])["errors"])

    def test_cli_json_and_read_only(self):
        p = self.put(); before = p.read_bytes(); output = self.root / "out.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main([str(self.input), "--output", str(output)]), 0)
        self.assertEqual(json.loads(output.read_text())["summary"]["record_count"], 1)
        self.assertEqual(p.read_bytes(), before)

    def test_cli_error_exit(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main([str(self.input / "missing"), "--output", str(self.root / "bad.json")]), 1)

    def test_cli_refuses_output_in_input(self):
        p = self.put()
        for output in (p, self.input / "new.json"):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as e:
                main([str(self.input), "--output", str(output)])
            self.assertEqual(e.exception.code, 2)

    def test_cli_write_error(self):
        self.put(); output = self.root / "file"; output.write_bytes(b"blocked")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([str(self.input), "--output", str(output / "out.json")]), 2)


if __name__ == "__main__":
    unittest.main()
