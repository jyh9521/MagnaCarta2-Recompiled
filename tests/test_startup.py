"""Synthetic-only bounded startup parser tests, without original assets."""
import struct
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import tools.research.analyze_startup as startup
from tools.research.analyze_startup import direct_calls, pointer_table, pe_entry, view, main, generated_entry_witness


class StartupTests(unittest.TestCase):
    def test_relative_forward_call(self):
        self.assertEqual(direct_calls(struct.pack('>I',0x48000011),0x1000),
                         [{'site':0x1000,'target':0x1010}])

    def test_relative_backward_call(self):
        self.assertEqual(direct_calls(struct.pack('>I',0x4BFFFFF1),0x1000)[0]['target'],0xFF0)

    def test_absolute_call(self):
        self.assertEqual(direct_calls(struct.pack('>I',0x48001003),0x2000)[0]['target'],0x1000)

    def test_non_calls_are_not_edges(self):
        self.assertEqual(direct_calls(struct.pack('>III',0x48000010,0x4E800421,0x60000000),0),[])

    def test_bad_instruction_alignment(self):
        for data,address in ((b'123',0),(b'1234',1)):
            with self.assertRaises(ValueError):direct_calls(data,address)

    def test_table_preserves_order_and_duplicate_calls(self):
        image=struct.pack('>5I',0,0x1234,0xFFFFFFFF,0x5678,0x1234)
        result=pointer_table(image,0x1000,0x1014,{0x1234,0x5678},0x1000)
        self.assertEqual(result['slots'],5)
        self.assertEqual(result['pointers'],[{'slot':0x1004,'target':0x1234},
                         {'slot':0x100C,'target':0x5678},{'slot':0x1010,'target':0x1234}])

    def test_unknown_initializer_is_error(self):
        with self.assertRaisesRegex(ValueError,'generated boundary'):
            pointer_table(struct.pack('>I',0x1234),0,4,set(),0)

    def test_status_table_does_not_skip_minus_one(self):
        with self.assertRaises(ValueError):
            pointer_table(struct.pack('>I',0xFFFFFFFF),0,4,set(),0,False)

    def test_invalid_table_bounds(self):
        for start,end in ((1,4),(4,0),(0,8)):
            with self.assertRaises(ValueError):pointer_table(bytes(4),start,end,set(),0)

    def test_view_rejects_underflow_overflow_negative(self):
        for address,size in ((99,1),(104,1),(100,-1)):
            with self.assertRaises(ValueError):view(bytes(4),address,size,100)
        self.assertEqual(view(bytes(4),104,0,100),b'')

    def pe(self):
        data=bytearray(256);data[:2]=b'MZ';struct.pack_into('<I',data,0x3C,64)
        data[64:68]=b'PE\0\0';struct.pack_into('<H',data,88,0x10B)
        struct.pack_into('<I',data,104,128)
        return data

    def test_pe_entry_little_endian(self):
        self.assertEqual(pe_entry(self.pe(),0x1000),0x1080)

    def test_pe_bounds_magic_and_optional_magic(self):
        variants=[bytes(2)]
        for offset,value in ((0,b'ZZ'),(64,b'XX'),(88,b'\x0b\x02')):
            data=self.pe();data[offset:offset+len(value)]=value;variants.append(data)
        data=self.pe();struct.pack_into('<I',data,0x3C,255);variants.append(data)
        data=self.pe();struct.pack_into('<I',data,104,255);variants.append(data)
        for data in variants:
            with self.assertRaises(ValueError):pe_entry(data)

    def test_cli_rejects_output_alias_before_reading(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'input';p.write_bytes(b'fixture')
            args=[]
            for option in ('xex','loader-source','generated-register','generated-init','generated-entry','output'):
                args.extend(('--'+option,str(p)))
            with self.assertRaisesRegex(ValueError,'aliases'):main(args)

    def test_xstart_is_a_real_generated_body_not_a_replacement(self):
        text='DEFINE_REX_FUNC(xstart) {\n// bl 0x12345678\ncall();\n}'
        result=generated_entry_witness(text,[{'target':0x12345678}])
        self.assertTrue(result['direct_calls_match_original'])
        for bad in ('',text+text,text.replace('12345678','12345670')):
            with self.assertRaises(ValueError):generated_entry_witness(bad,[{'target':0x12345678}])

    def guarded_cli(self, directory, tampered_option):
        args=[]
        for option in ('xex','loader-source','generated-register','generated-init','generated-entry'):
            p=Path(directory)/option
            p.write_bytes(b'changed' if option==tampered_option else b'fixture')
            args.extend(('--'+option,str(p)))
        return args+['--output',str(Path(directory)/'output.json')]

    def test_cli_rejects_tampered_mapping_before_decoding(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(startup,'REGISTER_SHA256',startup.sha(b'fixture')), \
             patch.object(startup,'GENERATED_INIT_SHA256',startup.sha(b'fixture')), \
             patch.object(startup,'image_from_xex') as decode:
            with self.assertRaisesRegex(ValueError,'image-mapping witness'):
                main(self.guarded_cli(directory,'generated-init'))
            decode.assert_not_called()
            self.assertFalse((Path(directory)/'output.json').exists())

    def test_cli_rejects_tampered_entry_before_decoding(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(startup,'REGISTER_SHA256',startup.sha(b'fixture')), \
             patch.object(startup,'GENERATED_INIT_SHA256',startup.sha(b'fixture')), \
             patch.object(startup,'GENERATED_ENTRY_SHA256',startup.sha(b'fixture')), \
             patch.object(startup,'image_from_xex') as decode:
            with self.assertRaisesRegex(ValueError,'title-entry witness'):
                main(self.guarded_cli(directory,'generated-entry'))
            decode.assert_not_called()
            self.assertFalse((Path(directory)/'output.json').exists())


if __name__=='__main__':unittest.main()
