"""Synthetic fixtures only: no proprietary game resources."""
import copy
import struct
import unittest
from tools.formats.ue3 import FormatError, Reader, parse_summary, parse_tables, strip_lzx_frames, package_header

def fixture(endian=">"):
    pack=lambda *v:struct.pack(endian+"I"*len(v),*v)
    string=lambda s:pack(len(s)+1)+s.encode()+b"\0"
    names=["Core","Package","Class","Thing","Object"]
    name_table=b"".join(string(s)+b"\0"*8 for s in names)
    fname=lambda i:pack(i,0)
    imports=fname(0)+fname(1)+pack(0)+fname(0)+fname(0)+fname(2)+pack(0xffffffff)+fname(3)
    header_size=101+len(name_table)+len(imports)+68
    exports=pack(0xfffffffe,0,0)+fname(4)+pack(0)+b"\0"*8+pack(4,header_size,0,0,0)+b"\0"*16
    magic=b"\x9e\x2a\x83\xc1" if endian==">" else b"\xc1\x83\x2a\x9e"
    head=magic+pack((25<<16)|446,header_size)+string("None")+pack(0,len(names),101,1,101+len(name_table)+len(imports),2,101+len(name_table),0)+b"\0"*16+pack(1,1,len(names),0,3004,42,0,0)
    assert len(head)==101 and len(exports)==68
    return head+name_table+imports+exports+b"DATA"

class UE3Tests(unittest.TestCase):
    def test_big_tables_and_edges(self):
        data=fixture();t=parse_tables(data)
        self.assertEqual(t["package_dependencies"],["Core"])
        self.assertEqual(t["exports"][0]["class_path"],"Core.Thing")
        self.assertEqual(t["table_edges"],[{"source":1,"field":"class","target":-2}])
    def test_little_endian(self): self.assertEqual(parse_tables(fixture("<"))["names"][3],"Thing")
    def test_version_guard(self):
        d=bytearray(fixture());struct.pack_into(">I",d,4,447)
        with self.assertRaisesRegex(FormatError,"unsupported"):parse_summary(d)
    def test_magic(self):
        with self.assertRaises(FormatError):parse_summary(b"xxxx")
    def test_truncated_summary(self):
        for n in range(4,101):
            with self.subTest(n=n),self.assertRaises(FormatError):parse_summary(fixture()[:n])
    def test_truncated_name(self):
        with self.assertRaises(FormatError):parse_tables(fixture()[:110])
    def test_invalid_name_reference(self):
        d=bytearray(fixture());s=parse_summary(d);struct.pack_into(">I",d,s["import_offset"],999)
        with self.assertRaisesRegex(FormatError,"FName"):parse_tables(d)
    def test_bad_serial_range(self):
        d=bytearray(fixture());s=parse_summary(d);struct.pack_into(">I",d,s["export_offset"]+36,0xfffffff0)
        with self.assertRaisesRegex(FormatError,"serial range"):parse_tables(d)
    def test_cycle(self):
        d=bytearray(fixture());s=parse_summary(d);struct.pack_into(">i",d,s["import_offset"]+16,-1)
        with self.assertRaisesRegex(FormatError,"cyclic"):parse_tables(d)
    def test_object_reference(self):
        d=bytearray(fixture());s=parse_summary(d);struct.pack_into(">i",d,s["export_offset"],-3)
        with self.assertRaisesRegex(FormatError,"object reference"):parse_tables(d)
    def test_invalid_count(self):
        with self.assertRaises(FormatError):Reader(b"\xff"*4).count()
    def test_fstring_unicode(self): self.assertEqual(Reader(struct.pack(">i",-2)+"字\0".encode("utf-16-be")).string(),"字")
    def test_fstring_termination(self):
        with self.assertRaisesRegex(FormatError,"unterminated"):Reader(b"\0\0\0\x02xx").string()
    def test_fstring_utf8_guard(self):
        with self.assertRaisesRegex(FormatError,"encoding"):Reader(b"\0\0\0\x02\xff\0").string()
    def test_frames(self): self.assertEqual(strip_lzx_frames(b"\0\x03abc\xff\0\x02\0\x02de\0\0"),b"abcde")
    def test_frame_truncated(self):
        with self.assertRaises(FormatError):strip_lzx_frames(b"\0\x03a")
    def test_frame_bad_terminal(self):
        with self.assertRaises(FormatError):strip_lzx_frames(b"\0\0x")
    def test_frame_bad_size(self):
        with self.assertRaises(FormatError):strip_lzx_frames(b"\xff\0\0\0\x01x")
    def test_uncompressed_header(self):
        d=fixture();self.assertEqual(package_header(d,parse_summary(d),None),d)
    def test_compressed_without_decoder(self):
        s=copy.deepcopy(parse_summary(fixture()));s["compression_flags"]=4
        with self.assertRaisesRegex(FormatError,"not configured"):package_header(fixture(),s,None)
    def test_compressed_profile_guard(self):
        s=copy.deepcopy(parse_summary(fixture()));s["compression_flags"]=2
        with self.assertRaises(FormatError):package_header(fixture(),s,None)
    def test_overlap_tables(self):
        d=fixture();s=parse_summary(d);s["header_size"]=s["export_offset"]
        with self.assertRaises(FormatError):parse_tables(d,s)
if __name__=="__main__":unittest.main()

class UE3IntegrationTests(unittest.TestCase):
    def test_xbox_unicode_endian(self):
        self.assertEqual(Reader(struct.pack(">i",-2)+"字\0".encode("utf-16-le"),">","<").string(),"字")
    def make(self,root):
        import hashlib
        iso=root/"disc.iso";data=fixture();iso.write_bytes(data)
        return iso,{"schema_version":1,"errors":[],"files":[{"type":"xdvdfs","path":iso.name,"size":len(data),"offset":0},{"type":"unreal-package-candidate","path":iso.name+"::test.xxx","size":len(data),"offset":0,"sha256":hashlib.sha256(data).hexdigest()}]}
    def test_manifest(self):
        from pathlib import Path
        import json,tempfile
        from tools.formats.ue3 import analyze_iso
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);iso,inv=self.make(root);m=root/"i.json";m.write_text(json.dumps(inv));r=analyze_iso(iso,m)
            self.assertEqual(r["summary"]["statuses"],{"tables-validated":1});self.assertEqual(r["summary"]["exports"],1);self.assertNotIn("exports",r["packages"][0])
    def test_manifest_guards(self):
        from pathlib import Path
        import json,tempfile
        from tools.formats.ue3 import analyze_iso
        for bad in ("schema","errors","root_missing","root_path","root_size","negative_offset","negative_size","outside","wrong_member_path","bad_hash"):
            with self.subTest(bad=bad),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);iso,inv=self.make(root);e=inv["files"][1]
                if bad=="schema":inv["schema_version"]=999
                if bad=="errors":inv["errors"]=["incomplete"]
                if bad=="root_missing":inv["files"].pop(0)
                if bad=="root_path":inv["files"][0]["path"]="wrong.iso"
                if bad=="root_size":inv["files"][0]["size"]+=1
                if bad=="negative_offset":e["offset"]=-1
                if bad=="negative_size":e["size"]=-1
                if bad=="outside":e["offset"]=1
                if bad=="wrong_member_path":e["path"]="wrong.iso::test.xxx"
                if bad=="bad_hash":e["sha256"]="x"
                m=root/"i.json";m.write_text(json.dumps(inv))
                with self.assertRaises(FormatError):analyze_iso(iso,m)
    def test_hash_guard(self):
        from pathlib import Path
        import json,tempfile
        from tools.formats.ue3 import analyze_iso
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);iso,inv=self.make(root);inv["files"][1]["sha256"]="0"*64;m=root/"i.json";m.write_text(json.dumps(inv));r=analyze_iso(iso,m)
            self.assertEqual(r["summary"]["statuses"],{"error":1});self.assertEqual(r["packages"][0]["error"],"inventory hash mismatch")

    def test_summary_table_overlap(self):
        d=bytearray(fixture());struct.pack_into(">II",d,25,1,53);struct.pack_into(">I",d,33,0);struct.pack_into(">I",d,41,0)
        with self.assertRaisesRegex(FormatError,"table offset"):parse_summary(d)

    def test_invalid_inventory_rows(self):
        from pathlib import Path
        import json,tempfile
        from tools.formats.ue3 import analyze_iso
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);iso,_=self.make(root);m=root/"i.json"
            for value in ([],{"schema_version":1,"errors":[],"files":[None]}):
                m.write_text(json.dumps(value))
                with self.assertRaises(FormatError):analyze_iso(iso,m)
