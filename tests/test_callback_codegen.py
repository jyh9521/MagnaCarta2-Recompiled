"""Synthetic guard contracts; real strict codegen is a separate Windows experiment."""
from pathlib import Path
import hashlib
import tempfile
import unittest
from unittest.mock import patch
from tools.research import probe_callback_codegen as p


class CallbackCodegenTests(unittest.TestCase):
    def test_range_and_hint(self):
        code=b'fixture'*8
        with patch.object(p,'BASE',p.ENTRY),patch.object(p,'SIZE',len(code)),patch.object(p,'RANGE_SHA256',hashlib.sha256(code).hexdigest()):
            self.assertEqual(p.verify_hint(code,f'[functions.0x8234FF10]\nsize={len(code)}')['entry'],p.ENTRY)
    def test_unknown_range(self):
        with self.assertRaisesRegex(ValueError,'range hash'):
            p.verify_hint(b'bad','[functions.0x8234FF10]\nsize=0x30')
    def test_wrong_size(self):
        with self.assertRaisesRegex(ValueError,'hint'):
            p.verify_hint(b'', '[functions.0x8234FF10]\nsize=0x34')
    def test_extra_entry(self):
        with self.assertRaisesRegex(ValueError,'hint'):
            p.verify_hint(b'', '[functions.0x8234FF10]\nsize=0x30\n[functions.0x8234FF40]\nsize=4')
    def fixture(self,root,body='return;'):
        (root/'a_recomp.0.cpp').write_text('DEFINE_REX_FUNC(sub_8234FF10) {\n'+body+'\n}')
        (root/'mc2_probe_register.cpp').write_text('registrar->SetFunction(0x8234FF10, sub_8234FF10);')
    def test_body_and_registration(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            self.assertTrue(p.verify_entry(root)['registered'])
    def test_fatal_body(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root,'REX_FATAL("bad");')
            with self.assertRaisesRegex(ValueError,'body'):p.verify_entry(root)
    def test_duplicate_body(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            (root/'b_recomp.1.cpp').write_bytes((root/'a_recomp.0.cpp').read_bytes())
            with self.assertRaisesRegex(ValueError,'body'):p.verify_entry(root)
    def test_missing_mapping(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            (root/'mc2_probe_register.cpp').write_text('registrar->SetFunction(0x8234FF40, sub_8234FF10);')
            with self.assertRaisesRegex(ValueError,'registration'):p.verify_entry(root)


if __name__=='__main__':unittest.main()
