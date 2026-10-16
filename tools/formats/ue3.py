"""Read-only UE3 446/25 package table reader; never deserializes object payloads."""
from __future__ import annotations
import argparse
import ctypes
import math
import os
import tempfile
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import struct

TOOL_VERSION = "0.2.0"
class FormatError(ValueError):
    pass

class Reader:
    def __init__(self, data: bytes, endian: str = ">", unicode_endian: str | None = None):
        self.data, self.pos, self.endian = data, 0, endian
        self.unicode_endian = unicode_endian or endian
    def read(self, n: int) -> bytes:
        if n < 0 or self.pos + n > len(self.data):
            raise FormatError(f"range outside buffer at {self.pos}: {n}")
        b = self.data[self.pos:self.pos+n]; self.pos += n
        return b
    def u32(self): return struct.unpack(self.endian + "I", self.read(4))[0]
    def i32(self): return struct.unpack(self.endian + "i", self.read(4))[0]
    def count(self, limit=1_000_000):
        n = self.i32()
        if not 0 <= n <= limit: raise FormatError(f"invalid count: {n}")
        return n
    def string(self):
        n = self.i32()
        if abs(n) > 1_048_576: raise FormatError(f"invalid string length: {n}")
        if not n: return ""
        raw = self.read(abs(n) * (2 if n < 0 else 1))
        term = b"\0\0" if n < 0 else b"\0"
        if not raw.endswith(term): raise FormatError("unterminated FString")
        try: return raw[:-len(term)].decode(("utf-16-be" if self.unicode_endian == ">" else "utf-16-le") if n < 0 else "utf-8")
        except UnicodeError as exc: raise FormatError(f"invalid FString encoding: {exc}") from exc
    def seek(self, offset):
        if not 0 <= offset <= len(self.data): raise FormatError(f"invalid offset: {offset}")
        self.pos = offset

def parse_summary(data: bytes, file_size: int | None = None):
    """Parse the supported profile only; offsets remain logical when compressed."""
    magic = data[:4]
    if magic not in (b"\x9e\x2a\x83\xc1", b"\xc1\x83\x2a\x9e"):
        raise FormatError("not a UE package magic")
    r = Reader(data, ">" if magic[0] == 0x9e else "<"); r.read(4)
    word = r.u32(); version, licensee = word & 0xffff, word >> 16
    if (version, licensee) != (446, 25):
        raise FormatError(f"unsupported serialization profile: {version}/{licensee}")
    out = {"version":version,"licensee_version":licensee,"byte_order":"big" if r.endian==">" else "little"}
    out["header_size"] = r.u32(); out["package_group"] = r.string(); out["package_flags"] = r.u32()
    for label in ("name", "export", "import"):
        out[label+"_count"] = r.count(); out[label+"_offset"] = r.u32()
    out["depends_offset"] = r.u32(); out["guid"] = r.read(16).hex()
    out["generations"] = [{"export_count":r.count(),"name_count":r.count(),"net_object_count":r.count()} for _ in range(r.count(1024))]
    out["engine_version"] = r.u32(); out["cooker_version"] = r.u32(); out["compression_flags"] = r.u32()
    out["compressed_chunks"] = []
    physical_end = r.pos + 4
    previous_end = 0
    for _ in range(r.count(65536)):
        c = dict(zip(("uncompressed_offset","uncompressed_size","compressed_offset","compressed_size"), [r.u32() for _ in range(4)]))
        if not c["uncompressed_size"] or not c["compressed_size"]: raise FormatError("empty compressed chunk")
        if c["uncompressed_offset"] < previous_end: raise FormatError("overlapping or unordered logical chunks")
        previous_end = c["uncompressed_offset"] + c["uncompressed_size"]
        if file_size is not None and c["compressed_offset"] + c["compressed_size"] > file_size: raise FormatError("compressed chunk outside file")
        physical_end = max(physical_end, c["compressed_offset"]+c["compressed_size"])
        out["compressed_chunks"].append(c)
    out["summary_end"] = r.pos
    chunks = out["compressed_chunks"]
    if bool(chunks) != bool(out["compression_flags"]): raise FormatError("compression flags/chunks mismatch")
    logical_size = max([file_size or len(data)] + [c["uncompressed_offset"]+c["uncompressed_size"] for c in chunks])
    for label in ("name", "export", "import"):
        if out[label+"_count"] and not (r.pos-len(chunks)*16) <= out[label+"_offset"] < logical_size: raise FormatError(f"invalid {label} table offset")
    if not r.pos <= out["header_size"] <= logical_size: raise FormatError("invalid header size")
    return out

def parse_tables(data: bytes, summary=None, logical_size=None):
    s = summary or parse_summary(data, len(data))

    r = Reader(data, ">" if s["byte_order"] == "big" else "<", "<")
    r.seek(s["name_offset"]); names=[]
    for _ in range(s["name_count"]): names.append(r.string()); r.read(8)
    name_end = r.pos
    def fname():
        i, n = r.u32(), r.u32()
        if i >= len(names): raise FormatError(f"invalid FName index: {i}")
        return {"index":i,"number":n,"name":names[i] if not n else f"{names[i]}_{n-1}"}
    def ref():
        v = r.i32()
        if not -s["import_count"] <= v <= s["export_count"]: raise FormatError(f"invalid object reference: {v}")
        return v
    r.seek(s["import_offset"]); imports=[]
    for _ in range(s["import_count"]):
        imports.append({"class_package":fname(),"class_name":fname(),"outer":ref(),"object_name":fname()})
    import_end = r.pos
    r.seek(s["export_offset"]); exports=[]
    for _ in range(s["export_count"]):
        start=r.pos
        e={"class":ref(),"super":ref(),"outer":ref(),"object_name":fname(),"archetype":ref(),"object_flags":r.read(8).hex(),"serial_size":r.u32(),"serial_offset":r.u32()}
        if e["serial_size"] and (e["serial_offset"] < s["header_size"] or e["serial_offset"]+e["serial_size"]>(logical_size or len(data))): raise FormatError("export serial range outside package")
        e["components"]=[{"name":fname(),"object":ref()} for _ in range(r.count())]
        e["export_flags"]=r.u32(); e["net_object_counts"]=[r.count() for _ in range(r.count(65536))]; e["guid"]=r.read(16).hex()
        e["table_offset"]=start; exports.append(e)
    export_end = r.pos
    ranges=sorted((a,b,label) for a,b,label in ((s["name_offset"],name_end,"name"),(s["import_offset"],import_end,"import"),(s["export_offset"],export_end,"export")) if b>a)
    for i,(a,b,label) in enumerate(ranges):
        if b>s["header_size"]: raise FormatError(f"{label} table exceeds header")
        if i and a<ranges[i-1][1]: raise FormatError("overlapping tables")
    def path(index):
        seen=set(); parts=[]
        while index:
            if index in seen: raise FormatError("cyclic object outer")
            seen.add(index); obj=imports[-index-1] if index<0 else exports[index-1]
            parts.append(obj["object_name"]["name"]); index=obj["outer"]
        return ".".join(reversed(parts))
    for i,obj in enumerate(imports): obj["path"]=path(-i-1)
    for i,obj in enumerate(exports):
        obj["path"]=path(i+1); obj["class_path"]=path(obj["class"]) if obj["class"] else "Class"
    edges=[]
    for i,obj in enumerate(exports):
        for field in ("class","super","outer","archetype"):
            if obj[field]: edges.append({"source":i+1,"field":field,"target":obj[field]})
        for component in obj["components"]:
            if component["object"]: edges.append({"source":i+1,"field":"component","target":component["object"]})
    dependencies=sorted({i["path"].split(".")[0] for i in imports if i["class_name"]["name"]=="Package"})
    return {"names":names,"imports":imports,"exports":exports,"table_edges":edges,"package_dependencies":dependencies,"table_ends":{"name":name_end,"import":import_end,"export":export_end}}

def strip_lzx_frames(data: bytes) -> bytes:
    """Remove Xbox LZX framing (2-byte size or FF/u16 output/u16 input)."""
    r=Reader(data); out=bytearray()
    while r.pos<len(data):
        first=r.read(1)[0]
        if first==255:
            expected=int.from_bytes(r.read(2),"big"); size=int.from_bytes(r.read(2),"big")
            if not 1<=expected<=32768: raise FormatError("invalid LZX frame output size")
        else:
            size=(first<<8)|r.read(1)[0]
        if not size:
            if any(data[r.pos:]): raise FormatError("nonzero bytes after LZX terminator")
            break
        out.extend(r.read(size))
    return bytes(out)

class LzxDecoder:
    def __init__(self, library: Path):
        self.library=ctypes.CDLL(str(library.resolve()))
        self.function=self.library.ue3_lzx
        self.function.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_int]
        self.function.restype=ctypes.c_int
    def __call__(self, data, size):
        if not 0<size<=128*1024*1024: raise FormatError("LZX output size exceeds limit")
        raw=strip_lzx_frames(data); output=ctypes.create_string_buffer(size)
        result=self.function(raw,len(raw),output,size)
        if result: raise FormatError(f"libmspack LZX failed: {result}")
        return output.raw

def package_header(data, summary, decoder):
    """Recover only logical header chunks; object payloads are not returned."""
    if not summary["compression_flags"]: return data
    if summary["compression_flags"]!=4: raise FormatError("unsupported compression flags")
    if decoder is None: raise FormatError("LZX decoder not configured")
    size=summary["header_size"]
    if size>128*1024*1024: raise FormatError("header exceeds limit")
    out=bytearray(size); covered=0
    for c in summary["compressed_chunks"]:
        off=c["uncompressed_offset"]
        if off>=size: break
        if not covered:
            out[:off]=data[:off]; covered=off
        if off!=covered: raise FormatError("gap in compressed header chunks")
        r=Reader(data); r.seek(c["compressed_offset"])
        if r.u32()!=0x9e2a83c1: raise FormatError("invalid chunk magic")
        block_size,total_comp,total_uncomp=r.u32(),r.u32(),r.u32()
        if not 0<block_size<=16*1024*1024 or total_uncomp!=c["uncompressed_size"]: raise FormatError("invalid chunk sizes")
        blocks=[(r.u32(),r.u32()) for _ in range(math.ceil(total_uncomp/block_size))]
        if sum(v[0] for v in blocks)!=total_comp or sum(v[1] for v in blocks)!=total_uncomp: raise FormatError("compressed block totals mismatch")
        if r.pos+total_comp!=c["compressed_offset"]+c["compressed_size"]: raise FormatError("chunk physical size mismatch")
        for comp,uncomp in blocks:
            if not 0<uncomp<=block_size: raise FormatError("invalid block output size")
            if off<size:
                decoded=decoder(r.read(comp),uncomp)
                end=min(off+uncomp,size); out[off:end]=decoded[:end-off]
            else: r.read(comp)
            off+=uncomp
        covered=off
        if covered>=size: break
    if covered<size: raise FormatError("compressed header incomplete")
    return bytes(out)

def analyze_iso(iso:Path, inventory:Path, decoder=None, full_tables=False):
    inv=json.loads(inventory.read_text(encoding="utf-8"))
    if not isinstance(inv,dict): raise FormatError("invalid inventory document")
    if inv.get("schema_version")!=1 or not isinstance(inv.get("files"),list) or inv.get("errors")!=[]: raise FormatError("invalid or incomplete inventory")
    if any(not isinstance(e,dict) for e in inv["files"]): raise FormatError("invalid inventory row")
    roots=[e for e in inv["files"] if e.get("type")=="xdvdfs"]
    if len(roots)!=1 or roots[0].get("offset")!=0 or roots[0].get("size")!=iso.stat().st_size or roots[0].get("path")!=iso.name: raise FormatError("ISO size or inventory root identity mismatch")
    for e in inv["files"]:
        if e.get("type")!="unreal-package-candidate": continue
        if type(e.get("offset")) is not int or type(e.get("size")) is not int or e["offset"]<0 or e["size"]<=0 or e["offset"]+e["size"]>iso.stat().st_size or e["size"]>256*1024*1024: raise FormatError("inventory member outside ISO")
        if not isinstance(e.get("sha256"),str) or len(e["sha256"])!=64: raise FormatError("invalid inventory member hash")
        if not e.get("path", "").startswith(iso.name+"::"): raise FormatError("inventory member belongs to different ISO")
    rows=[]
    with iso.open("rb") as f:
        for e in inv["files"]:
            if e["type"]!="unreal-package-candidate": continue
            row={"path":e["path"].split("::",1)[-1],"sha256":e["sha256"],"size":e["size"]}
            try:
                f.seek(e["offset"]); data=f.read(e["size"])
                if len(data)!=e["size"] or hashlib.sha256(data).hexdigest()!=e["sha256"]: raise FormatError("inventory hash mismatch")
                s=parse_summary(data[:1_048_576],e["size"]); row["summary"]=s
                if s["compression_flags"] and decoder is None:
                    row["status"]="summary-only"; row["error"]=f"compression decoder required: flags={s['compression_flags']}"
                else:
                    header=package_header(data,s,decoder)
                    logical_size=max([e["size"]]+[c["uncompressed_offset"]+c["uncompressed_size"] for c in s["compressed_chunks"]])
                    t=parse_tables(header,s,logical_size)
                    row["names"]=t["names"]; row["imports"]=t["imports"]
                    row["package_dependencies"]=t["package_dependencies"]
                    row["table_ends"]=t["table_ends"]
                    row["class_histogram"]=dict(Counter(x["class_path"] for x in t["exports"]))
                    row["export_columns"]=["name_index","name_number","class","super","outer","archetype","flags_hex","serial_size","serial_offset","export_flags"]
                    row["exports"]=[[x["object_name"]["index"],x["object_name"]["number"],x["class"],x["super"],x["outer"],x["archetype"],x["object_flags"],x["serial_size"],x["serial_offset"],x["export_flags"]] for x in t["exports"]]
                    row["table_edges"]=[[x["source"],x["field"],x["target"]] for x in t["table_edges"]]
                    row["status"]="tables-validated"
            except (FormatError,OSError) as exc: row["status"]="error"; row["error"]=str(exc)
            rows.append(row)
    available={}
    for x in rows: available.setdefault(Path(x["path"]).stem.casefold(),[]).append(x["path"])
    edges=[]
    for row in rows:
        for dep in row.get("package_dependencies",[]):
            edges.append({"source":row["path"],"target_name":dep,"target_path":available.get(dep.casefold(),[None])[0] if len(available.get(dep.casefold(),[]))==1 else None,"candidate_paths":available.get(dep.casefold(),[]),"evidence":"root Package import; not runtime closure"})
    report = {"schema_version":1,"tool_version":TOOL_VERSION,"packages":rows,"package_edges":edges,"summary":{"packages":len(rows),"statuses":dict(Counter(x["status"] for x in rows)),"compression_flags":dict(Counter(str(x.get("summary",{}).get("compression_flags")) for x in rows)),"names":sum(len(x.get("names",[])) for x in rows),"imports":sum(len(x.get("imports",[])) for x in rows),"exports":sum(len(x.get("exports",[])) for x in rows),"table_edges":sum(len(x.get("table_edges",[])) for x in rows),"package_edges":len(edges),"resolved_package_edges":sum(e["target_path"] is not None for e in edges)}}
    classes=Counter()
    for row in rows: classes.update(row.get("class_histogram",{}))
    report["summary"]["class_histogram"]=dict(classes)
    report["summary"]["native_binding_status"]="not analyzed: UFunction/UClass payloads are not deserialized"
    report["summary"]["script_definition_candidates"]={k:v for k,v in classes.items() if k.split(".")[-1] in ("Class","Function","State","ScriptStruct")}
    report["summary"]["unresolved_package_names"]=sorted({e["target_name"] for e in edges if e["target_path"] is None})
    for row in rows:
        row["table_counts"]={k:len(row.get(k,[])) for k in ("names","imports","exports","table_edges")}
        if not full_tables:
            for k in ("names","imports","exports","table_edges"): row.pop(k,None)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("iso",type=Path); p.add_argument("inventory",type=Path); p.add_argument("--output",required=True,type=Path); p.add_argument("--lzx-library",type=Path); p.add_argument("--full-tables",action="store_true"); a=p.parse_args()
    if a.output.resolve() in (a.iso.resolve(),a.inventory.resolve()) or (a.output.exists() and any(a.output.samefile(i) for i in (a.iso,a.inventory))): p.error("output must differ from inputs")
    try:
        result=analyze_iso(a.iso,a.inventory,LzxDecoder(a.lzx_library) if a.lzx_library else None,a.full_tables)
        a.output.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix=a.output.name+".",dir=a.output.parent)
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as f: json.dump(result,f,ensure_ascii=True,separators=(",",":")); f.write("\n")
            os.replace(tmp,a.output)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
        print(json.dumps({k:v for k,v in result["summary"].items() if k not in ("class_histogram","unresolved_package_names")},sort_keys=True)); return int(result["summary"]["statuses"].get("error",0)>0)
    except (OSError,FormatError,ValueError,KeyError) as exc: print(f"ERROR: {exc}"); return 1
if __name__=="__main__": raise SystemExit(main())
