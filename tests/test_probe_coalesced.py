import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools.formats.coalesced import EmbeddedFile, SerializedString, serialize
from tools.research.probe_coalesced import alignment_key, inspect_manifest, main


class ProbeCoalescedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = serialize([EmbeddedFile(SerializedString("..\\Demo\\INT\\demo.int", "ascii", 0),
                                            SerializedString("[Fixture]\nText=Synthetic {0}\n", "ascii", 0))])
        self.image = self.root / "fixture.iso"
        self.image.write_bytes(self.data)
        self.manifest = self.root / "manifest.json"
        self.record = dict(path="fixture.iso::Demo/Coalesced.int", offset=0, size=len(self.data), sha256=hashlib.sha256(self.data).hexdigest())
        self.meta = dict(schema_version=1, errors=[], files=[
            dict(type="xdvdfs", path="fixture.iso", size=len(self.data), sha256=self.record["sha256"], disc="fixture"), self.record])
        self.save()

    def save(self):
        self.manifest.write_text(json.dumps(self.meta), encoding="utf-8")

    def test_readonly_roundtrip(self):
        result = inspect_manifest(self.manifest, self.root, self.root / "out")
        self.assertEqual(result["source_candidates"], 1)
        self.assertEqual(self.image.read_bytes(), self.data)
        catalog = json.loads((self.root / "out/source.catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["entries"][0]["source"], "Synthetic {0}")

    def test_hash_mismatch(self):
        self.record["sha256"] = "0" * 64; self.save()
        with self.assertRaises(ValueError):
            inspect_manifest(self.manifest, self.root, self.root / "out")

    def test_incomplete_inventory(self):
        self.meta["errors"] = ["synthetic failure"]; self.save()
        with self.assertRaises(ValueError):
            inspect_manifest(self.manifest, self.root, self.root / "out")

    def test_malformed_manifest(self):
        for invalid in ([], dict(schema_version=1, errors=[], files=[None])):
            self.manifest.write_text(json.dumps(invalid), encoding="utf-8")
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                inspect_manifest(self.manifest, self.root, self.root / "out")

    def test_protect_source_directory(self):
        with self.assertRaises(ValueError):
            inspect_manifest(self.manifest, self.root, self.root)

    def test_range_check(self):
        self.record["offset"] = -1; self.save()
        with self.assertRaises(ValueError):
            inspect_manifest(self.manifest, self.root, self.root / "out")

    def test_no_members(self):
        self.meta["files"].pop(); self.save()
        with self.assertRaises(ValueError):
            inspect_manifest(self.manifest, self.root, self.root / "out")

    def test_duplicate_basename(self):
        self.meta["files"].append(dict(self.record, path="fixture.iso::Other/Coalesced.int")); self.save()
        with self.assertRaises(ValueError):
            inspect_manifest(self.manifest, self.root, self.root / "out")
        self.assertFalse((self.root / "out/Coalesced.int.json").exists())

    def test_structural_alignment(self):
        a = dict(embedded_path="..\\Demo\\INT\\Demo.int", section="S", key="K", occurrence=1)
        b = dict(a, embedded_path="..\\Demo\\JPN\\Demo.jpn")
        self.assertEqual(alignment_key(a), alignment_key(b))

    def test_cli(self):
        with contextlib.redirect_stdout(io.StringIO()):
            result = main(["--manifest", str(self.manifest), "--image-root", str(self.root), "--output-dir", str(self.root / "out")])
        self.assertEqual(result, 0)

    def test_cli_failure(self):
        with contextlib.redirect_stderr(io.StringIO()):
            result = main(["--manifest", str(self.manifest), "--image-root", str(self.root), "--output-dir", str(self.root)])
        self.assertEqual(result, 1)

    def test_existing_output_hardlink_preserves_image(self):
        output = self.root / "out"; output.mkdir()
        os.link(self.image, output / "Coalesced.int.json")
        os.link(self.manifest, output / "source.catalog.json")
        before_manifest = self.manifest.read_bytes()
        inspect_manifest(self.manifest, self.root, output)
        self.assertEqual(self.image.read_bytes(), self.data)
        self.assertEqual(self.manifest.read_bytes(), before_manifest)
