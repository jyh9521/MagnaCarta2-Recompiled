"""Original native61 suffix-dispatch oracle and isolated 256-input differential."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import struct
import subprocess

from tools.research.verify_branch_ranges import BASE,image_from_xex
from tools.research.verify_callback import sha,view
from tools.research.verify_thunk import sections_and_pdata
from tools.research.compile_module import digest,inventory,vc_environment
from tools.research.probe_route_a import CLANG_CL_SHA256

TARGET=0x82517D70
TABLE=0x83251180
MAPPING_SHA256='63fea05a382da874e1fb5827c37ab8fb92e877e663010d273f7066ffbe6217d2'
RANGES={TARGET:(44,'b628e1746cfef4cd7c8340ad46cddaaf9fe16e6a083111c11983d7e43c6ce471'),
        0x82E78008:(124,'fcc0646f0b0add7abd3448d87ce12ab8c2c2428d6f40494fac3597b31812680a'),
        0x8250820C:(36,'eaac439a745a9cd8b4cf40b5c0a70138174f311f8643bdd3a28ba58699253bba')}
WORDS=(0x8164000C,0x3D408325,0x394A0D80,0x392B0001,0x38EA0400,0x890B0000,
       0x9124000C,0x5506103E,0x7D66382E,0x7D6903A6,0x4E800420)


def signed16(value):return value-0x10000 if value&0x8000 else value


def execute(code,registers,memory,lr):
    """Execute only the exact 11-word original profile, byte-addressed fixture."""
    if len(code)!=44 or len(registers)!=32:raise ValueError('invalid extended native input')
    if struct.unpack('>11I',code)!=WORDS:raise ValueError('unknown extended native opcode/template')
    regs=[value&0xFFFFFFFFFFFFFFFF for value in registers];data=dict(memory);stores=[];ctr=0
    def read(address,size):
        if address<0 or address+size>0x100000000:raise ValueError('read range outside guest space')
        result=0
        for offset in range(size):
            value=data.get(address+offset)
            if type(value)!=int or not 0<=value<=255:raise ValueError('read outside byte fixture')
            result=(result<<8)|value
        return result
    for word in WORDS:
        op=word>>26;rt=(word>>21)&31;ra=(word>>16)&31;rb=(word>>11)&31;imm=signed16(word&0xFFFF)
        if op in (32,34):regs[rt]=read(((regs[ra]&0xFFFFFFFF)+imm)&0xFFFFFFFF,4 if op==32 else 1)
        elif op==15:regs[rt]=(imm<<16)&0xFFFFFFFFFFFFFFFF
        elif op==14:regs[rt]=(regs[ra]+imm)&0xFFFFFFFFFFFFFFFF
        elif op==36:
            address=((regs[ra]&0xFFFFFFFF)+imm)&0xFFFFFFFF
            read(address,4)  # Only explicitly supplied, in-range bytes are writable.
            value=regs[rt]&0xFFFFFFFF
            for offset,byte in enumerate(struct.pack('>I',value)):data[address+offset]=byte
            stores.append({'address':address,'value':value})
        elif op==21:regs[ra]=((regs[rt]&0xFFFFFFFF)<<rb | (regs[rt]&0xFFFFFFFF)>>(32-rb))&0xFFFFFFFF
        elif word==0x7D66382E:regs[rt]=read(((regs[ra]&0xFFFFFFFF)+(regs[rb]&0xFFFFFFFF))&0xFFFFFFFF,4)
        elif word==0x7D6903A6:ctr=regs[11]
        elif word==0x4E800420:return {'registers':regs,'ctr':ctr,'lr':lr,'dispatch':ctr,'memory':data,'stores':stores}
        else:raise ValueError('unsupported original word')
    raise ValueError('missing tail dispatch')


def put_word(memory,address,value):
    for offset,byte in enumerate(struct.pack('>I',value&0xFFFFFFFF)):memory[address+offset]=byte


def fixture(suffix):
    if type(suffix)!=int or not 0<=suffix<=255:raise ValueError('suffix must be one byte')
    frame=0x2000 if suffix%2==0 else 0xFFFEE000;cursor=0x6000+suffix
    target=0 if suffix==0 else 0xFFFFFFFF if suffix==255 else 0x82000000+suffix*0x100
    memory={cursor:suffix};put_word(memory,frame+12,cursor);put_word(memory,TABLE+suffix*4,target)
    regs=[0xABCD000000000000+(index<<16)+suffix for index in range(32)];regs[4]=0xF00D000000000000|frame
    return {'suffix':suffix,'frame':frame,'cursor':cursor,'target':target,'registers':regs,'lr':0x1122334455667788,'memory':memory}


def verify_original(image):
    for address,(size,expected) in RANGES.items():
        if sha(view(image,address,size))!=expected:raise ValueError('original extended-native witness mismatch')
    _,pdata=sections_and_pdata(image)
    if any(a<=TARGET<a+size for a,size in pdata):raise ValueError('unexpected containing PDATA')
    if struct.unpack('>I',view(image,0x8320BAD4,4))[0]!=TARGET:raise ValueError('original pointer mismatch')
    words=struct.unpack('>31I',view(image,0x82E78008,124))
    if words[22]&0xFFFF!=0x61 or words[25]!=0x91480184:raise ValueError('original native61 destination mismatch')
    return {'ranges':RANGES,'containing_pdata':False,'registration':{'entry':0x82E78008,'source':0x8320BAD4,'index':0x61,'destination':0x83250F04},
            'caller':{'bctrl':0x82508228,'lr':0x8250822C},'dispatch':'GNatives[0x100+suffix], not another selector table'}


def extract_body(directory):
    found=[]
    for path in sorted(Path(directory).glob('*.cpp')):
        text=path.read_text(encoding='utf-8-sig')
        for match in re.finditer(r'DEFINE_REX_FUNC\(sub_82517D70\) \{(.*?)\n\}',text,re.S):
            body=match[0]
            if 'REX_FATAL' in body or body.count('REX_CALL_INDIRECT_FUNC(')!=1 or body.count('REX_STORE_U32(')!=1:raise ValueError('unexpected generated native61 shape')
            found.append({'source':str(path.resolve()),'source_sha256':digest(path),'body':body,'body_sha256':sha(body.encode()),'line':text.count('\n',0,match.start())+1})
    if len(found)!=1:raise ValueError('expected one complete native61 body')
    mapping=(Path(directory)/'mc2_probe_init.cpp').read_text(encoding='utf-8-sig');registration=(Path(directory)/'mc2_probe_register.cpp').read_text(encoding='utf-8-sig')
    if re.findall(r'\{\s*0x82517D70,\s*(\w+)\s*\}',mapping)!=['sub_82517D70'] or re.findall(r'registrar->SetFunction\(0x82517D70,\s*(\w+)\);',registration)!=['sub_82517D70']:
        raise ValueError('expected one-to-one native61 mapping and registration')
    found[0]['registered']=True;return found[0]


def harness(body,code):
    expected=[execute(code,fixture(s)['registers'],fixture(s)['memory'],fixture(s)['lr']) for s in range(256)]
    text='#include "mc2_probe_pch.h"\n#include <windows.h>\n#include <cstdio>\n#include <cstring>\nstatic unsigned recorded=0;\n#undef REX_CALL_INDIRECT_FUNC\n#define REX_CALL_INDIRECT_FUNC(address) do { recorded=(address); } while(0)\n'+body
    text+='\nstatic const uint64_t expected_regs[256][32]={\n'
    text+=',\n'.join('{'+','.join(f'0x{value:016X}ull' for value in result['registers'])+'}' for result in expected)+'};\n'
    text+='int main(){uint8_t* base=static_cast<uint8_t*>(VirtualAlloc(nullptr,0x100000000ull,MEM_RESERVE,PAGE_NOACCESS));if(!base)return 2;const uint32_t guest_pages[]={0x2000,0x6000,0x83251000,0xFFFEE000};uint32_t pages[4];unsigned char before[4][4096];PPCContext ctx{};int failures=0;\n'
    text+='for(unsigned i=0;i<4;i++){pages[i]=guest_pages[i]+REX_PHYS_HOST_OFFSET(guest_pages[i]);if(VirtualAlloc(base+pages[i],4096,MEM_COMMIT,PAGE_READWRITE)!=base+pages[i]){VirtualFree(base,0,MEM_RELEASE);return 3;}}\n'
    text+='for(unsigned suffix=0;suffix<256;suffix++){ctx=PPCContext{};recorded=0;for(auto page:pages)for(unsigned i=0;i<4096;i++)base[page+i]=(i*17+suffix)%256;uint32_t frame=suffix%2?0xFFFEE000u:0x2000u,cursor=0x6000u+suffix;uint32_t target=suffix==0?0:suffix==255?0xFFFFFFFFu:0x82000000u+suffix*0x100u;REX_STORE_U32(frame+12,cursor);REX_STORE_U8(cursor,suffix);REX_STORE_U32(0x83251180u+suffix*4,target);\n'
    for index in range(32):text+=f'ctx.r{index}.u64=0xABCD000000000000ull+({index}ull<<16)+suffix;\n'
    text+='ctx.r4.u64=0xF00D000000000000ull|frame;ctx.lr=0x1122334455667788ull;ctx.ctr.u64=0xAABBCCDDEEFF0011ull;ctx.xer.ca=1;ctx.xer.so=1;ctx.xer.ov=1;\n'
    for index in range(8):text+=f'ctx.cr{index}.set_raw({index+1});\n'
    text+='for(unsigned i=0;i<4;i++)std::memcpy(before[i],base+pages[i],4096);uint32_t next=cursor+1;for(unsigned i=0;i<4;i++)before[suffix%2?3:0][12+i]=(next>>(24-i*8))&255;sub_82517D70(ctx,base);bool good=ctx.lr==0x1122334455667788ull && ctx.ctr.u64==target && recorded==target && ctx.xer.ca==1 && ctx.xer.so==1 && ctx.xer.ov==1;\n'
    for index in range(32):text+=f'good=good && ctx.r{index}.u64==expected_regs[suffix][{index}];\n'
    for index in range(8):text+=f'good=good && ctx.cr{index}.raw()=={index+1};\n'
    text+='for(unsigned i=0;i<4;i++)good=good && std::memcmp(before[i],base+pages[i],4096)==0;std::printf("EXTENDED_CASE %u suffix=%02X target=%08X cursor_delta=1 success=%d\\n",suffix,suffix,recorded,good?1:0);failures+=!good;}bool released=VirtualFree(base,0,MEM_RELEASE)!=0;std::printf("EXTENDED_MEMORY pages=4 released=%d\\n",released?1:0);return failures || !released?1:0;}\n'
    return text


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('xex','loader-source','mapping','output'):parser.add_argument('--'+name,type=Path,required=True)
    for name in ('generated','sdk','compiler','vcvars'):parser.add_argument('--'+name,type=Path)
    args=parser.parse_args(argv);bundle=(args.generated,args.sdk,args.compiler,args.vcvars)
    if any(bundle) and not all(bundle):raise ValueError('all toolchain options required')
    inputs=[args.xex,args.loader_source,args.mapping];hashes={str(p):digest(p) for p in inputs}
    if hashes[str(args.mapping)]!=MAPPING_SHA256:raise ValueError('unsupported baseline mapping')
    image=image_from_xex(args.xex.read_bytes(),args.loader_source);original=verify_original(image);code=view(image,TARGET,44)
    if re.search(r'\{\s*0x82517D70,',args.mapping.read_text(encoding='utf-8-sig')):raise ValueError('baseline unexpectedly maps native61')
    fixtures=[fixture(s) for s in range(256)];results=[execute(code,c['registers'],c['memory'],c['lr']) for c in fixtures]
    output=args.output.absolute();roots=[p.resolve() for p in inputs]+[p.resolve() for p in (args.generated,args.sdk) if p]
    if any(output==p or p in output.parents for p in roots):raise ValueError('output aliases input tree')
    output.mkdir(parents=True,exist_ok=False)
    report={'schema':1,'inputs':hashes,'image_sha256':sha(image),'original':original,'cases':fixtures,'oracle_results':results,'success':True,'generated_execution':'not-requested','scope':'pure synthetic sparse frame/script/dispatch table; actual title and runtime GNatives untouched'}
    try:
        if args.generated:
            if os.name!='nt' or digest(args.compiler)!=CLANG_CL_SHA256:raise ValueError('unsupported compiler/platform')
            trees=[args.generated,args.sdk/'include',args.compiler.resolve().parent.parent/'lib/clang/20/include'];witnesses=[inventory(p) for p in trees];compiler_hash=digest(args.compiler);vcvars_hash=digest(args.vcvars)
            body=extract_body(args.generated);source=output/'extended.cpp';exe=output/'extended.exe';source.write_text(harness(body['body'],code),encoding='utf-8')
            command=[str(args.compiler.resolve()),'/nologo','/Brepro','/std:c++latest','/utf-8','/O2','/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/EHa','/arch:AVX2','/bigobj','/MD','/I'+str((args.sdk/'include').resolve()),'/I'+str(args.generated.resolve()),str(source.resolve()),'/Fo'+str((output/'extended.obj').resolve()),'/Fe'+str(exe.resolve()),'/link','/Brepro']
            process=subprocess.run(command,cwd=output,env=vc_environment(args.vcvars.resolve()),capture_output=True,text=True,timeout=600);(output/'compile.txt').write_text(process.stdout+process.stderr,encoding='utf-8')
            report.update(generated=body,source_and_header_trees=witnesses,compile_command=command,compile_exit=process.returncode,success=False,compiler_sha256=compiler_hash,vcvars_sha256=vcvars_hash)
            if process.returncode==0:
                run=subprocess.run([str(exe.resolve())],cwd=output,capture_output=True,text=True,timeout=30)
                expected=''.join(f'EXTENDED_CASE {c["suffix"]} suffix={c["suffix"]:02X} target={c["target"]:08X} cursor_delta=1 success=1\n' for c in fixtures)+'EXTENDED_MEMORY pages=4 released=1\n';(output/'run.txt').write_text(run.stdout+run.stderr,encoding='utf-8')
                report.update(run_exit=run.returncode,literal_output=run.stdout,expected_output=expected,executable_sha256=digest(exe),success=run.returncode==0 and run.stdout==expected and not run.stderr)
            report['generated_execution']='all256 suffixes, original body and SDK memory macros, external dispatch RECORDED ONLY'
            if any(inventory(p)!=old for p,old in zip(trees,witnesses)) or digest(args.compiler)!=compiler_hash or digest(args.vcvars)!=vcvars_hash:raise ValueError('source/header/toolchain changed')
        report['inputs_unchanged']=all(digest(p)==hashes[str(p)] for p in inputs)
        if not report['inputs_unchanged']:raise ValueError('input changed')
    except Exception as error:report.update(success=False,error=f'{type(error).__name__}: {error}');raise
    finally:(output/'extended-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f'EXTENDED target=82517D70 suffixes=256 success={report["success"]}')
    return 0 if report['success'] else 1


if __name__=='__main__':raise SystemExit(main())
