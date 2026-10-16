"""Hash-locked dual-return callback audit and finite original/generated oracle."""
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

TARGET=0x82C1C1A0
TAIL=0x82C1C214
RANGES={TARGET:(136,'60e3229fb7c29acb4ca50ea10e03bf77af7d9e361a9882d12b2f8e7e9ad3388f'),
        0x82C35478:(24,'6f2361b3f7345bbd41f1d30df845a6077c57bb885bf0075e7b5e2aaeb4c057e4'),
        0x8286FE70:(32,'7c03dee81ecdb23f141c71907b93f6f111c897c67501b0b7662d4a68d456d4ba')}
MAPPING_SHA256='450e79f7118b0eb6a9f9036d2c233e7f9e2b7c6724e53a8cb8bcb806ff18dd83'
MASK64=(1<<64)-1


def signed(value,bits):return value-(1<<bits) if value&(1<<(bits-1)) else value


def branch_target(address,word):
    op=word>>26
    if op==18:
        delta=signed(word&0x3FFFFFC,26)
    elif op==16:delta=signed(word&0xFFFC,16)
    else:raise ValueError('not direct branch')
    return (delta if word&2 else address+delta)&0xFFFFFFFF


def audit_tail(image,sections,target=TAIL,base=BASE):
    branches=[];pointers=[];materializations=[];code_words=[]
    for section in sections:
        if section['flags']&0x20000000:
            for address in range((section['start']+3)&~3,section['end']-3,4):
                word=struct.unpack('>I',view(image,address,4,base))[0]
                if word==target:code_words.append({'site':address,'section':section['name'],'qualification':'raw word match, not proven code-embedded data'})
                if word>>26 in (16,18) and branch_target(address,word)==target:
                    branches.append({'site':address,'link':bool(word&1),'internal':TARGET<=address<TARGET+136})
                if word>>26==15 and (word>>16)&31==0 and word&0xFFFF==((target+0x8000)>>16)&0xFFFF:
                    reg=(word>>21)&31
                    for following in range(address+4,min(address+100,section['end']-3),4):
                        candidate=struct.unpack('>I',view(image,following,4,base))[0]
                        if candidate>>26==14 and (candidate>>16)&31==reg and candidate&0xFFFF==target&0xFFFF:
                            materializations.append({'lis':address,'addi':following,'qualification':'bounded syntactic pair; register lifetime not proven'})
        else:
            for address in range((section['start']+3)&~3,section['end']-3,4):
                if struct.unpack('>I',view(image,address,4,base))[0]==target:
                    pointers.append({'site':address,'section':section['name']})
    return {'target':target,'direct_encoding_references':branches,'noncode_aligned_pointer_references':pointers,
            'code_aligned_pointer_words':code_words,
            'nearby_lis_addi_candidates':materializations,
            'scope':'all non-discardable code words and noncode section words; no indirect/runtime-reference completeness claim',
            'independent_external_entry_observed':any(not b['internal'] for b in branches) or bool(pointers) or bool(materializations) or bool(code_words)}


def execute(code,registers,memory,initial_ca=0,max_steps=4096,initial_so=0):
    """Finite read-only PPC subset; rejects cycles, unknown ops and missing reads."""
    if not code or len(code)%4 or len(registers)!=32:raise ValueError('invalid oracle input')
    if initial_ca not in (0,1) or initial_so not in (0,1):raise ValueError('invalid XER fixture')
    regs=[v&MASK64 for v in registers];words=dict(memory);pc=0;ca=initial_ca;cr={24:False,25:False,26:False,27:bool(initial_so)}
    seen=set();trace=[]
    for _ in range(max_steps):
        if pc<0 or pc+4>len(code) or pc%4:raise ValueError('branch outside callback')
        state=(pc,tuple(regs),ca,tuple(cr.values()))
        if state in seen:raise ValueError('cycle detected')
        seen.add(state);trace.append(pc)
        word=struct.unpack_from('>I',code,pc)[0];op=word>>26;rt=(word>>21)&31;ra=(word>>16)&31;rb=(word>>11)&31
        imm=word&0xFFFF;xo=(word>>1)&1023;next_pc=pc+4
        if word==0x4E800020:return {'registers':regs,'memory':words,'ca':ca,'cr6':cr,'trace':trace,'return_offset':pc}
        if op==32:
            address=((regs[ra] if ra else 0)+signed(imm,16))&0xFFFFFFFF
            if address not in words or type(words[address])!=int or not 0<=words[address]<=0xFFFFFFFF:raise ValueError('read outside word fixture')
            regs[rt]=words[address]
        elif op==14:regs[rt]=((regs[ra] if ra else 0)+signed(imm,16))&MASK64
        elif op==21:
            shift=rb;mb=(word>>6)&31;me=(word>>1)&31
            if mb>me or word&1:raise ValueError('unsupported rotate mask')
            value=regs[rt]&0xFFFFFFFF;rotated=((value<<shift)|(value>>(32-shift if shift else 32)))&0xFFFFFFFF
            mask=((0xFFFFFFFF>>mb)&((0xFFFFFFFF<<(31-me))&0xFFFFFFFF));regs[ra]=rotated&mask
        elif op==10 or (op==31 and xo==32):
            if (word>>23)&7!=6 or word&0x200000:raise ValueError('unsupported compare field/width')
            first=regs[ra]&0xFFFFFFFF;second=imm if op==10 else regs[rb]&0xFFFFFFFF
            cr={24:first<second,25:first>second,26:first==second,27:bool(initial_so)}
        elif op==31 and xo==444 and rt==rb:regs[ra]=regs[rt]
        elif op==31 and xo in (8,136) and not word&1:
            a,b=regs[ra],regs[rb]
            if xo==8:regs[rt]=(b-a)&MASK64;ca=int((b&0xFFFFFFFF)>=(a&0xFFFFFFFF))
            else:
                total=(~a&0xFFFFFFFF)+(b&0xFFFFFFFF)+ca
                regs[rt]=((~a&MASK64)+b+ca)&MASK64;ca=int(total>0xFFFFFFFF)
        elif op in (16,18) and not word&1:
            take=True
            if op==16:
                bo=(word>>21)&31;bi=(word>>16)&31
                if bo not in (4,12) or bi not in cr:raise ValueError('unsupported conditional branch')
                take=cr[bi] if bo==12 else not cr[bi]
            if take:next_pc=branch_target(pc,word)
        else:raise ValueError(f'unknown callback opcode at +{pc:X}')
        pc=next_pc
    raise ValueError('oracle step limit')


def fixture(left,right):
    memory={0x100:0x200,0x104:0x240,0x220:0,0x260:0};cursor=0x400
    for values,head in ((left,0x220),(right,0x260)):
        previous=None
        for value in values:
            node,data=cursor,cursor+8;cursor+=16
            memory[node]=data;memory[node+4]=0;memory[data]=value&0xFFFFFFFF
            if previous is None:memory[head]=node
            else:memory[previous+4]=node
            previous=node
    registers=[0xABCD0000+index*0x101 for index in range(32)];registers[3]=0x100;registers[4]=0x104
    expected_left=max(((v>>13)&0xFFFF for v in left),default=0);expected_right=max(((v>>13)&0xFFFF for v in right),default=0)
    return {'left':left,'right':right,'registers':registers,'memory':memory,
            'expected_result':0 if expected_left==expected_right else 0xFFFFFFFF if expected_left>expected_right else 1}


def cases():
    s=lambda value:(value&0xFFFF)<<13
    pairs=[([],[]),([s(1)],[]),([],[s(1)]),([s(5)],[s(5)]),([s(9)],[s(3)]),([s(3)],[s(9)]),
           ([s(1),s(50),s(2)],[s(49),s(3)]),([s(1),s(2)],[s(1),s(65535),s(4)]),
           ([s(65535)],[s(65535)]),([0xFFFFFFFF],[s(65535)]),([0xE0001FFF],[0]),
           ([s(7),s(7),s(3)],[s(7)]),([s(32768)],[s(32767)]),([s(32767)],[s(32768)])]
    return [dict(fixture(a,b),initial_ca=index%2,initial_so=(index//2)%2) for index,(a,b) in enumerate(pairs)]


def extract_body(directory):
    found=[]
    for path in sorted(Path(directory).glob('*.cpp')):
        text=path.read_text(encoding='utf-8-sig')
        for match in re.finditer(r'DEFINE_REX_FUNC\(sub_82C1C1A0\) \{(.*?)\n\}',text,re.S):
            if any(token in match[0] for token in ('REX_FATAL','REX_CALL_','REX_STORE_')):raise ValueError('unexpected callback call/store/fatal')
            found.append({'source':str(path.resolve()),'source_sha256':digest(path),'body':match[0],'body_sha256':sha(match[0].encode()),'line':text.count('\n',0,match.start())+1})
    if len(found)!=1:raise ValueError('expected one complete generated compare callback')
    return found[0]


def verify_new_mapping(mapping_text,body):
    result={'entry_present':bool(re.search(r'\{\s*0x82C1C1A0,',mapping_text)),
            'tail_present':bool(re.search(r'\{\s*0x82C1C214,',mapping_text)),
            'tail_label_in_complete_body':'loc_82C1C214:' in body}
    if not result['entry_present']:raise ValueError('new callback entry registration missing')
    if not result['tail_label_in_complete_body']:raise ValueError('internal tail label missing from complete callback')
    return result


def harness(body,code):
    text='#include "mc2_probe_pch.h"\n#include <cstdio>\n#include <cstring>\n'+body+'\nint main(){alignas(32) unsigned char memory[4096],before[4096];uint8_t* base=memory;PPCContext ctx{};int failures=0;\n'
    for number,case in enumerate(cases()):
        expected=execute(code,case['registers'],case['memory'],case['initial_ca'],initial_so=case['initial_so'])
        if expected['registers'][3]&0xFFFFFFFF!=case['expected_result']:raise ValueError('oracle differs from independent maximum oracle')
        text+='{for(unsigned i=0;i<4096;i++)memory[i]=(i*17+5)%256;ctx=PPCContext{};\n'
        for address,value in case['memory'].items():text+=f'REX_STORE_U32({address},0x{value:08X}u);\n'
        for index,value in enumerate(case['registers']):text+=f'ctx.r{index}.u64=0x{value:016X}ull;\n'
        text+=f'ctx.xer.ca={case["initial_ca"]};ctx.xer.so={case["initial_so"]};ctx.lr=0x1122334455667788ull;std::memcpy(before,memory,4096);sub_82C1C1A0(ctx,base);bool good=ctx.lr==0x1122334455667788ull && std::memcmp(memory,before,4096)==0;\n'
        for index,value in enumerate(expected['registers']):text+=f'good=good && ctx.r{index}.u64==0x{value:016X}ull;\n'
        for bit,name in ((24,'lt'),(25,'gt'),(26,'eq'),(27,'so')):text+=f'good=good && ctx.cr6.{name}=={str(expected["cr6"][bit]).lower()};\n'
        text+=f'good=good && ctx.xer.ca=={expected["ca"]};std::printf("COMPARE_CASE {number} result=%08X success=%d\\n",ctx.r3.u32,good?1:0);failures+=!good;}}\n'
    return text+'return failures?1:0;}\n'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('xex','loader-source','mapping','output'):parser.add_argument('--'+name,type=Path,required=True)
    for name in ('generated','sdk','compiler','vcvars'):parser.add_argument('--'+name,type=Path)
    args=parser.parse_args(argv);bundle=(args.generated,args.sdk,args.compiler,args.vcvars)
    if any(bundle) and not all(bundle):raise ValueError('all toolchain options required')
    inputs=[args.xex,args.loader_source,args.mapping];hashes={str(p):digest(p) for p in inputs}
    if hashes[str(args.mapping)]!=MAPPING_SHA256:raise ValueError('unsupported baseline mapping')
    image=image_from_xex(args.xex.read_bytes(),args.loader_source)
    for address,(size,expected) in RANGES.items():
        if sha(view(image,address,size))!=expected:raise ValueError('original compare witness mismatch')
    sections,pdata=sections_and_pdata(image);audit=audit_tail(image,sections)
    mapping_text=args.mapping.read_text(encoding='utf-8-sig')
    if re.search(r'\{\s*0x82C1C1A0,',mapping_text) or not re.search(r'\{\s*0x82C1C214,',mapping_text):raise ValueError('baseline entry/tail mapping mismatch')
    if any(a<=TARGET<a+size for a,size in pdata):raise ValueError('unexpected containing PDATA')
    code=view(image,TARGET,136);fixtures=cases();results=[execute(code,c['registers'],c['memory'],c['initial_ca'],initial_so=c['initial_so']) for c in fixtures]
    if any((r['registers'][3]&0xFFFFFFFF)!=c['expected_result'] for c,r in zip(fixtures,results)):raise ValueError('PPC/max oracle mismatch')
    if {r['return_offset'] for r in results}!={0x70,0x84}:raise ValueError('both original return paths not exercised')
    output=args.output.absolute();roots=[p.resolve() for p in inputs]+[p.resolve() for p in (args.generated,args.sdk) if p]
    if any(output==p or p in output.parents for p in roots):raise ValueError('output aliases input tree')
    output.mkdir(parents=True,exist_ok=False)
    report={'schema':1,'inputs':hashes,'image_sha256':sha(image),'ranges':RANGES,'tail_reference_audit':audit,
            'target':TARGET,'cases':fixtures,'oracle_results':results,'success':True,'generated_execution':'not-requested',
            'original_return_addresses':[TARGET+0x70,TARGET+0x84],'scope':'finite synthetic read-only linked-word fixtures, no named game object semantics'}
    try:
        if args.generated:
            if os.name!='nt' or digest(args.compiler)!=CLANG_CL_SHA256:raise ValueError('unsupported compiler/platform')
            trees=[args.generated,args.sdk/'include',args.compiler.resolve().parent.parent/'lib/clang/20/include'];witnesses=[inventory(p) for p in trees]
            compiler_hash=digest(args.compiler);vcvars_hash=digest(args.vcvars)
            body=extract_body(args.generated);source=output/'compare.cpp';exe=output/'compare.exe';source.write_text(harness(body['body'],code),encoding='utf-8')
            new_mapping=(args.generated/'mc2_probe_init.cpp').read_text(encoding='utf-8-sig')
            report['new_mapping']=verify_new_mapping(new_mapping,body['body'])
            command=[str(args.compiler.resolve()),'/nologo','/Brepro','/std:c++latest','/utf-8','/O2','/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/EHa','/arch:AVX2','/bigobj','/MD','/I'+str((args.sdk/'include').resolve()),'/I'+str(args.generated.resolve()),str(source.resolve()),'/Fo'+str((output/'compare.obj').resolve()),'/Fe'+str(exe.resolve()),'/link','/Brepro']
            process=subprocess.run(command,cwd=output,env=vc_environment(args.vcvars.resolve()),capture_output=True,text=True,timeout=600)
            (output/'compile.txt').write_text(process.stdout+process.stderr,encoding='utf-8')
            report.update(generated=body,source_and_header_trees=witnesses,compile_command=command,compile_exit=process.returncode,success=False,compiler_sha256=compiler_hash,vcvars_sha256=vcvars_hash)
            if process.returncode==0:
                run=subprocess.run([str(exe.resolve())],cwd=output,capture_output=True,text=True,timeout=30)
                expected=''.join(f'COMPARE_CASE {n} result={case["expected_result"]:08X} success=1\n' for n,case in enumerate(fixtures))
                (output/'run.txt').write_text(run.stdout+run.stderr,encoding='utf-8')
                report.update(run_exit=run.returncode,literal_output=run.stdout,expected_output=expected,executable_sha256=digest(exe),success=run.returncode==0 and run.stdout==expected and not run.stderr)
            report['generated_execution']='unmodified complete generated body, no guest callee or macro replacement'
            if any(inventory(p)!=old for p,old in zip(trees,witnesses)) or digest(args.compiler)!=compiler_hash or digest(args.vcvars)!=vcvars_hash:raise ValueError('source/header/toolchain changed')
        report['inputs_unchanged']=all(digest(p)==hashes[str(p)] for p in inputs)
        if not report['inputs_unchanged']:raise ValueError('input changed')
    except Exception as error:
        report.update(success=False,error=f'{type(error).__name__}: {error}');raise
    finally:(output/'compare-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f'COMPARE target=82C1C1A0 cases={len(fixtures)} returns=2 success={report["success"]}')
    return 0 if report['success'] else 1


if __name__=='__main__':raise SystemExit(main())
