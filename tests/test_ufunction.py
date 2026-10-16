"""Synthetic, redistribution-neutral UFunction framing fixtures."""
import hashlib
import struct
import unittest
import tempfile
import json
from pathlib import Path
from tools.formats.ufunction import analyze_iso
from tools.formats.ufunction import BytecodeReader, FormatError, PackageRanges, parse_function

NAMES=['None','Example','Property']
def u32(n):return struct.pack('>I',n)
def ref(n):return struct.pack('>i',n)
def fname(n):return u32(n)+u32(0)
def fixture(script=b'\x53',native=0,flags=0):
    return ref(1)+fname(0)+ref(0)*5+ref(10)+ref(20)+u32(len(script))+script+struct.pack('>HB I',native,0,flags)+(b'\0\7' if flags&0x40 else b'')+fname(1)
def scan(b):return BytecodeReader(b,NAMES,3,10).run()

class FunctionMetadataTests(unittest.TestCase):
    def test_script_fields_and_hash(self):
        m,b=parse_function(fixture(),NAMES,3,10)
        self.assertEqual(b,b'\x53');self.assertEqual(m['script_offset'],44)
        self.assertEqual(m['script_sha256'],hashlib.sha256(b).hexdigest())
        self.assertEqual((m['line'],m['text_pos'],m['friendly_name']),(10,20,'Example'))
    def test_indexed_native(self):
        m,_=parse_function(fixture(native=129,flags=0x400),NAMES,3,10)
        self.assertTrue(m['is_native']);self.assertEqual(m['native_index'],129)
    def test_zero_index_native_is_native(self):
        m,_=parse_function(fixture(flags=0x400),NAMES,3,10)
        self.assertTrue(m['is_native']);self.assertEqual(m['native_index'],0)
    def test_network_rep_offset(self):
        m,_=parse_function(fixture(flags=0x40),NAMES,3,10);self.assertEqual(m['rep_offset'],7)
    def test_every_truncation_rejected(self):
        b=fixture()
        for n in range(len(b)):
            with self.subTest(n=n),self.assertRaises(FormatError):parse_function(b[:n],NAMES,3,10)
    def test_tail_rejected(self):
        with self.assertRaises(FormatError):parse_function(fixture()+b'X',NAMES,3,10)
    def test_nonempty_properties_rejected(self):
        b=bytearray(fixture());b[4:8]=u32(2)
        with self.assertRaisesRegex(FormatError,'property stream'):parse_function(b,NAMES,3,10)
    def test_invalid_ref_rejected(self):
        b=bytearray(fixture());b[12:16]=ref(11)
        with self.assertRaisesRegex(FormatError,'reference'):parse_function(b,NAMES,3,10)
    def test_native_flag_mismatch(self):
        with self.assertRaisesRegex(FormatError,'FUNC_Native'):parse_function(fixture(native=1),NAMES,3,10)
    def test_invalid_name_rejected(self):
        b=bytearray(fixture());b[-8:-4]=u32(999)
        with self.assertRaisesRegex(FormatError,'name reference'):parse_function(b,NAMES,3,10)

class BytecodeTests(unittest.TestCase):
    def test_direct_native(self):
        r=scan(b'\x81\x25\x16\x53');self.assertEqual(r['status'],'framing-validated');self.assertEqual(r['calls'][0]['native_index'],129)
    def test_extended_native(self):
        r=scan(b'\x61\x23\x16\x53');self.assertEqual(r['calls'][0]['native_index'],291)
    def test_final_call(self):
        r=scan(b'\x1c'+ref(2)+b'\x16\x53');self.assertEqual(r['calls'][0]['target'],2)
    def test_virtual_call(self):
        r=scan(b'\x1b'+fname(1)+b'\x16\x53');self.assertEqual(r['calls'][0]['name'],'Example')
    def test_native_byte_in_constant_not_call(self):
        r=scan(b'\x1d\x81\x81\x81\x81\x53');self.assertEqual(r['calls'],[])
    def test_nested_call(self):
        r=scan(b'\x81\x82\x16\x16\x53');self.assertEqual(len(r['calls']),2)
    def test_unknown_stops_not_skip(self):
        r=scan(b'\x03\x81\x16\x53');self.assertEqual(r['status'],'error');self.assertEqual(r['calls'],[]);self.assertIn('unsupported token',r['error'])
    def test_invalid_ref(self):self.assertEqual(scan(b'\x00'+ref(11)+b'\x53')['status'],'error')
    def test_invalid_name(self):self.assertEqual(scan(b'\x21'+fname(88)+b'\x53')['status'],'error')
    def test_missing_end(self):self.assertEqual(scan(b'\x25')['status'],'error')
    def test_top_level_endfunctionparms_rejected(self):
        self.assertEqual(scan(b'\x16\x53')['status'],'error')
    def test_top_level_endparmvalue_rejected(self):
        self.assertEqual(scan(b'\x15\x53')['status'],'error')
    def test_trailing_end(self):self.assertEqual(scan(b'\x53\x53')['status'],'error')
    def test_unterminated_call(self):self.assertEqual(scan(b'\x81\x53')['status'],'error')
    def test_depth_limit(self):self.assertEqual(scan(b'\x2d'*130+b'\x25\x53')['status'],'error')
    def test_empty(self):self.assertEqual(scan(b'')['status'],'framing-validated')
    def test_conditional(self):self.assertEqual(scan(b'\x45\x27\0\1\x25\0\1\x26\x53')['status'],'framing-validated')
    def test_context(self):self.assertEqual(scan(b'\x19\x17\0\1\0\x25\x53')['status'],'framing-validated')
    def test_find_446_has_no_endparms(self):
        r=scan(b'\x46\x00'+ref(1)+b'\0\1\x25\x53');self.assertEqual(r['status'],'framing-validated')
    def test_string_literal_is_not_tokens(self):
        self.assertEqual(scan(b'\x1f\x81\x81\0\x53')['calls'],[])
    def test_truncated_string(self):self.assertEqual(scan(b'\x1fABC')['status'],'error')
    def test_delegate_comparison_terminator(self):
        self.assertEqual(scan(b'\x3c\x00'+ref(1)+b'\x3f\x16\x53')['status'],'framing-validated')
    def test_nested_endofscript_rejected(self):
        self.assertEqual(scan(b'\x2d\x53')['status'],'error')
    def test_default_parameter_terminator(self):
        self.assertEqual(scan(b'\x49\0\1\x25\x15\x53')['status'],'framing-validated')
        self.assertEqual(scan(b'\x49\0\1\x25\x26\x53')['status'],'error')
    def test_struct_member(self):self.assertEqual(scan(b'\x35'+ref(1)+ref(2)+b'\0\0\x17\x53')['status'],'framing-validated')

class RangeTests(unittest.TestCase):
    def test_plain_range(self):
        r=PackageRanges(b'abcdef',{'compression_flags':0,'compressed_chunks':[]},None)
        self.assertEqual(r.read(1,3),b'bcd')
    def test_plain_invalid(self):
        r=PackageRanges(b'abcdef',{'compression_flags':0,'compressed_chunks':[]},None)
        for offset,size in [(-1,1),(0,-1),(6,1)]:
            with self.assertRaises(FormatError):r.read(offset,size)
    def test_block_crossing_and_cache(self):
        # fake compressor: two 3-byte blocks, identity decompressor.
        chunk=u32(0x9e2a83c1)+u32(3)+u32(6)+u32(6)+u32(3)+u32(3)+u32(3)+u32(3)+b'abcdef'
        s={'compression_flags':4,'compressed_chunks':[{'uncompressed_offset':4,'uncompressed_size':6,'compressed_offset':4,'compressed_size':len(chunk)}]}
        calls=[]
        r=PackageRanges(b'HEAD'+chunk,s,lambda d,n:(calls.append((d,n)) or d))
        self.assertEqual(r.read(2,6),b'ADabcd');self.assertEqual(r.read(5,3),b'bcd');self.assertEqual(len(calls),2)
    def test_decoder_output_mismatch(self):
        chunk=u32(0x9e2a83c1)+u32(3)+u32(3)+u32(3)+u32(3)+u32(3)+b'abc'
        s={'compression_flags':4,'compressed_chunks':[{'uncompressed_offset':4,'uncompressed_size':3,'compressed_offset':4,'compressed_size':len(chunk)}]}
        r=PackageRanges(b'HEAD'+chunk,s,lambda d,n:b'')
        with self.assertRaisesRegex(FormatError,'output size'):r.read(4,1)



class InventoryTests(unittest.TestCase):
    def check_definition_profile(self, endian, regex):
        from tools.formats.ufunction import PACKAGES
        pack=lambda *n:struct.pack(endian+'I'*len(n),*n)
        magic=b'\x9e\x2a\x83\xc1' if endian=='>' else b'\xc1\x83\x2a\x9e'
        payload=magic+pack((25<<16)|446,89)+pack(5)+b'None\0'+pack(0,0,0,0,0,0,0,0)+b'\0'*16+pack(0,3004,42,0,0)
        self.assertEqual(len(payload),89)
        with tempfile.TemporaryDirectory() as td:
            iso=Path(td)/'sample.iso';iso.write_bytes(payload*7)
            root={'type':'xdvdfs','offset':0,'size':iso.stat().st_size,'path':iso.name}
            rows=[{'type':'unreal-package-candidate','offset':i*89,'size':89,'path':iso.name+'::Cooked/'+name+'.xxx','sha256':hashlib.sha256(payload).hexdigest()} for i,name in enumerate(PACKAGES)]
            inventory=Path(td)/'inventory.json'
            inventory.write_text(json.dumps({'schema_version':1,'errors':[],'files':[root]+rows}),encoding='utf-8')
            with self.assertRaisesRegex(FormatError,regex):analyze_iso(iso,inventory,None)
    def test_little_endian_profile_rejected_in_actual_chain(self):
        self.check_definition_profile('<','requires big-endian')
    def test_empty_definition_package_rejected_in_actual_chain(self):
        self.check_definition_profile('>','no Function exports')
    def check_inventory(self, value, regex):
        with tempfile.TemporaryDirectory() as td:
            iso=Path(td)/'sample.iso';iso.write_bytes(b'1234')
            inventory=Path(td)/'inventory.json';inventory.write_text(json.dumps(value),encoding='utf-8')
            with self.assertRaisesRegex(FormatError,regex):analyze_iso(iso,inventory,None)
    def test_invalid_document(self):self.check_inventory([], 'schema')
    def test_errors_rejected(self):self.check_inventory({'schema_version':1,'errors':['error'],'files':[]},'schema')
    def test_nonobject_row(self):self.check_inventory({'schema_version':1,'errors':[],'files':[1]},'schema')
    def test_root_mismatch(self):self.check_inventory({'schema_version':1,'errors':[],'files':[{'type':'xdvdfs','offset':0,'size':9,'path':'sample.iso'}]},'root')
    def test_duplicate_definition_packages(self):
        root={'type':'xdvdfs','offset':0,'size':4,'path':'sample.iso'}
        rows=[{'path':'sample.iso::Core.xxx'}]*7
        self.check_inventory({'schema_version':1,'errors':[],'files':[root]+rows},'seven')

if __name__=='__main__':unittest.main()
