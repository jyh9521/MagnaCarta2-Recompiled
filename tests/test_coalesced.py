"""全部样本由测试现场构造，不包含原版源文。"""
import contextlib
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest

from tools.formats.coalesced import (EmbeddedFile, SerializedString, analyze, extract_entries,
                                    main, parse, script_counts, serialize)
from tools.validators.validate_catalog import validate


def fixture(content="[Demo]\nText=自制 {0}$n\n", encoding="utf-16-le", path="..\\Fixture\\demo.int"):
    return [EmbeddedFile(SerializedString(path, "ascii", 0), SerializedString(content, encoding, 0))]


class CoalescedTests(unittest.TestCase):
    def test_utf16_roundtrip_and_code_units(self):
        original = fixture("[Demo]\nText=自制 😀\n")
        data = serialize(original)
        self.assertEqual(serialize(parse(data)), data)
        self.assertEqual(parse(data)[0].content.text, original[0].content.text)

    def test_ascii_roundtrip(self):
        data = serialize(fixture("[Demo]\nText=synthetic\n", "ascii"))
        self.assertEqual(serialize(parse(data)), data)

    def test_utf8_roundtrip(self):
        data = serialize(fixture("测试", "utf-8"))
        self.assertEqual(parse(data)[0].content.encoding, "utf-8")
        self.assertEqual(serialize(parse(data)), data)

    def test_opaque_bytes_retained_not_exported(self):
        data = serialize(fixture("\xff", "opaque-8bit"))
        result = analyze(data, "synthetic.int")
        self.assertTrue(result["roundtrip_equal"])
        self.assertEqual(result["summary"]["opaque_documents"], 1)
        self.assertEqual(result["catalog"]["entries"], [])

    def test_empty_table(self):
        self.assertEqual(parse(struct.pack(">i", 0)), [])

    def test_zero_length_content(self):
        self.assertEqual(parse(serialize(fixture("", "zero")))[0].content.encoding, "zero")

    def test_nonempty_zero_rejected(self):
        with self.assertRaises(ValueError):
            serialize(fixture("a", "zero"))

    def test_bad_encoding(self):
        with self.assertRaises(ValueError):
            serialize(fixture("a", "invented"))

    def test_truncation_every_byte(self):
        data = serialize(fixture())
        for n in range(len(data)):
            with self.subTest(n=n), self.assertRaises((ValueError, UnicodeError)):
                parse(data[:n])

    def test_invalid_counts(self):
        for count in (-1, 1, 100001, 2147483647):
            with self.subTest(count=count), self.assertRaises(ValueError):
                parse(struct.pack(">i", count))

    def test_trailing_data(self):
        with self.assertRaises(ValueError):
            parse(serialize(fixture()) + b"\x00")

    def test_bad_narrow_terminator(self):
        data = bytearray(serialize(fixture("x", "ascii"))); data[-1] = 1
        with self.assertRaises(ValueError):
            parse(data)

    def test_bad_wide_terminator(self):
        data = bytearray(serialize(fixture())); data[-1] = 1
        with self.assertRaises(ValueError):
            parse(data)

    def test_extreme_string_length(self):
        with self.assertRaises(ValueError):
            parse(struct.pack(">ii", 2, -2147483648) + b"\x00" * 4)

    def test_duplicate_paths(self):
        f = fixture()
        with self.assertRaises(ValueError):
            serialize(f + f)

    def test_empty_path(self):
        with self.assertRaises(ValueError):
            serialize(fixture(path=""))

    def test_embedded_nul_path(self):
        with self.assertRaises(ValueError):
            serialize(fixture(path="a\x00b"))

    def test_preserve_duplicate_ini_keys(self):
        rows = extract_entries(fixture("[Demo]\n+Text=one\n+Text=two=three\n;X=comment\n"), "fixture")
        self.assertEqual([r["occurrence"] for r in rows], [1, 2])
        self.assertEqual([r["source"] for r in rows], ["one", "two=three"])
        self.assertEqual(len({r["id"] for r in rows}), 2)

    def test_stable_ids(self):
        a = extract_entries(fixture("[Demo]\nText=one\n"), "fixture")
        b = extract_entries(fixture("; comment\n[Demo]\nText=two\n"), "fixture")
        self.assertEqual(a[0]["id"], b[0]["id"])

    def test_catalog_valid(self):
        result = analyze(serialize(fixture()), "fixture")
        self.assertEqual(validate(result["catalog"]), [])
        self.assertEqual(result["catalog"]["entries"][0]["source_locale"], "und")

    def test_script_counts_not_locale_guess(self):
        self.assertEqual(script_counts("A한あ字"), dict(hangul=1, kana=1, han=1))

    def test_cli_good_and_hash_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "fixture.dat"; out = Path(tmp) / "report.json"
            data = serialize(fixture()); p.write_bytes(data)
            argv = [str(p), "--sha256", hashlib.sha256(data).hexdigest(), "--resource", "synthetic", "--output", str(out)]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(argv), 0)
            self.assertTrue(json.loads(out.read_text(encoding="utf-8"))["roundtrip_equal"])
            self.assertEqual(p.read_bytes(), data)
            argv[2] = "0" * 64
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(argv), 1)

    def test_cli_invalid_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "fixture"; p.write_bytes(b"x")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(p), "--offset", "-1", "--sha256", "0" * 64, "--resource", "x", "--output", str(p.parent / "out")]), 1)

    def test_cli_hardlink_output_preserves_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "input"; output = Path(tmp) / "output"
            data = serialize(fixture()); source.write_bytes(data)
            os.link(source, output)
            with contextlib.redirect_stdout(io.StringIO()):
                result = main([str(source), "--sha256", hashlib.sha256(data).hexdigest(), "--resource", "synthetic", "--output", str(output)])
            self.assertEqual(result, 0)
            self.assertEqual(source.read_bytes(), data)
            self.assertFalse(source.samefile(output))

    def test_cli_refuses_same_output(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["fixture", "--sha256", "0" * 64, "--resource", "x", "--output", "fixture"])


if __name__ == "__main__":
    unittest.main()
