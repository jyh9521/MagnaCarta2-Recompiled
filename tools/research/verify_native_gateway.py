"""Original six-instruction gateway audit and synthetic sparse-memory differential."""
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

TARGET=0x82509380
SELECTOR=0x83250A98
GNATIVES=0x83250D80
MAPPING_SHA256='4eb5a1728751187fe72aa6e861be5db3cf8028dc9e8e818d80f217b6bd60f36b'
RANGES={TARGET:(24,'24858452f74ebfe37c65055b81249f2b52a972d7f8374451f2b260775436bad2'),
        0x82E710C8:(124,'3dd929abe42091fe2511c77947f3ead953f33ce0cf7239ec2c1c49adfa4e8eee'),
        0x82517828:(52,'0fcdc7103b8c4e01f9f7eeb59dc419bf34f3d2c1c01ea5aedbbad3162aa3c861')}


def execute(code,registers,memory,lr):
    """Exact finite six-word oracle; a tail dispatch is returned, never invoked."""
    if len(code)!=24 or len(registers)!=32:raise ValueError('invalid gateway input')
    expected=(0x3D608325,0x80640008,0x394B0980,0x812A0118,0x7D2903A6,0x4E800420)
    if struct.unpack('>6I',code)!=expected:raise ValueError('unknown gateway instruction/template')
    regs=[r&0xFFFFFFFFFFFFFFFF for r in registers];words=dict(memory)
    def read(address):
        if address not in words or type(words[address])!=int or not 0<=words[address]<=0xFFFFFFFF:
            raise ValueError('read outside big-endian word fixture')
        return words[address]
    regs[11]=0xFFFFFFFF83250000
    regs[3]=read(((regs[4]&0xFFFFFFFF)+8)&0xFFFFFFFF)
    regs[10]=0xFFFFFFFF83250980
    regs[9]=read(SELECTOR)
    return {'registers':regs,'ctr':regs[9],'lr':lr,'dispatch':regs[9],'memory':words}


def cases():
    specs=[(0x2000,0,0),(0x5000,0xFFFFFFFF,0xFFFFFFFF),(0x9000,0x12345678,0x8250BAF0),
           (0xFFFEE000,0x80000000,0x80000000)]
    result=[]
    for number,(frame,obj,target) in enumerate(specs):
        registers=[0xA1B2000000000000+index*0x1000101+number for index in range(32)]
        registers[4]=0xF00D000000000000|frame
        result.append({'frame':frame,'object_word':obj,'target':target,'registers':registers,
                       'lr':0x1122334455667788,'memory':{frame+8:obj,SELECTOR:target}})
    return result


def verify_original(image):
    for address,(size,expected) in RANGES.items():
        if sha(view(image,address,size))!=expected:raise ValueError(f'original gateway witness mismatch: {address:08X}')
    _,pdata=sections_and_pdata(image)
    if any(a<=TARGET<a+size for a,size in pdata):raise ValueError('unexpected containing PDATA')
    if struct.unpack('>I',view(image,0x8320B760,4))[0]!=TARGET:raise ValueError('original source slot mismatch')
    # The exact registration template loads this source slot and writes index52.
    words=struct.unpack('>31I',view(image,0x82E710C8,124))
    if words[22]&0xFFFF!=0x52 or words[25]!=0x91480148:raise ValueError('original registration slot mismatch')
    return {'ranges':RANGES,'containing_pdata':False,'registration':{'entry':0x82E710C8,'source':0x8320B760,'index':0x52,'destination':GNATIVES+0x52*4},
            'caller':{'entry_range':0x82517828,'bctrl':0x82517858,'lr':0x8251785C},
            'selector':{'base':0x83250980,'slot':0x46,'address':SELECTOR,'distinct_from_gnatives':True}}


def extract_body(directory):
    found=[]
    for path in sorted(Path(directory).glob('*.cpp')):
        text=path.read_text(encoding='utf-8-sig')
        for match in re.finditer(r'DEFINE_REX_FUNC\(sub_82509380\) \{(.*?)\n\}',text,re.S):
            body=match[0]
            if 'REX_FATAL' in body or 'REX_STORE_' in body or body.count('REX_CALL_INDIRECT_FUNC(')!=1 or body.count('REX_LOAD_U32(')!=2:
                raise ValueError('unexpected generated gateway shape')
            found.append({'source':str(path.resolve()),'source_sha256':digest(path),'body':body,'body_sha256':sha(body.encode()),'line':text.count('\n',0,match.start())+1})
    if len(found)!=1:raise ValueError('expected one complete generated gateway')
    mapping=(Path(directory)/'mc2_probe_init.cpp').read_text(encoding='utf-8-sig')
    if not re.search(r'\{\s*0x82509380,',mapping):raise ValueError('generated gateway mapping missing')
    register=(Path(directory)/'mc2_probe_register.cpp').read_text(encoding='utf-8-sig')
    found[0]['metadata']=verify_metadata(mapping,register)
    return found[0]


def verify_metadata(mapping,register):
    mappings=re.findall(r'\{\s*0x82509380,\s*(\w+)\s*\}',mapping)
    registrations=re.findall(r'registrar->SetFunction\(0x82509380,\s*(\w+)\);',register)
    if mappings!=['sub_82509380']:raise ValueError('expected exact one-to-one gateway image mapping')
    if registrations!=['sub_82509380']:raise ValueError('expected exact one-to-one gateway function registration')
    return {'image_mapping_count':1,'function_registration_count':1,'symbol':'sub_82509380'}


def harness(body,code):
    fixtures=cases();pages=sorted({SELECTOR&~0xFFF}|{case['frame']&~0xFFF for case in fixtures})
    text='#include "mc2_probe_pch.h"\n#include <windows.h>\n#include <cstdio>\n#include <cstring>\nstatic uint32_t recorded=0;\n#undef REX_CALL_INDIRECT_FUNC\n#define REX_CALL_INDIRECT_FUNC(address) do { recorded=(address); } while(0)\n'+body
    text+='\nint main(){uint8_t* base=static_cast<uint8_t*>(VirtualAlloc(nullptr,0x100000000ull,MEM_RESERVE,PAGE_NOACCESS));if(!base){std::puts("GATEWAY_RESERVE failed");return 2;}\n'
    text+='const uint32_t guest_pages[]={'+','.join(f'0x{page:08X}u' for page in pages)+'};uint32_t pages[sizeof(guest_pages)/sizeof(guest_pages[0])];for(unsigned i=0;i<sizeof(pages)/sizeof(pages[0]);i++)pages[i]=guest_pages[i]+REX_PHYS_HOST_OFFSET(guest_pages[i]);unsigned char before[sizeof(pages)/sizeof(pages[0])][4096];PPCContext ctx{};int failures=0;\n'
    text+='for(auto page:pages){if(VirtualAlloc(base+page,4096,MEM_COMMIT,PAGE_READWRITE)!=base+page){std::puts("GATEWAY_COMMIT failed");VirtualFree(base,0,MEM_RELEASE);return 3;}}\n'
    for number,case in enumerate(fixtures):
        expected=execute(code,case['registers'],case['memory'],case['lr'])
        # Leave the GNatives address span on the same committed page untouched.
        text+='{ctx=PPCContext{};recorded=0;for(auto page:pages)for(unsigned i=0;i<4096;i++)if(page!=0x83250000u || i<0xB00)base[page+i]=(i*17+7)%256;\n'
        for address,value in case['memory'].items():text+=f'REX_STORE_U32(0x{address:08X}u,0x{value:08X}u);\n'
        for index,value in enumerate(case['registers']):text+=f'ctx.r{index}.u64=0x{value:016X}ull;\n'
        text+=f'ctx.lr=0x{case["lr"]:016X}ull;ctx.ctr.u64=0x99AABBCCDDEEFF00ull;for(unsigned i=0;i<sizeof(pages)/sizeof(pages[0]);i++)std::memcpy(before[i],base+pages[i],4096);sub_82509380(ctx,base);bool good=ctx.lr==0x{case["lr"]:016X}ull && ctx.ctr.u64==0x{expected["ctr"]:016X}ull && recorded==0x{expected["dispatch"]:08X}u;\n'
        for index,value in enumerate(expected['registers']):text+=f'good=good && ctx.r{index}.u64==0x{value:016X}ull;\n'
        text+='for(unsigned i=0;i<sizeof(pages)/sizeof(pages[0]);i++)good=good && std::memcmp(before[i],base+pages[i],4096)==0;\n'
        text+=f'std::printf("GATEWAY_CASE {number} object=%08X target=%08X unchanged=%d success=%d\\n",ctx.r3.u32,recorded,good?1:0,good?1:0);failures+=!good;}}\n'
    return text+'bool released=VirtualFree(base,0,MEM_RELEASE)!=0;std::printf("GATEWAY_MEMORY pages=5 released=%d\\n",released?1:0);return failures || !released ? 1:0;}\n'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('xex','loader-source','mapping','output'):parser.add_argument('--'+name,type=Path,required=True)
    for name in ('generated','sdk','compiler','vcvars'):parser.add_argument('--'+name,type=Path)
    args=parser.parse_args(argv);bundle=(args.generated,args.sdk,args.compiler,args.vcvars)
    if any(bundle) and not all(bundle):raise ValueError('all toolchain options required')
    inputs=[args.xex,args.loader_source,args.mapping];hashes={str(p):digest(p) for p in inputs}
    if hashes[str(args.mapping)]!=MAPPING_SHA256:raise ValueError('unsupported baseline mapping')
    image=image_from_xex(args.xex.read_bytes(),args.loader_source);original=verify_original(image);code=view(image,TARGET,24)
    if re.search(r'\{\s*0x82509380,',args.mapping.read_text(encoding='utf-8-sig')):raise ValueError('baseline unexpectedly maps gateway')
    fixtures=cases();results=[execute(code,c['registers'],c['memory'],c['lr']) for c in fixtures]
    output=args.output.absolute();roots=[p.resolve() for p in inputs]+[p.resolve() for p in (args.generated,args.sdk) if p]
    if any(output==p or p in output.parents for p in roots):raise ValueError('output aliases input tree')
    output.mkdir(parents=True,exist_ok=False)
    report={'schema':1,'inputs':hashes,'image_sha256':sha(image),'original':original,'fixtures':fixtures,'oracle_results':results,'success':True,'generated_execution':'not-requested','scope':'pure synthetic sparse memory, no XEX loading/title execution/vtable or GNatives fixture'}
    try:
        if args.generated:
            if os.name!='nt' or digest(args.compiler)!=CLANG_CL_SHA256:raise ValueError('unsupported compiler/platform')
            trees=[args.generated,args.sdk/'include',args.compiler.resolve().parent.parent/'lib/clang/20/include'];witnesses=[inventory(p) for p in trees]
            compiler_hash=digest(args.compiler);vcvars_hash=digest(args.vcvars)
            body=extract_body(args.generated);source=output/'gateway.cpp';exe=output/'gateway.exe';source.write_text(harness(body['body'],code),encoding='utf-8')
            command=[str(args.compiler.resolve()),'/nologo','/Brepro','/std:c++latest','/utf-8','/O2','/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/EHa','/arch:AVX2','/bigobj','/MD','/I'+str((args.sdk/'include').resolve()),'/I'+str(args.generated.resolve()),str(source.resolve()),'/Fo'+str((output/'gateway.obj').resolve()),'/Fe'+str(exe.resolve()),'/link','/Brepro']
            process=subprocess.run(command,cwd=output,env=vc_environment(args.vcvars.resolve()),capture_output=True,text=True,timeout=600)
            (output/'compile.txt').write_text(process.stdout+process.stderr,encoding='utf-8')
            report.update(generated=body,source_and_header_trees=witnesses,compile_command=command,compile_exit=process.returncode,success=False,compiler_sha256=compiler_hash,vcvars_sha256=vcvars_hash)
            if process.returncode==0:
                run=subprocess.run([str(exe.resolve())],cwd=output,capture_output=True,text=True,timeout=30)
                expected=''.join(f'GATEWAY_CASE {n} object={c["object_word"]:08X} target={c["target"]:08X} unchanged=1 success=1\n' for n,c in enumerate(fixtures))+'GATEWAY_MEMORY pages=5 released=1\n'
                (output/'run.txt').write_text(run.stdout+run.stderr,encoding='utf-8')
                report.update(run_exit=run.returncode,literal_output=run.stdout,expected_output=expected,executable_sha256=digest(exe),success=run.returncode==0 and run.stdout==expected and not run.stderr)
            report['generated_execution']='unmodified body and SDK loads; external tail target RECORDED ONLY; synthetic reservation released'
            if any(inventory(p)!=old for p,old in zip(trees,witnesses)) or digest(args.compiler)!=compiler_hash or digest(args.vcvars)!=vcvars_hash:raise ValueError('source/header/toolchain changed')
        report['inputs_unchanged']=all(digest(p)==hashes[str(p)] for p in inputs)
        if not report['inputs_unchanged']:raise ValueError('input changed')
    except Exception as error:
        report.update(success=False,error=f'{type(error).__name__}: {error}');raise
    finally:(output/'gateway-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f'GATEWAY target=82509380 cases={len(fixtures)} success={report["success"]}')
    return 0 if report['success'] else 1


if __name__=='__main__':raise SystemExit(main())
