"""Read-only original callback audit and narrow generated-leaf differential probe."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess

from tools.research.verify_branch_ranges import BASE, image_from_xex
from tools.research.compile_module import digest, vc_environment, inventory
from tools.research.probe_route_a import CLANG_CL_SHA256

TARGET=0x8234FF10
RANGES={TARGET:(48,'5c43c892cc33dcb8b15d083257e0a8211788bb01aaa0698cd379c2164e77665e'),
        0x82D6C814:(52,'202a1ab7d650d7ef8d794b7fee340b2f6f1316f882a136e6370c4b8de94e2c06'),
        0x823B9AF8:(36,'5be23cc244ed483e4994d1c1245d13b66d7e18187db96c1a2d0cb06be09bf3c8')}


def sha(data):return hashlib.sha256(data).hexdigest()


def view(image,address,size,base=BASE):
    offset=address-base
    if offset<0 or size<0 or offset+size>len(image):raise ValueError('image range out of bounds')
    return image[offset:offset+size]


def execute_callback(code,registers,memory):
    """Finite oracle: cmplwi cr6 / beqlr cr6 / lis / addi / stw / blr only.

    This deliberately rejects every other opcode/template, memory overflow,
    nonzero RA for lis, and missing return. It is not a general PPC emulator.
    Input memory/registers are copied; ordered stores remain observable.
    """
    if not code or len(code)%4:raise ValueError('unaligned callback code')
    regs=list(registers)
    if len(regs)!=32:raise ValueError('expected 32 registers')
    regs=[r&0xFFFFFFFFFFFFFFFF for r in regs];data=bytearray(memory);stores=[];equal=None
    for pc in range(0,len(code),4):
        word=struct.unpack_from('>I',code,pc)[0];op=word>>26
        rt=(word>>21)&31;ra=(word>>16)&31;imm=word&0xFFFF
        signed=imm-0x10000 if imm&0x8000 else imm
        if word==0x4E800020:return {'registers':regs,'memory':bytes(data),'stores':stores,'equal':equal}
        if word==0x4D9A0020:
            if equal is None:raise ValueError('conditional return before compare')
            if equal:return {'registers':regs,'memory':bytes(data),'stores':stores,'equal':equal}
        elif word==0x2B030000:equal=(regs[3]&0xFFFFFFFF)==0
        elif op==15 and ra==0:regs[rt]=(signed<<16)&0xFFFFFFFFFFFFFFFF
        elif op==14:regs[rt]=((regs[ra] if ra else 0)+signed)&0xFFFFFFFFFFFFFFFF
        elif op==36:
            address=((regs[ra] if ra else 0)+signed)&0xFFFFFFFF
            if address+4>len(data):raise ValueError('store outside fixture')
            value=regs[rt]&0xFFFFFFFF
            data[address:address+4]=struct.pack('>I',value);stores.append((address,value))
        else:raise ValueError(f'unsupported callback instruction at +{pc:X}')
    raise ValueError('missing callback return')


def verify_image(image):
    result=[]
    for address,(size,expected) in RANGES.items():
        if sha(view(image,address,size))!=expected:raise ValueError(f'callback witness mismatch: {address:08X}')
        result.append({'address':address,'size':size,'sha256':expected})
    # The original exception table is another independent boundary witness.
    if image[:2]!=b'MZ' or len(image)<64:raise ValueError('invalid DOS image')
    pe=struct.unpack_from('<I',image,0x3C)[0]
    if view(image,BASE+pe,4)!=b'PE\0\0':raise ValueError('invalid PE image')
    offset,size=struct.unpack('<II',view(image,BASE+pe+24+96+24,8))
    if size%8:raise ValueError('invalid PDATA length')
    records=list(struct.iter_unpack('>II',view(image,BASE+offset,size)))
    if any(a<=TARGET<a+((fields>>8)&0x3FFFFF)*4 for a,fields in records):
        raise ValueError('unexpected containing PDATA record')
    code=view(image,TARGET,48)
    run=execute_callback(code,[0,0,0,0x100]+[0]*28,bytes(0x1000))
    expected=[(0x184,0x82124644),(0x100,0x82124FC0),(0x184,0x82125118)]
    if run['stores']!=expected:raise ValueError('original callback store sequence mismatch')
    return {'ranges':result,'containing_pdata':False,'ordered_stores':expected,
            'address_materialization':{'lis':0x82D6C814,'addi':0x82D6C834,'call':0x82D6C844,'argument_register':9,'target':TARGET},
            'actual_call_witness':{'load_source_offsets':[284,284],'bctrl':0x823B9B18,'lr':0x823B9B1C},
            'semantics':'null r3 returns without stores; nonnull writes object+132,object+0,object+132 in that order; final +132 overwrites first value',
            'limits':'no class name/constructor identity asserted; no whole-game execution'}


def extract_body(directory):
    found=[]
    for path in sorted(Path(directory).glob('*.cpp')):
        text=path.read_text(encoding='utf-8-sig')
        for match in re.finditer(r'DEFINE_REX_FUNC\(sub_8234FF10\) \{(.*?)\n\}',text,re.S):
            if 'REX_FATAL' in match[0] or 'REX_CALL_' in match[0]:raise ValueError('unexpected callback fatal/dispatch')
            comments=re.findall(r'// ([^\n]+)',match[1])
            if len(comments)!=12 or match[0].count('REX_STORE_U32(')!=3:
                raise ValueError('unexpected generated callback shape')
            found.append({'source':str(path.resolve()),'source_sha256':digest(path),'body':match[0],
                          'body_sha256':sha(match[0].encode()),'line':text.count('\n',0,match.start())+1})
    if len(found)!=1:raise ValueError('expected exactly one generated callback body')
    return found[0]


def fixtures(code):
    result=[]
    for seed,address in enumerate((0,0x100,0x180,0x400,0xF78)):
        regs=[(0xA5000000+index*0x101+seed)&0xFFFFFFFF for index in range(32)];regs[3]=address
        memory=bytes((index*17+seed)%256 for index in range(4096))
        expected=execute_callback(code,regs,memory)
        result.append({'seed':seed,'address':address,'registers':regs,'initial_memory':memory,
                       'expected_registers':expected['registers'],'expected_memory':expected['memory'],
                       'expected_equal':expected['equal'],'ordered_stores':expected['stores']})
    return result


def harness(body,cases):
    text='#include "mc2_probe_pch.h"\n#include <cstdio>\n#include <cstring>\n'+body+'\nint main(){ alignas(32) unsigned char memory[4096]{}; uint8_t* base=memory; PPCContext ctx{}; int failures=0;\n'
    for number,case in enumerate(cases):
        text+='{ ctx=PPCContext{};\n'
        text+=f'for(unsigned i=0;i<4096;i++) memory[i]=(i*17+{case["seed"]})%256;\n'
        for index,value in enumerate(case['registers']):text+=f'ctx.r{index}.u64=0x{value:08X}u;\n'
        text+='ctx.lr=0x11223344; sub_8234FF10(ctx,base); bool good=ctx.lr==0x11223344;\n'
        for index,value in enumerate(case['expected_registers']):text+=f'good=good && ctx.r{index}.u64==0x{value:016X}ull;\n'
        changes={i:v for i,v in enumerate(case['expected_memory']) if v!=case['initial_memory'][i]}
        text+=f'for(unsigned i=0;i<4096;i++) {{ unsigned expected=(i*17+{case["seed"]})%256; switch(i){{'
        for offset,value in changes.items():text+=f'case {offset}:expected={value};break;'
        text+='} good=good && memory[i]==expected; }\n'
        text+=f'good=good && ctx.cr6.eq=={str(case["expected_equal"]).lower()}; std::printf("CALLBACK_CASE {number} r3={case["address"]:08X} success=%d\\n",good?1:0);failures+=!good; }}\n'
    return text+'return failures?1:0; }\n'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for option in ('xex','loader-source','output'):parser.add_argument('--'+option,type=Path,required=True)
    for option in ('generated','sdk','compiler','vcvars'):parser.add_argument('--'+option,type=Path)
    args=parser.parse_args(argv)
    bundle=(args.generated,args.sdk,args.compiler,args.vcvars)
    if any(bundle) and not all(bundle):raise ValueError('generated probe requires all toolchain options')
    inputs=[args.xex,args.loader_source];hashes={str(p):digest(p) for p in inputs}
    image=image_from_xex(args.xex.read_bytes(),args.loader_source);report=verify_image(image)
    output=args.output.absolute()
    if any(output==p.resolve() or output in p.resolve().parents for p in inputs):raise ValueError('output aliases input')
    if args.generated and (output==args.generated.resolve() or args.generated.resolve() in output.parents):
        raise ValueError('output inside generated tree')
    if args.sdk and (output==args.sdk.resolve() or args.sdk.resolve() in output.parents):
        raise ValueError('output inside SDK tree')
    output.mkdir(parents=True,exist_ok=False)
    report.update(inputs=hashes,image_sha256=sha(image),generated_execution='not-requested',success=True)
    try:
        if args.generated:
            if os.name!='nt' or digest(args.compiler)!=CLANG_CL_SHA256:raise ValueError('unsupported compiler/platform')
            trees=[args.generated,args.sdk/'include',args.compiler.resolve().parent.parent/'lib/clang/20/include']
            witnesses=[inventory(p) for p in trees]
            report['source_and_header_trees']=witnesses
            report['vcvars_sha256']=digest(args.vcvars)
            generated=extract_body(args.generated);cases=fixtures(view(image,TARGET,48))
            source=output/'callback-harness.cpp';exe=output/'callback-harness.exe'
            source.write_text(harness(generated['body'],cases),encoding='utf-8')
            command=[str(args.compiler.resolve()),'/nologo','/Brepro','/std:c++latest','/utf-8','/O2',
                     '/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN',
                     '/EHa','/arch:AVX2','/bigobj','/MD','/I'+str((args.sdk/'include').resolve()),
                     '/I'+str(args.generated.resolve()),str(source.resolve()),'/Fo'+str((output/'callback.obj').resolve()),
                     '/Fe'+str(exe.resolve()),'/link','/Brepro']
            compiled=subprocess.run(command,cwd=output,env=vc_environment(args.vcvars.resolve()),capture_output=True,text=True,timeout=600)
            (output/'compile.txt').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
            report.update(generated=generated,compile_command=command,compile_exit=compiled.returncode,
                          compiler_sha256=digest(args.compiler),harness_sha256=digest(source),success=False)
            if compiled.returncode==0:
                run=subprocess.run([str(exe.resolve())],cwd=output,capture_output=True,text=True,timeout=30)
                expected=''.join(f'CALLBACK_CASE {n} r3={case["address"]:08X} success=1\n' for n,case in enumerate(cases))
                (output/'run.txt').write_text(run.stdout+run.stderr,encoding='utf-8')
                report.update(run_exit=run.returncode,literal_output=run.stdout,expected_output=expected,
                              executable_sha256=digest(exe),success=run.returncode==0 and run.stdout==expected and not run.stderr)
            report['generated_execution']='isolated unmodified generated body, real SDK memory macros, five synthetic cases'
            if any(inventory(p)!=before for p,before in zip(trees,witnesses)) or digest(args.compiler)!=CLANG_CL_SHA256 or digest(args.vcvars)!=report['vcvars_sha256']:
                raise ValueError('source/header/toolchain input changed')
        report['inputs_unchanged']=all(digest(p)==hashes[str(p)] for p in inputs)
        if not report['inputs_unchanged']:raise ValueError('input changed')
    except Exception as error:
        report.update(success=False,error=f'{type(error).__name__}: {error}')
        raise
    finally:
        (output/'callback-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f'CALLBACK target=8234FF10 original_stores=3 generated_cases={5 if args.generated else 0} success={report["success"]}')
    return 0 if report['success'] else 1


if __name__=='__main__':raise SystemExit(main())
