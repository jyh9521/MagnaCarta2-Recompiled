"""Read-only UE3 446/25 cooked UFunction metadata and conservative token reader."""
from __future__ import annotations
from collections import Counter, OrderedDict
import argparse, hashlib, json, math, struct
from pathlib import Path
try:
    from .ue3 import Reader, FormatError, LzxDecoder, parse_summary, parse_tables
except ImportError:
    from ue3 import Reader, FormatError, LzxDecoder, parse_summary, parse_tables

class PackageRanges:
    """Decode intersecting blocks only; bounded LRU, never a full logical package."""
    def __init__(self, data, summary, decoder):
        self.data, self.s, self.decoder = data, summary, decoder
        self.blocks=[]; self.cache=OrderedDict(); self.decoded_blocks=0
        self.logical_size=max([len(data)]+[c['uncompressed_offset']+c['uncompressed_size'] for c in summary['compressed_chunks']])
        if summary['compression_flags'] not in (0,4): raise FormatError('unsupported compression flags')
        for c in summary['compressed_chunks']:
            r=Reader(data); r.seek(c['compressed_offset'])
            if r.u32()!=0x9e2a83c1: raise FormatError('invalid chunk magic')
            bs,tc,tu=r.u32(),r.u32(),r.u32()
            if not 0<bs<=16*1024*1024 or tu!=c['uncompressed_size']: raise FormatError('invalid chunk sizes')
            blocks=[(r.u32(),r.u32()) for _ in range(math.ceil(tu/bs))]
            if sum(a for a,b in blocks)!=tc or sum(b for a,b in blocks)!=tu: raise FormatError('block totals mismatch')
            if r.pos+tc!=c['compressed_offset']+c['compressed_size']: raise FormatError('physical chunk mismatch')
            lo=c['uncompressed_offset']; physical=r.pos
            for comp,uncomp in blocks:
                if not 0<uncomp<=bs: raise FormatError('invalid block output')
                self.blocks.append((lo,lo+uncomp,physical,comp));lo+=uncomp;physical+=comp
    def read(self, offset, size):
        if offset<0 or size<0 or offset+size>self.logical_size: raise FormatError('logical range outside package')
        if not self.blocks: return self.data[offset:offset+size]
        end=offset+size; out=bytearray(); pos=offset
        first=self.blocks[0][0]
        if pos<first:
            n=min(end,first);out.extend(self.data[pos:n]);pos=n
        for i,(lo,hi,physical,comp) in enumerate(self.blocks):
            if hi<=pos or lo>=end: continue
            if lo>pos: raise FormatError('gap in logical range')
            if i not in self.cache:
                if self.decoder is None: raise FormatError('LZX decoder required')
                value=self.decoder(self.data[physical:physical+comp],hi-lo)
                if len(value)!=hi-lo: raise FormatError('decoder output size mismatch')
                self.cache[i]=value;self.decoded_blocks+=1
                while len(self.cache)>4:self.cache.popitem(last=False)
            self.cache.move_to_end(i);n=min(end,hi);out.extend(self.cache[i][pos-lo:n-lo]);pos=n
        if pos!=end: raise FormatError('logical range incomplete')
        return bytes(out)


def parse_function(data, names, import_count, export_count):
    """446/25 observed uncooked-metadata profile. No heuristic tail scanning."""
    r=Reader(data)
    def ref():
        v=r.i32()
        if not -import_count<=v<=export_count: raise FormatError('invalid function object reference')
        return v
    def name():
        i,n=r.u32(),r.u32()
        if i>=len(names):raise FormatError('invalid function name reference')
        return names[i] if not n else f'{names[i]}_{n-1}'
    result={'net_index':r.i32()}
    if name()!='None':raise FormatError('unsupported nonempty function property stream')
    for field in ('super','next','script_text','children','cpp_text'):result[field]=ref()
    result['line']=r.i32();result['text_pos']=r.i32()
    size=r.count(16*1024*1024);result['script_size']=size;result['script_offset']=r.pos
    script=r.read(size)
    result['script_sha256']=hashlib.sha256(script).hexdigest()
    result['native_index']=int.from_bytes(r.read(2),'big');result['operator_precedence']=r.read(1)[0]
    result['function_flags']=r.u32();result['is_native']=bool(result['function_flags']&0x400)
    if result['function_flags']&0x40:result['rep_offset']=int.from_bytes(r.read(2),'big')
    result['friendly_name']=name()
    if r.pos!=len(data):raise FormatError(f'function trailing bytes: {len(data)-r.pos}')
    if result['native_index'] and not result['is_native']:raise FormatError('native index without FUNC_Native')
    return result,script


class BytecodeReader:
    """Token framing only, not a VM, decompiler, or semantic validation."""
    def __init__(self, data, names, import_count, export_count):
        self.r=Reader(data); self.names=names;self.import_count=import_count;self.export_count=export_count
        self.calls=[];self.tokens=Counter();self.boundaries=[]
    def ref(self):
        v=self.r.i32()
        if not -self.import_count<=v<=self.export_count:raise FormatError('bytecode object reference outside tables')
        return v
    def name(self):
        i,n=self.r.u32(),self.r.u32()
        if i>=len(self.names):raise FormatError('bytecode name outside table')
        return self.names[i] if not n else f'{self.names[i]}_{n-1}'
    def u16(self):return int.from_bytes(self.r.read(2),'big')
    def params(self,depth):
        while True:
            t=self.expr(depth+1)
            if t==0x16:break
            if t in (0x53,0x15):raise FormatError('unterminated call parameter list')
    def expr(self,depth=0):
        if depth>128:raise FormatError('bytecode expression depth exceeds limit')
        start=self.r.pos;t=self.r.read(1)[0];self.boundaries.append(start);self.tokens[f'{t:02x}']+=1
        if t==0x53 and depth:raise FormatError('EndOfScript inside expression')
        def ex():
            value=self.expr(depth+1)
            if value in (0x15,0x16):raise FormatError('unexpected expression delimiter')
            return value
        def many(n):
            for _ in range(n):ex()
        if t>=0x60:
            index=t if t>=0x70 else ((t-0x60)<<8)|self.r.read(1)[0]
            self.calls.append({'offset':start,'kind':'native-index','native_index':index});self.params(depth)
        elif t in (0x00,0x01,0x02,0x29,0x48,0x20,0x0e,0x3a):self.ref()
        elif t in (0x08,0x0b,0x15,0x16,0x17,0x25,0x26,0x27,0x28,0x2a,0x30,0x31,0x3f,0x4a,0x50,0x53):pass
        elif t in (0x04,0x0d,0x2d,0x36,0x51):ex()
        elif t in (0x0f,0x10,0x14,0x1a,0x44):many(2)
        elif t in (0x1d,0x1e):self.r.read(4)
        elif t in (0x22,0x23):self.r.read(12)
        elif t in (0x24,0x2c):self.r.read(1)
        elif t in (0x21,0x43,0x4b):self.name()
        elif t in (0x1b,0x37):
            name=self.name();self.calls.append({'offset':start,'kind':'virtual-name' if t==0x1b else 'global-name','name':name});self.params(depth)
        elif t==0x1c:
            target=self.ref();self.calls.append({'offset':start,'kind':'final-object','target':target});self.params(depth)
        elif t==0x42:
            self.r.read(1);target=self.ref();name=self.name();self.calls.append({'offset':start,'kind':'delegate','target':target,'name':name});self.params(depth)
        elif t in (0x1f,0x34):
            unit=2 if t==0x34 else 1
            while any(self.r.read(unit)):pass
        elif t==0x06:self.u16()
        elif t in (0x07,0x18):self.u16();ex()
        elif t==0x09:self.r.read(3);ex()
        elif t==0x05:self.r.read(1);ex()
        elif t==0x0a:
            if self.u16()!=0xffff:ex()
        elif t==0x0c:
            while True:
                name=self.name();self.r.read(4)
                if name=='None':break
        elif t==0x11:many(5)
        elif t in (0x12,0x19):ex();self.r.read(3);ex()
        elif t in (0x13,0x2e,0x52):self.ref();ex()
        elif t==0x2f:ex();self.u16()
        elif t in (0x32,0x33):self.ref();many(2)
        elif t==0x35:self.ref();self.ref();self.r.read(2);ex()
        elif t==0x38:self.r.read(1);ex()
        elif t in (0x39,0x40):many(3)
        elif t in (0x3b,0x3c,0x3d,0x3e):
            many(2)
            if self.expr(depth+1)!=0x16:raise FormatError('delegate comparison missing EndFunctionParms')
        elif t==0x41:self.r.read(13)
        elif t==0x45:ex();self.u16();ex();self.u16();ex()
        elif t in (0x46,0x47):ex();self.u16();ex()
        elif t==0x49:
            self.u16();ex()
            if self.expr(depth+1)!=0x15:raise FormatError('default parameter missing EndParmValue')
        elif t in (0x54,0x55,0x56):many(2)
        elif t==0x57:many(3)
        elif t==0x58:many(2);self.r.read(1);ex();self.u16()
        else:raise FormatError(f'unsupported token 0x{t:02x} at {start}')
        return t
    def run(self):
        error=None
        try:
            while self.r.pos<len(self.r.data):
                t=self.expr()
                if t in (0x15,0x16):raise FormatError('unexpected top-level expression delimiter')
                if t==0x53 and self.r.pos!=len(self.r.data):raise FormatError('bytes after EndOfScript')
            if self.r.data and (not self.boundaries or self.r.data[self.boundaries[-1]]!=0x53):raise FormatError('missing terminal EndOfScript')
        except FormatError as exc:error=str(exc)
        return {'status':'error' if error else 'framing-validated','error':error,'consumed':self.r.pos,'size':len(self.r.data),'token_counts':dict(self.tokens),'calls':self.calls}


PACKAGES=('Core','Engine','GameFramework','IpDrv','MC2Game','OnlineSubsystemLive','UnrealScriptTest')
def analyze_iso(iso, inventory, decoder):
    inv=json.loads(inventory.read_text(encoding='utf-8'))
    if not isinstance(inv,dict) or inv.get('schema_version')!=1 or inv.get('errors')!=[] or not isinstance(inv.get('files'),list) or any(not isinstance(e,dict) for e in inv['files']):raise FormatError('invalid inventory schema/errors')
    roots=[e for e in inv['files'] if e.get('type')=='xdvdfs']
    if len(roots)!=1 or roots[0]['offset']!=0 or roots[0]['size']!=iso.stat().st_size or roots[0]['path']!=iso.name:raise FormatError('inventory root mismatch')
    selected=[e for e in inv['files'] if isinstance(e.get('path'),str) and any(e['path'].endswith('/'+p+'.xxx') for p in PACKAGES)]
    if Counter(Path(e['path']).stem for e in selected)!=Counter(PACKAGES):raise FormatError('expected exactly seven definition packages')
    for e in selected:
        if e.get('type')!='unreal-package-candidate' or type(e.get('offset')) is not int or type(e.get('size')) is not int or not isinstance(e.get('sha256'),str) or len(e['sha256'])!=64:raise FormatError('invalid member metadata')
    result={'schema_version':1,'profile':'UE3-446-25-preserved-script-metadata','packages':[],'functions':[]}
    with iso.open('rb') as f:
        for e in selected:
            if not e['path'].startswith(iso.name+'::') or not 0<=e['offset']<e['offset']+e['size']<=iso.stat().st_size or e['size']>256*1024*1024:raise FormatError('invalid member range/identity')
            f.seek(e['offset']);data=f.read(e['size'])
            if len(data)!=e['size'] or hashlib.sha256(data).hexdigest()!=e['sha256']:raise FormatError('inventory hash mismatch')
            s=parse_summary(data,len(data))
            if s['byte_order']!='big':raise FormatError('UFunction profile requires big-endian UE3 446/25')
            rr=PackageRanges(data,s,decoder)
            table=parse_tables(rr.read(0,s['header_size']),s,rr.logical_size)
            rows=[]
            for i,obj in enumerate(table['exports'],1):
                if obj['class_path']!='Core.Function':continue
                row={'package':Path(e['path']).name,'package_sha256':e['sha256'],'export':i,'path':obj['path'],'serial_offset':obj['serial_offset'],'serial_size':obj['serial_size']}
                try:
                    payload=rr.read(obj['serial_offset'],obj['serial_size'])
                    row['payload_sha256']=hashlib.sha256(payload).hexdigest()
                    meta,script=parse_function(payload,table['names'],len(table['imports']),len(table['exports']));row.update(meta);row['metadata_status']='validated'
                    row['bytecode']=BytecodeReader(script,table['names'],len(table['imports']),len(table['exports'])).run()
                    for call in row['bytecode']['calls']:
                        if call['kind']=='final-object':
                            target=call['target'];dest=table['exports'][target-1] if target>0 else table['imports'][-target-1] if target else None
                            call['target_path']=dest['path'] if dest else None
                            call['target_class']=dest.get('class_path',dest.get('class_name',{}).get('name')) if dest else None
                except FormatError as exc:row['metadata_status']='error';row['error']=str(exc)
                rows.append(row)
            if not rows:raise FormatError('definition package contains no Function exports')
            local_functions={r['export']:r for r in rows}
            for row in rows:
                for call in row.get('bytecode',{}).get('calls',[]):
                    if call['kind']=='final-object':
                        target=local_functions.get(call['target'])
                        call['binding_status']=('native-declaration-no-implementation' if target.get('is_native') else 'script-declaration-not-executed') if target and target.get('metadata_status')=='validated' else 'external-or-unresolved-function'
            result['functions'].extend(rows)
            result['packages'].append({'path':e['path'].split('::',1)[1],'sha256':e['sha256'],'functions':len(rows),'decoded_blocks':rr.decoded_blocks,'logical_bytes':rr.logical_size})
    byindex={}
    for row in result['functions']:
        if row.get('is_native') and row['native_index']:byindex.setdefault(row['native_index'],[]).append(row['package']+'.'+row['path'])
    qualified={r['package'][:-4]+'.'+r['path']:r for r in result['functions']}
    calls=Counter();unresolved=Counter();tokenerrors=Counter()
    for row in result['functions']:
        bc=row.get('bytecode',{})
        if bc.get('error'):tokenerrors[bc['error'].split(' at ')[0]]+=1
        for call in bc.get('calls',[]):
            calls[call['kind']]+=1
            call['evidence']='complete-token-stream' if bc['status']=='framing-validated' else 'validated-prefix-in-incomplete-stream'
            if call['kind']=='final-object' and call['target']<0:
                target=qualified.get(call['target_path'])
                if target and target.get('metadata_status')=='validated':
                    call['resolved_package']=target['package']
                    call['binding_status']='native-declaration-no-implementation' if target['is_native'] else 'script-declaration-not-executed'
            if call['kind']=='native-index':
                call['declaration_candidates']=byindex.get(call['native_index'],[])
                call['binding_status']='declaration-only-no-implementation' if call['declaration_candidates'] else 'unresolved-native-registration'
                if not call['declaration_candidates']:unresolved[str(call['native_index'])]+=1
    rows=result['functions'];native=[r for r in rows if r.get('is_native')]
    result['summary']={'functions':len(rows),'metadata_statuses':dict(Counter(r['metadata_status'] for r in rows)),'bytecode_statuses':dict(Counter(r.get('bytecode',{}).get('status','not-read') for r in rows)),'native_declarations':len(native),'indexed_native_declarations':sum(bool(r['native_index']) for r in native),'name_registered_native_declarations':sum(not r['native_index'] for r in native),'unique_native_indices':len(byindex),'script_bytes':sum(r.get('script_size',0) for r in rows),'call_kinds':dict(calls),'final_binding_statuses':dict(Counter(c['binding_status'] for r in rows for c in r.get('bytecode',{}).get('calls',[]) if c['kind']=='final-object')),'unresolved_native_indices':dict(unresolved),'bytecode_error_classes':dict(tokenerrors),'compatible_native_implementations':0,'runtime_execution':'not-tested'}
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('iso',type=Path);p.add_argument('inventory',type=Path);p.add_argument('--lzx-library',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    if a.output.resolve() in (a.iso.resolve(),a.inventory.resolve(),a.lzx_library.resolve()) or (a.output.exists() and any(a.output.samefile(i) for i in (a.iso,a.inventory,a.lzx_library))):p.error('output must differ from inputs')
    try:
        report=analyze_iso(a.iso,a.inventory,LzxDecoder(a.lzx_library));a.output.parent.mkdir(parents=True,exist_ok=True)
        import os,tempfile
        fd,tmp=tempfile.mkstemp(dir=a.output.parent,prefix=a.output.name+'.')
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=True,separators=(',',':'));f.write('\n')
            os.replace(tmp,a.output)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        print(json.dumps(report['summary'],sort_keys=True));return int(report['summary']['metadata_statuses'].get('error',0)>0 or report['summary']['bytecode_statuses'].get('error',0)>0)
    except (OSError,ValueError,KeyError) as exc:print(f'ERROR: {exc}');return 1
if __name__=='__main__':raise SystemExit(main())
