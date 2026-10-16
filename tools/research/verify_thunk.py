"""Read-only virtual tail-thunk candidates and bounded generated dispatch probe."""
from __future__ import annotations
import argparse
from bisect import bisect_right
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess

from tools.research.verify_branch_ranges import BASE,image_from_xex
from tools.research.verify_callback import view,sha
from tools.research.compile_module import digest,inventory,vc_environment
from tools.research.probe_route_a import CLANG_CL_SHA256

TARGET=0x823C2740
TARGET_SHA256='0a315417a24fefd102c136c2b181f682cfa3b65422c9cbdaa146fd6caf719265'
MAPPING_SHA256='4eac8309956903d5d383f2d95abd1bbcb083d2386c12e74d277b38191a2b773b'


def thunk_offset(code):
    if len(code)!=16:raise ValueError('expected exactly four instructions')
    first,load,ctr,branch=struct.unpack('>4I',code)
    offset=load&0xFFFF
    if first!=0x81630000 or load&0xFFFF0000!=0x814B0000 or ctr!=0x7D4903A6 or branch!=0x4E800420 or offset>0x7FFC or offset%4:
        raise ValueError('unsupported virtual tail-thunk pattern')
    return offset


def execute_thunk(code,object_address,memory,lr):
    offset=thunk_offset(code)
    def read(address):
        if address not in memory:raise ValueError('read outside fixture')
        value=memory[address]
        if type(value)!=int or not 0<=value<=0xFFFFFFFF:raise ValueError('invalid big-endian word fixture')
        return value
    table=read(object_address&0xFFFFFFFF);target=read((table+offset)&0xFFFFFFFF)
    return {'r10':target,'r11':table,'ctr':target,'lr':lr,'dispatch':target,'memory':dict(memory)}


def sections_and_pdata(image):
    if len(image)<64 or image[:2]!=b'MZ':raise ValueError('invalid DOS image')
    pe=struct.unpack_from('<I',image,0x3C)[0]
    header=view(image,BASE+pe,24)
    if header[:4]!=b'PE\0\0':raise ValueError('invalid PE image')
    count=struct.unpack_from('<H',header,6)[0];optional=struct.unpack_from('<H',header,20)[0]
    optional_data=view(image,BASE+pe+24,optional)
    if len(optional_data)<128 or struct.unpack_from('<H',optional_data)[0]!=0x10B:raise ValueError('expected PE32 directories')
    sections=[]
    for index in range(count):
        row=view(image,BASE+pe+24+optional+index*40,40)
        size,rva=struct.unpack_from('<II',row,8);flags=struct.unpack_from('<I',row,36)[0]
        name=row[:8].rstrip(b'\0').decode('ascii','strict')
        # Discardable relocation/debug suffixes are not loaded scan inputs.
        if flags&0x2000000:continue
        view(image,BASE+rva,size)
        sections.append({'name':name,'start':BASE+rva,'end':BASE+rva+size,'flags':flags})
    rva,size=struct.unpack_from('<II',optional_data,96+24)
    if size%8:raise ValueError('invalid PDATA size')
    pdata=sorted((start,((fields>>8)&0x3FFFFF)*4) for start,fields in struct.iter_unpack('>II',view(image,BASE+rva,size)))
    return sections,pdata


def terminal(word):
    return word in (0x4E800020,0x4E800420) or (word>>26==18 and not word&1)


def scan_candidates(image,sections,pdata,mapped,base=BASE):
    code=[s for s in sections if s['flags']&0x20000000]
    # Exclude .pdata: an exception record isn't an independent object/vtable use.
    data=[s for s in sections if s['flags']&0x40000000 and not s['flags']&0xA2000000 and s['name']!='.pdata']
    xrefs={}
    for section in data:
        for address in range((section['start']+3)&~3,section['end']-3,4):
            value=struct.unpack('>I',view(image,address,4,base))[0]
            xrefs.setdefault(value,[]).append(address)
    starts=[row[0] for row in pdata];result=[]
    for section in code:
        for address in range((section['start']+3)&~3,section['end']-15,4):
            if address in mapped or address not in xrefs:continue
            blob=view(image,address,16,base)
            try:offset=thunk_offset(blob)
            except ValueError:continue
            containing=None;index=bisect_right(starts,address)-1
            if index>=0 and pdata[index][0]<=address<pdata[index][0]+pdata[index][1]:containing=pdata[index]
            if containing and (containing[0]!=address or containing[1]!=16):continue
            previous=struct.unpack('>I',view(image,address-4,4,base))[0] if address>=section['start']+4 else None
            if not containing and (previous is None or not terminal(previous)):continue
            result.append({'address':address,'size':16,'slot_offset':offset,'sha256':sha(blob),
                           'code_section':section['name'],'readonly_pointer_references':xrefs[address],
                           'boundary_witness':{'pdata':containing,'preceding_terminal':None if previous is None else f'{previous:08X}'},
                           'mapping_present':False,'status':'static candidate only; not executed, no automatic hint'})
    return result


def extract_body(directory):
    found=[]
    for path in sorted(Path(directory).glob('*.cpp')):
        text=path.read_text(encoding='utf-8-sig')
        for match in re.finditer(r'DEFINE_REX_FUNC\(sub_823C2740\) \{(.*?)\n\}',text,re.S):
            body=match[0]
            if 'REX_FATAL' in body or body.count('REX_CALL_INDIRECT_FUNC(')!=1 or body.count('REX_LOAD_U32(')!=2 or 'REX_STORE_' in body:
                raise ValueError('unexpected generated thunk shape')
            found.append({'source':str(path.resolve()),'source_sha256':digest(path),'body':body,'body_sha256':sha(body.encode()),'line':text.count('\n',0,match.start())+1})
    if len(found)!=1:raise ValueError('expected one generated thunk')
    return found[0]


def cases():
    return [(0x100,0x200,0x12345678),(0x180,0x300,0),(0x400,0x800,0xFFFFFFFF),(0xF00,0xF40,0x8234FF10)]


def harness(body,original_code):
    text='#include "mc2_probe_pch.h"\n#include <cstdio>\n#include <cstring>\nstatic unsigned recorded=0;\n#undef REX_CALL_INDIRECT_FUNC\n#define REX_CALL_INDIRECT_FUNC(address) do { recorded=(address); } while(0)\n'+body+'\nint main(){alignas(32) unsigned char memory[4096],before[4096];uint8_t* base=memory;PPCContext ctx{};int failures=0;\n'
    for number,(obj,table,target) in enumerate(cases()):
        expected=execute_thunk(original_code,obj,{obj:table,table+12:target},0x1122334455667788)
        if expected['dispatch']!=target:raise ValueError('fixture differs from original oracle')
        text+='{for(unsigned i=0;i<4096;i++)memory[i]=(i*17+3)%256;ctx=PPCContext{};recorded=0;\n'
        text+=f'ctx.r3.u64={obj};ctx.lr=0x1122334455667788ull;REX_STORE_U32({obj},{table});REX_STORE_U32({table+12},0x{target:08X}u);std::memcpy(before,memory,4096);sub_823C2740(ctx,base);\n'
        text+=f'bool good=recorded==0x{target:08X}u && ctx.r10.u64==0x{target:08X}u && ctx.r11.u64=={table} && ctx.ctr.u64==0x{target:08X}u && ctx.lr==0x1122334455667788ull && ctx.r3.u64=={obj} && std::memcmp(memory,before,4096)==0;std::printf("THUNK_CASE {number} target={target:08X} recorded=%08X success=%d\\n",recorded,good?1:0);failures+=!good;}}\n'
    return text+'return failures?1:0;}\n'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('xex','loader-source','mapping','output'):parser.add_argument('--'+name,type=Path,required=True)
    for name in ('generated','sdk','compiler','vcvars'):parser.add_argument('--'+name,type=Path)
    args=parser.parse_args(argv);bundle=(args.generated,args.sdk,args.compiler,args.vcvars)
    if any(bundle) and not all(bundle):raise ValueError('all generated-probe toolchain options required')
    inputs=[args.xex,args.loader_source,args.mapping];hashes={str(p):digest(p) for p in inputs}
    if hashes[str(args.mapping)]!=MAPPING_SHA256:raise ValueError('unsupported baseline mapping witness')
    image=image_from_xex(args.xex.read_bytes(),args.loader_source)
    if sha(view(image,TARGET,16))!=TARGET_SHA256:raise ValueError('original thunk mismatch')
    caller_sha=sha(view(image,0x828C5040,36))
    if caller_sha!='a9c656532f0b547cdbb05fab15482739bdaa258d1ae01da061a018030cd89086':raise ValueError('original caller mismatch')
    mapped={int(v,16) for v in re.findall(r'\{\s*0x([A-Fa-f0-9]+),\s*\w+\s*\}',args.mapping.read_text(encoding='utf-8-sig'))}
    if len(mapped)<58000:raise ValueError('incomplete baseline mapping')
    sections,pdata=sections_and_pdata(image);candidates=scan_candidates(image,sections,pdata,mapped)
    if TARGET not in {r['address'] for r in candidates}:raise ValueError('observed target missing from static candidates')
    output=args.output.absolute()
    roots=[p.resolve() for p in inputs]+[p.resolve() for p in (args.generated,args.sdk) if p]
    if any(output==p or p in output.parents for p in roots):raise ValueError('output aliases input tree')
    output.mkdir(parents=True,exist_ok=False)
    report={'schema':1,'inputs':hashes,'image_sha256':sha(image),'candidates':candidates,'candidate_count':len(candidates),
            'target':TARGET,'success':True,'generated_execution':'not-requested','scope':'exact register-template virtual tail-thunks; candidates are unexecuted, no automatic hints'}
    report['caller_witness']={'address':0x828C5040,'size':36,'sha256':caller_sha,'bctrl':0x828C5060,'return_lr':0x828C5064,'input_slot_offset':8,'thunk_output_slot_offset':12}
    report['oracle_fixtures']=[execute_thunk(view(image,TARGET,16),obj,{obj:table,table+12:target},0x1122334455667788) for obj,table,target in cases()]
    try:
        if args.generated:
            if os.name!='nt' or digest(args.compiler)!=CLANG_CL_SHA256:raise ValueError('unsupported compiler/platform')
            trees=[args.generated,args.sdk/'include',args.compiler.resolve().parent.parent/'lib/clang/20/include'];witnesses=[inventory(p) for p in trees]
            compiler_hash=digest(args.compiler);vcvars_hash=digest(args.vcvars)
            generated=extract_body(args.generated);source=output/'thunk.cpp';exe=output/'thunk.exe';source.write_text(harness(generated['body'],view(image,TARGET,16)),encoding='utf-8')
            command=[str(args.compiler.resolve()),'/nologo','/Brepro','/std:c++latest','/utf-8','/O2','/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/EHa','/arch:AVX2','/bigobj','/MD','/I'+str((args.sdk/'include').resolve()),'/I'+str(args.generated.resolve()),str(source.resolve()),'/Fo'+str((output/'thunk.obj').resolve()),'/Fe'+str(exe.resolve()),'/link','/Brepro']
            process=subprocess.run(command,cwd=output,env=vc_environment(args.vcvars.resolve()),capture_output=True,text=True,timeout=600)
            (output/'compile.txt').write_text(process.stdout+process.stderr,encoding='utf-8')
            report.update(generated=generated,source_and_header_trees=witnesses,compile_command=command,compile_exit=process.returncode,success=False,compiler_sha256=compiler_hash,vcvars_sha256=vcvars_hash,harness_sha256=digest(source))
            if process.returncode==0:
                run=subprocess.run([str(exe.resolve())],cwd=output,capture_output=True,text=True,timeout=30)
                expected=''.join(f'THUNK_CASE {n} target={target:08X} recorded={target:08X} success=1\n' for n,(_,_,target) in enumerate(cases()))
                (output/'run.txt').write_text(run.stdout+run.stderr,encoding='utf-8')
                report.update(run_exit=run.returncode,literal_output=run.stdout,expected_output=expected,executable_sha256=digest(exe),success=run.returncode==0 and run.stdout==expected and not run.stderr)
            report['generated_execution']='external dispatch recorded only; unknown callee NOT EXECUTED'
            if any(inventory(p)!=old for p,old in zip(trees,witnesses)) or digest(args.compiler)!=compiler_hash or digest(args.vcvars)!=vcvars_hash:raise ValueError('source/header/toolchain input changed')
        report['inputs_unchanged']=all(digest(p)==hashes[str(p)] for p in inputs)
        if not report['inputs_unchanged']:raise ValueError('input changed')
    except Exception as error:
        report.update(success=False,error=f'{type(error).__name__}: {error}');raise
    finally:(output/'thunk-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f'THUNK target=823C2740 candidates={len(candidates)} cases={4 if args.generated else 0} success={report["success"]}')
    return 0 if report['success'] else 1


if __name__=='__main__':raise SystemExit(main())
