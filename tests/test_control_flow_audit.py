import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.research.audit_generated_control_flow import audit_text, audit_tree, main


class ControlFlowAuditTests(unittest.TestCase):
    def test_valid_backward_goto(self):
        text = 'DEFINE_REX_FUNC(f) {\nloc_1000:\n if (x) goto loc_1000;\n}\n'
        self.assertEqual(audit_text(text, "fixture.cpp")["findings"], [])

    def test_missing_label(self):
        text = 'DEFINE_REX_FUNC(f) {\n if (x) goto loc_1000;\n}\n'
        row = audit_text(text, "fixture.cpp")["findings"][0]
        self.assertEqual(row["target"], "loc_1000")
        self.assertEqual(row["line"], 2)

    def test_labels_not_borrowed_from_next_function(self):
        text = 'DEFINE_REX_FUNC(f) { goto loc_1000; }\nDEFINE_REX_FUNC(g) {\nloc_1000:\n return;\n}\n'
        self.assertEqual(len(audit_text(text, "fixture.cpp")["findings"]), 1)

    def test_explicit_unresolved_fatal(self):
        text = 'DEFINE_REX_FUNC(f) {\nREX_FATAL("Unresolved conditional branch to 0x1000");\n}\n'
        row = audit_text(text, "fixture.cpp")["findings"][0]
        self.assertEqual(row["type"], "unresolved-branch-fatal")

    def test_actual_sdk_diagnostic_spelling(self):
        text = 'DEFINE_REX_FUNC(f) {\nif (x) REX_FATAL("Unresolved branch from 0x82CE6768 to 0x82CE6754");\n}\n'
        row = audit_text(text, "fixture.cpp")["findings"][0]
        self.assertEqual(row["addresses"], ["0x82CE6768", "0x82CE6754"])

    def test_other_fatal_is_not_control_flow_finding(self):
        text = 'DEFINE_REX_FUNC(f) { REX_FATAL("synthetic invariant"); }\n'
        self.assertEqual(audit_text(text, "fixture.cpp")["findings"], [])

    def test_reject_unknown_template(self):
        with self.assertRaises(ValueError):
            audit_text("void f() {}", "fixture.cpp")

    def test_cli_report_and_readonly(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); generated = root / "generated"; generated.mkdir()
            source = generated / "fixture.cpp"
            original = b'DEFINE_REX_FUNC(f) { goto loc_1000; }\n'
            source.write_bytes(original)
            output = root / "audit.json"
            with contextlib.redirect_stdout(io.StringIO()):
                result = main([str(generated), "--output", str(output)])
            self.assertEqual(result, 1)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(json.loads(output.read_text())["status"], "FAIL")
            self.assertEqual(audit_tree(generated)["source_count"], 1)

    def test_cli_protects_input_tree(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([temp, "--output", str(Path(temp) / "out.json")]), 2)

    def test_known_metadata_sources_are_explicitly_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "demo_init.cpp").write_text("const rex::PPCImageInfo PPCImageConfig = {};", encoding="utf-8")
            (root / "demo_register.cpp").write_text("void demo_RegisterFunctions() { registrar->SetFunction(1, f); }", encoding="utf-8")
            (root / "demo_recomp.1.cpp").write_text("DEFINE_REX_FUNC(f) { return; }", encoding="utf-8")
            result = audit_tree(root)
            self.assertEqual(result["function_source_count"], 1)
            self.assertEqual(len(result["metadata_sources"]), 2)
