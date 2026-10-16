"""Synthetic XEX2 metadata fixtures; no proprietary input data."""
import contextlib
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest

from tools.formats.xex import XexError, main, parse_xex, version


def fixture(headers=()):
    data = bytearray(2048)
    data[:24] = struct.pack(">4s5I", b"XEX2", 1, 1536, 0, 256, len(headers))
    struct.pack_into(">II", data, 256, 0x184, 4096)
    struct.pack_into(">I", data, 256 + 0x110, 0x82000000)
    for i, (key, val, payload) in enumerate(headers):
        struct.pack_into(">II", data, 24 + i * 8, key, val)
        if payload is not None:
            data[val:val+len(payload)] = payload
    return data


class XexTests(unittest.TestCase):
    def test_minimal(self):
        result = parse_xex(fixture())
        self.assertEqual(result["security"]["load_address"], 0x82000000)
        self.assertEqual(result["optional_headers"], [])

    def test_execution_and_inline_address(self):
        payload = struct.pack(">4I4BI", 5, 0x20010003, 0x20010000, 10, 0, 0, 2, 2, 12)
        result = parse_xex(fixture([(0x40006, 768, payload), (0x10201, 0x82000000, None)]))
        self.assertEqual(result["execution_info"]["disc_number"], 2)
        self.assertEqual(result["execution_info"]["version"], "2.0.256.3")
        self.assertEqual(result["optional_headers"][1]["storage"], "inline")

    def test_version_bits(self):
        self.assertEqual(version(0x21234567), "2.1.9029.103")

    def test_basic_compression(self):
        payload = struct.pack(">IHH4I", 24, 1, 1, 16, 4, 32, 8)
        result = parse_xex(fixture([(0x3ff, 768, payload)]))
        self.assertEqual(result["file_format"]["decompressed_size"], 60)
        self.assertEqual(result["file_format"]["stored_data_size"], 48)

    def test_import_library(self):
        name = b"a.xex\0\0\0"
        lib = struct.pack(">I20sIIIHHI", 44, b"\0" * 20, 0, 0x20000000, 0x10000000, 0x100, 1, 0x82000004)
        payload = struct.pack(">3I", 12 + len(name) + len(lib), len(name), 1) + name + lib
        result = parse_xex(fixture([(0x103ff, 768, payload)]))
        self.assertEqual(result["import_libraries"][0]["name"], "a.xex")
        self.assertEqual(result["import_libraries"][0]["import_record_addresses"], [0x82000004])

    def test_secret_omission(self):
        data = fixture([(0x40404, 768, b"SECRET_LAN_VALUE")])
        data[256+0x150:256+0x160] = b"SECRET_IMAGE_KEY"
        output = json.dumps(parse_xex(data))
        self.assertNotIn("SECRET", output)
        self.assertNotIn(b"SECRET_IMAGE_KEY".hex(), output)

    def test_bad_magic(self):
        with self.assertRaises(XexError):
            parse_xex(b"bad" * 100)

    def test_truncated(self):
        with self.assertRaises(XexError):
            parse_xex(b"XEX2")

    def test_header_count_bounds(self):
        data = fixture()
        struct.pack_into(">I", data, 20, 1000000)
        with self.assertRaises(XexError):
            parse_xex(data)

    def test_optional_offset_bounds(self):
        with self.assertRaises(XexError):
            parse_xex(fixture([(0x40006, 2000, b"\0"*24)]))

    def test_variable_size_bounds(self):
        with self.assertRaises(XexError):
            parse_xex(fixture([(0x3ff, 768, struct.pack(">I", 0xffff))]))

    def test_duplicate_key(self):
        with self.assertRaises(XexError):
            parse_xex(fixture([(0x10100, 1, None), (0x10100, 2, None)]))

    def test_overlap_security(self):
        with self.assertRaises(XexError):
            parse_xex(fixture([(0x40310, 280, b"\0" * 64)]))

    def test_invalid_import_count(self):
        with self.assertRaises(XexError):
            parse_xex(fixture([(0x103ff, 768, struct.pack(">3I", 12, 0, 20))]))

    def test_cli_slice_and_hash_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp)/"source.bin", Path(temp)/"out.json"
            source.write_bytes(b"padding!" + fixture())
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(source), "--offset", "8", "--size", "2048", "--output", str(output)]), 0)
                before = output.read_bytes()
                self.assertEqual(main([str(source), "--offset", "8", "--expected-sha256", "0"*64, "--output", str(output)]), 1)
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(json.loads(before)["source"]["offset"], 8)

    def test_cli_prevents_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)/"source.bin"
            source.write_bytes(fixture())
            before = source.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(source), "--output", str(source)]), 1)
            self.assertEqual(source.read_bytes(), before)

    def test_cli_prevents_hardlink_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp)/"source.bin", Path(temp)/"alias.bin"
            source.write_bytes(fixture())
            os.link(source, output)
            before = source.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(source), "--output", str(output)]), 1)
            self.assertEqual(source.read_bytes(), before)

    def test_cli_does_not_follow_preexisting_temporary_hardlink(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp)/"source.bin", Path(temp)/"out.json"
            source.write_bytes(fixture())
            os.link(source, output.with_name(output.name + ".tmp"))
            before = source.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(source), "--output", str(output)]), 0)
            self.assertEqual(source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
