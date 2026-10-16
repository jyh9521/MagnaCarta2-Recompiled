import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from tools.research import verify_branch_ranges as branch


class BranchRangeTests(unittest.TestCase):
    def test_negative_displacements(self):
        self.assertEqual(branch.branch_target(0x1000, 0x409AFFEC), 0xFEC)
        self.assertEqual(branch.branch_target(0x1000, 0x419AFFF0), 0xFF0)

    def test_forward_displacement(self):
        self.assertEqual(branch.branch_target(0x1000, 0x419A0010), 0x1010)

    def test_link_and_nonbranch_rejected(self):
        for word in (0x409AFFED, 0x4E800020):
            with self.assertRaises(ValueError):
                branch.branch_target(0x1000, word)

    def test_wrong_xex_rejected_before_key_source(self):
        with self.assertRaisesRegex(ValueError, "XEX hash"):
            branch.image_from_xex(b"fixture", "not-present")

    def test_wrong_loader_source_rejected(self):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"loader.cc"
            path.write_bytes(b"fixture")
            with patch.object(branch, "XEX_SHA256", hashlib.sha256(b"fixture").hexdigest()):
                with self.assertRaisesRegex(ValueError, "loader source hash"):
                    branch.image_from_xex(b"fixture", path)

    def test_first_real_range_paths(self):
        address = 0x82CE6748
        code = bytes.fromhex(branch.RANGES[address])
        count = 0
        for selected in range(4):
            for flag in (0, 1, 2, 3, 128, 255):
                # Exercise direct pointer, fallback1, fallback2, absent paths.
                values = [0x2000 if selected == i else 0 for i in range(3)]
                mem = {0x1000+712: values[0], 0x1000+708: values[1], 0x1000+716: values[2], 0x2000+468: flag}
                result = branch.execute_leaf(code, address, {3: 0x1000}, mem)
                self.assertEqual(result["return"], flag & 1 if selected < 3 else 0)
                self.assertEqual(result["dispatch"], None)
                if selected in (1, 2):
                    self.assertIn(0x82CE6754, result["trace"])
                    self.assertIn(0x82CE6768 if selected == 1 else 0x82CE6774, result["trace"])
                count += 1
        self.assertEqual(count, 24)

    def test_second_real_range_paths(self):
        address = 0x82DA3488
        code = bytes.fromhex(branch.RANGES[address])
        for outer, inner in ((0, 0), (0x2000, 0), (0x2000, 0x3000)):
            mem = {0x1050: outer, 0x207C: inner, 0x3000: 0x4000, 0x411C: 0x5000}
            result = branch.execute_leaf(code, address, {3: 0x1000}, mem)
            self.assertEqual(result["return"], inner if outer and inner else 0)
            self.assertEqual(result["dispatch"], 0x5000 if outer and inner else None)
            if outer and not inner:
                self.assertIn(0x82DA34A4, result["trace"])
                self.assertIn(0x82DA3494, result["trace"])

    def test_oracle_unknown_opcode_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            branch.execute_leaf(bytes(4), 0x1000, {}, {})

    def test_oracle_missing_memory_rejected(self):
        with self.assertRaises(KeyError):
            branch.execute_leaf(bytes.fromhex(branch.RANGES[0x82CE6748]), 0x82CE6748, {3: 0x1000}, {})

    def test_generated_missing_functions_rejected(self):
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaisesRegex(ValueError, "both contiguous"):
                branch.verify_generated(path)

    def test_generated_missing_label_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"fixture_recomp.0.cpp"
            path.write_text("DEFINE_REX_FUNC(sub_1000) {\ngoto loc_1004;\n}\n")
            with self.assertRaisesRegex(ValueError, "undeclared generated labels"):
                branch.verify_generated(directory)

    def test_generated_fixture_gotos(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"fixture_recomp.0.cpp"
            body = "DEFINE_REX_FUNC(sub_82CE6748) {\nif (ctx.cr6.eq) goto loc_82CE6760;\nloc_82CE6760:\nloc_82CE6754:\n" + "if (!ctx.cr6.eq) goto loc_82CE6754;\n"*2 + "}\n"
            body += "DEFINE_REX_FUNC(sub_82DA3488) {\nif (!ctx.cr6.eq) goto loc_82DA349C;\nloc_82DA349C:\nloc_82DA3494:\nif (ctx.cr6.eq) goto loc_82DA3494;\n}\n"
            path.write_text(body)
            self.assertEqual(branch.verify_generated(directory)["verified_gotos"], 5)
            path.write_text(body + "REX_FATAL(\"fixture\");")
            with self.assertRaisesRegex(ValueError, "still contains"):
                branch.verify_generated(directory)


if __name__ == "__main__":
    unittest.main()
