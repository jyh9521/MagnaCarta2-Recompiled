"""Synthetic guard contracts; real strict codegen is a separate Windows experiment."""
from pathlib import Path
import hashlib
import tempfile
import unittest
from unittest.mock import patch
from tools.research import probe_callback_codegen as p


class CallbackCodegenTests(unittest.TestCase):
    def test_indexed_tail_profile(self):
        self.assertEqual(p.profile_fields('indexed-tail'),(0x82A3DEA0,72,'da78cc530445e6be3717bc6cec9e6cf949e163d65dc481ee5d6f63d4648b708a'))

    def test_indexed_tail_exact_hint(self):
        code=bytes.fromhex('8943003c548b063e7ca92b787cc533787f0b5040419800103c608007606300574e80002081430024556b18387ce63b787d244b787c6b502e81630000814b00107d4903a64e800420')
        with patch.object(p,'BASE',0x82A3DEA0):
            self.assertEqual(p.verify_hint(code,'[functions.0x82A3DEA0]\nsize=72','indexed-tail')['size'],72)

    def test_indexed_tail_no_truncation(self):
        with self.assertRaisesRegex(ValueError,'hint'):
            p.verify_hint(b'','[functions.0x82A3DEA0]\nsize=36','indexed-tail')

    def test_indexed_tail_wrong_bytes(self):
        with self.assertRaisesRegex(ValueError,'range hash'):
            p.verify_hint(bytes(72),'[functions.0x82A3DEA0]\nsize=72','indexed-tail')

    def test_indexed_tail_registration(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            for path in root.iterdir():path.write_text(path.read_text().replace('8234FF10','82A3DEA0'))
            self.assertTrue(p.verify_entry(root,0x82A3DEA0)['registered'])

    def test_conditional_tail_profile(self):
        self.assertEqual(p.profile_fields('conditional-tail'),(0x826A9EC8,32,'8b4df364b42994f970049966b3a8c5db4528bc3c6a18c3f7cd2a78b35d0501a7'))

    def test_conditional_tail_exact_hint(self):
        code=bytes.fromhex('814301087c6b1b7880630080554900c22b030000912b01084d9a00204801fa3c')
        with patch.object(p,'BASE',0x826A9EC8):
            self.assertEqual(p.verify_hint(code,'[functions.0x826A9EC8]\nsize=32','conditional-tail')['size'],32)

    def test_conditional_tail_no_truncation(self):
        with self.assertRaisesRegex(ValueError,'hint'):
            p.verify_hint(b'','[functions.0x826A9EC8]\nsize=28','conditional-tail')

    def test_conditional_tail_wrong_bytes(self):
        with self.assertRaisesRegex(ValueError,'range hash'):
            p.verify_hint(bytes(32),'[functions.0x826A9EC8]\nsize=32','conditional-tail')

    def test_conditional_tail_registration(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            for path in root.iterdir():path.write_text(path.read_text().replace('8234FF10','826A9EC8'))
            self.assertTrue(p.verify_entry(root,0x826A9EC8)['registered'])

    def test_bitfield_profile_range(self):
        self.assertEqual(p.profile_fields('bitfield-leaf'),(0x82AC2810,32,'9174c77a101ea25e91a9fb0f1b8c9c7e512c4b7fdc7d80af0ce39fbfbe311f6a'))

    def test_bitfield_exact_hint(self):
        code=bytes.fromhex('81630020556abffe556bc7fe2b0a0000616300024c9a0020556307fa4e800020')
        with patch.object(p,'BASE',0x82AC2810):
            self.assertEqual(p.verify_hint(code,'[functions.0x82AC2810]\nsize=32','bitfield-leaf')['size'],32)

    def test_bitfield_early_return_truncation_rejected(self):
        with self.assertRaisesRegex(ValueError,'hint'):
            p.verify_hint(b'','[functions.0x82AC2810]\nsize=24','bitfield-leaf')

    def test_bitfield_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError,'range hash'):
            p.verify_hint(bytes(32),'[functions.0x82AC2810]\nsize=32','bitfield-leaf')

    def test_bitfield_mapping(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            for path in root.iterdir():path.write_text(path.read_text().replace('8234FF10','82AC2810'))
            self.assertTrue(p.verify_entry(root,0x82AC2810)['registered'])

    def test_float_leaf_profile_range(self):
        self.assertEqual(p.profile_fields('float-leaf'),(0x82AC1DE8,20,'579d0af704a9e2c35ba6dc55ffe769344f780cf91ddc302e77aa72da6071ab53'))

    def test_float_leaf_exact_hint(self):
        code=bytes.fromhex('c0030030d0040000c0030034d00500004e800020')
        with patch.object(p,'BASE',0x82AC1DE8):
            self.assertEqual(p.verify_hint(code,'[functions.0x82AC1DE8]\nsize=20','float-leaf')['size'],20)

    def test_float_leaf_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError,'range hash'):
            p.verify_hint(bytes(20),'[functions.0x82AC1DE8]\nsize=20','float-leaf')

    def test_float_leaf_size_rejected(self):
        with self.assertRaisesRegex(ValueError,'hint'):
            p.verify_hint(b'','[functions.0x82AC1DE8]\nsize=24','float-leaf')

    def test_float_leaf_real_registration(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            for path in root.iterdir():path.write_text(path.read_text().replace('8234FF10','82AC1DE8'))
            self.assertTrue(p.verify_entry(root,0x82AC1DE8)['registered'])

    def test_extended_profile_range(self):
        self.assertEqual(p.profile_fields('extended-native'),(0x82517D70,0x2C,'b628e1746cfef4cd7c8340ad46cddaaf9fe16e6a083111c11983d7e43c6ce471'))

    def test_extended_wrong_hint(self):
        with self.assertRaisesRegex(ValueError,'hint'):
            p.verify_hint(b'','[functions.0x82517D70]\nsize=0x30','extended-native')

    def test_extended_generated_registration(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            for path in root.iterdir():path.write_text(path.read_text().replace('8234FF10','82517D70'))
            self.assertTrue(p.verify_entry(root,0x82517D70)['registered'])

    def test_gateway_profile_range(self):
        self.assertEqual(p.profile_fields('native-gateway'),(0x82509380,0x18,'24858452f74ebfe37c65055b81249f2b52a972d7f8374451f2b260775436bad2'))

    def test_gateway_wrong_hint(self):
        with self.assertRaisesRegex(ValueError,'hint'):
            p.verify_hint(b'','[functions.0x82509380]\nsize=0x1C','native-gateway')

    def test_gateway_generated_registration(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            for path in root.iterdir():path.write_text(path.read_text().replace('8234FF10','82509380'))
            self.assertTrue(p.verify_entry(root,0x82509380)['registered'])

    def test_compare_profile_range(self):
        entry,size,digest=p.profile_fields('compare')
        self.assertEqual((entry,size),(0x82C1C1A0,0x88))
        self.assertEqual(digest,'60e3229fb7c29acb4ca50ea10e03bf77af7d9e361a9882d12b2f8e7e9ad3388f')

    def test_compare_wrong_hint(self):
        with self.assertRaisesRegex(ValueError,'hint'):
            p.verify_hint(b'','[functions.0x82C1C1A0]\nsize=0x74','compare')

    def test_compare_generated_registration(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            for path in root.iterdir():path.write_text(path.read_text().replace('8234FF10','82C1C1A0'))
            self.assertTrue(p.verify_entry(root,0x82C1C1A0)['registered'])

    def test_virtual_thunk_profile_range(self):
        code=bytes.fromhex('81630000814b000c7d4903a64e800420')
        with patch.object(p,'BASE',0x823C2740):
            self.assertEqual(p.verify_hint(code,'[functions.0x823C2740]\nsize=0x10','virtual-thunk')['size'],16)

    def test_virtual_thunk_wrong_hint(self):
        with self.assertRaisesRegex(ValueError,'hint'):
            p.verify_hint(b'','[functions.0x823C2740]\nsize=0x14','virtual-thunk')

    def test_unknown_profile(self):
        with self.assertRaisesRegex(ValueError,'profile'):p.profile_fields('unverified')

    def test_virtual_thunk_generated_registration(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            for path in root.iterdir():path.write_text(path.read_text().replace('8234FF10','823C2740'))
            self.assertTrue(p.verify_entry(root,0x823C2740)['registered'])

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
