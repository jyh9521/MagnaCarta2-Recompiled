"""Hash-locked original float leaf proof and integer IEEE format oracle.

The oracle is round-to-nearest-even, gradual underflow, with explicit NaN
policy. It is not proof of Xenon FPSCR modes, traps, or signaling-NaN behavior.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import re
import os
import subprocess

BASE=0x82000000
ENTRY=0x82AC1DE8
EXPECTED=bytes.fromhex('c0030030d0040000c0030034d00500004e800020')
IMAGE_SHA256='d18d49fb2960426715ba17d61d069cce42b1eadac153af13c9395cd42b1773e9'

def uint(value,bits):
    if type(value) is not int or not 0<=value<1<<bits:raise ValueError('invalid unsigned bit pattern')
    return value

def policy(value):
    if value not in ('preserve','quiet'):raise ValueError('unknown NaN policy')

def widen32(word,nan_policy='preserve'):
    """IEEE binary32 to exact binary64 bits, no host float operations."""
    uint(word,32);policy(nan_policy)
    sign=(word>>31)<<63; exp=(word>>23)&255; frac=word&0x7fffff
    if exp==255:
        payload=frac<<29
        if frac and nan_policy=='quiet':payload|=1<<51
        return sign|(2047<<52)|payload
    if exp:return sign|((exp+896)<<52)|(frac<<29)
    if not frac:return sign
    k=frac.bit_length()-1
    return sign|((k-149+1023)<<52)|((frac-(1<<k))<<(52-k))

def rounded_shift(value,shift):
    """Integer times2**shift rounded nearest, ties to even."""
    if shift>=0:return value<<shift
    n=-shift;whole=value>>n;rem=value- (whole<<n);half=1<<(n-1)
    return whole+int(rem>half or rem==half and whole&1)

def narrow64(word,nan_policy='preserve'):
    """IEEE binary64 to binary32 bits: RNE/gradual underflow, explicit NaNs."""
    uint(word,64);policy(nan_policy)
    sign=(word>>63)<<31; exp=(word>>52)&2047;frac=word&((1<<52)-1)
    if exp==2047:
        if not frac:return sign|0x7f800000
        payload=frac>>29
        if not payload:payload=1
        if nan_policy=='quiet':payload|=1<<22
        return sign|0x7f800000|payload
    sig=((1<<52)|frac) if exp else frac
    if not sig:return sign
    power=exp-1023-52 if exp else -1074
    highest=sig.bit_length()-1+power
    if highest < -126:
        rounded=rounded_shift(sig,power+149)
        return sign|rounded
    rounded=rounded_shift(sig,power-highest+23)
    if rounded>=1<<24:rounded>>=1;highest+=1
    if highest>127:return sign|0x7f800000
    return sign|((highest+127)<<23)|(rounded&0x7fffff)

def simulate_leaf(memory,object_offset,out_first,out_second,nan_policy='preserve'):
    """Ordered valid-memory fixture, BE32 accesses, no guest runtime execution."""
    policy(nan_policy)
    if type(memory) is not bytes or len(memory)>1048576:raise ValueError('invalid bounded fixture memory')
    accesses=(object_offset+0x30 if type(object_offset) is int else None,
              object_offset+0x34 if type(object_offset) is int else None,out_first,out_second)
    if any(type(a) is not int or a<0 or a%4 or a+4>len(memory) for a in accesses):raise ValueError('invalid aligned fixture access')
    result=bytearray(memory);fpr0=None
    for source,dest in ((accesses[0],out_first),(accesses[1],out_second)):
        fpr0=widen32(int.from_bytes(result[source:source+4],'big'),nan_policy)
        result[dest:dest+4]=narrow64(fpr0,nan_policy).to_bytes(4,'big')
    return {'memory':bytes(result),'fpr0_bits':fpr0,'accesses':[
        ['read32',accesses[0]],['write32',out_first],['read32',accesses[1]],['write32',out_second]],
        'unchanged_architectural_fields_modeled':['GPRs','CR','LR','CTR'],
        'not_modeled':['FPSCR flags/mode/traps','memory faults/MMIO','hardware signaling NaN semantics','instruction timing']}

def verify_original(image):
    if type(image) is not bytes or hashlib.sha256(image).hexdigest()!=IMAGE_SHA256:raise ValueError('unsupported original image hash')
    off=ENTRY-BASE
    if image[off:off+20]!=EXPECTED:raise ValueError('original leaf instruction mismatch')
    before=image[off-4:off];after=image[off+20:off+24]
    if before!=bytes.fromhex('4e800420') or after!=bytes(4):raise ValueError('original sibling/padding boundary mismatch')
    pe=struct.unpack_from('<I',image,0x3c)[0];pdata,size=struct.unpack_from('<II',image,pe+24+96+24)
    if size%8 or pdata+size>len(image):raise ValueError('invalid PDATA')
    containing=[]
    for o in range(pdata,pdata+size,8):
        a,fields=struct.unpack_from('>II',image,o);end=a+((fields>>8)&0x3fffff)*4
        if a<=ENTRY<end:containing.append([a,end])
    if containing:raise ValueError('unexpected containing PDATA')
    return {'entry':ENTRY,'size':20,'original_bytes_hex':EXPECTED.hex(),'sha256':hashlib.sha256(EXPECTED).hexdigest(),
            'before_word_hex':before.hex(),'after_word_hex':after.hex(),'containing_pdata':containing,
            'boundary':'conservative leaf ending BLR; preceding sibling BCTR and following zero padding; not PDATA-derived',
            'instructions':['lfs f0,0x30(r3)','stfs f0,0(r4)','lfs f0,0x34(r3)','stfs f0,0(r5)','blr']}


def extract_body(directory):
    found=[]
    for path in sorted(Path(directory).glob('*.cpp')):
        text=path.read_text(encoding='utf-8-sig')
        for match in re.finditer(r'DEFINE_REX_FUNC\(sub_82AC1DE8\) \{(.*?)\n\}',text,re.S):
            body=match[0]
            if 'REX_FATAL' in body or 'REX_CALL' in body or body.count('REX_LOAD_U32(')!=2 or body.count('REX_STORE_U32(')!=2:
                raise ValueError('unexpected generated float leaf shape')
            local=bool(re.search(r'PPCRegister\s+f0\s*(?:;|=|\{)',body))
            found.append({'source':str(path.resolve()),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'body':body,'body_sha256':hashlib.sha256(body.encode()).hexdigest(),'f0_local':local,'line':text.count('\n',0,match.start())+1})
    if len(found)!=1:raise ValueError('expected one complete float leaf body')
    for filename,pattern in [('mc2_probe_init.cpp',r'\{\s*0x82AC1DE8,\s*(\w+)\s*\}'),('mc2_probe_register.cpp',r'registrar->SetFunction\(0x82AC1DE8,\s*(\w+)\);')]:
        if re.findall(pattern,(Path(directory)/filename).read_text(encoding='utf-8-sig'))!=['sub_82AC1DE8']:raise ValueError('expected one-to-one float leaf mapping and registration')
    return found[0]

def differential_fixtures():
    words=[0,0x80000000,1,0x807fffff,0x00800000,0x3f800000,0x7f7fffff,0x7f800000,0xff800000,0x7fc12345,0x7f812345,0xff812345]
    rows=[]
    for i,first in enumerate(words):
        for alias in range(4):
            for mode in range(4):
                for flush in (0,0x40,0x8000,0x8040):
                    mem=bytearray((j*17+len(rows))%256 for j in range(4096));mem[0x30:0x34]=first.to_bytes(4,'big');second=words[(i+3)%len(words)];mem[0x34:0x38]=second.to_bytes(4,'big')
                    out1=0x34 if alias==1 else 0x30 if alias==3 else 0x100
                    out2=out1 if alias==2 else 0x30 if alias==3 else 0x104
                    q=simulate_leaf(bytes(mem),0,out1,out2,'quiet');v=simulate_leaf(bytes(mem),0,out1,out2,'preserve')
                    rows.append({'index':len(rows),'first':first,'second':second,'alias':alias,'host_round':mode<<13,'host_flush':flush,'out1':out1,'out2':out2,'guest':0xFFFEE000 if len(rows)%2 else 0x2000,'initial':bytes(mem),'quiet':q,'preserve':v})
    return rows

def harness(body,fixtures):
    text='#include "mc2_probe_pch.h"\n#include <windows.h>\n#include <cstdio>\n#include <cstring>\n'+body['body']+'\n'
    text+='struct Case{unsigned a,b,o1,o2,guest,mode,flush;uint64_t f0;};\nstatic const Case cases[]={\n'
    text+=',\n'.join('{'+','.join(f'0x{c[k]:X}u' for k in ('first','second','out1','out2','guest','host_round','host_flush'))+f',0x{c["quiet"]["fpr0_bits"]:016X}ull'+'}' for c in fixtures)+'};\n'
    text+='static const unsigned char expected[][4096]={\n'+',\n'.join('{'+','.join(str(b) for b in c['quiet']['memory'])+'}' for c in fixtures)+'};\n'
    text+='int main(){auto saved=PPCFPSCRRegister::Platform::getcsr();uint8_t* base=(uint8_t*)VirtualAlloc(nullptr,0x100000000ull,MEM_RESERVE,PAGE_NOACCESS);if(!base)return 2;unsigned guests[]={0x2000u,0xFFFEE000u};for(auto g:guests){auto p=g+REX_PHYS_HOST_OFFSET(g);if(VirtualAlloc(base+p,4096,MEM_COMMIT,PAGE_READWRITE)!=base+p){VirtualFree(base,0,MEM_RELEASE);return 3;}}unsigned failures=0;\n'
    text+='for(unsigned n=0;n<sizeof(cases)/sizeof(cases[0]);n++){auto c=cases[n];auto page=c.guest+REX_PHYS_HOST_OFFSET(c.guest);auto other=guests[c.guest==0x2000?1:0];other+=REX_PHYS_HOST_OFFSET(other);for(unsigned j=0;j<4096;j++){base[page+j]=(j*17+n)%256;base[other+j]=0xA5;}REX_STORE_U32(c.guest+0x30,c.a);REX_STORE_U32(c.guest+0x34,c.b);alignas(PPCContext) unsigned char initial[sizeof(PPCContext)]{};PPCContext ctx{};for(unsigned j=0;j<sizeof(ctx);j++)((unsigned char*)&ctx)[j]=(j*7+13)%256;ctx.r3.u64=0xABCD000000000000ull|c.guest;ctx.r4.u64=0x1234000000000000ull|(c.guest+c.o1);ctx.r5.u64=0x5678000000000000ull|(c.guest+c.o2);PPCFPSCRRegister::Platform::setcsr(0x1F80u|c.mode|c.flush);ctx.fpscr.InitHost();std::memcpy(initial,&ctx,sizeof(ctx));PPCContext expected_ctx;std::memcpy(&expected_ctx,initial,sizeof(ctx));expected_ctx.fpscr.csr&=~PPCFPSCRRegister::FlushMask;'
    if not body['f0_local']:text+='expected_ctx.f0.u64=c.f0;'
    text+='sub_82AC1DE8(ctx,base);auto host=PPCFPSCRRegister::Platform::getcsr();PPCFPSCRRegister::Platform::setcsr(saved);bool memory=std::memcmp(base+page,expected[n],4096)==0;for(unsigned j=0;j<4096;j++)memory=memory&&base[other+j]==0xA5;bool context=std::memcmp(&ctx,&expected_ctx,sizeof(ctx))==0;bool mode=(host&~0x3Fu)==(0x1F80u|c.mode);bool good=memory&&context&&mode;std::printf("FLOAT_CASE %u memory=%d context=%d mode=%d ctx_f0=%016llX out1=%08X out2=%08X host_csr=%08X cached_csr=%08X success=%d\\n",n,memory,context,mode,(unsigned long long)ctx.f0.u64,REX_LOAD_U32(c.guest+c.o1),REX_LOAD_U32(c.guest+c.o2),host,ctx.fpscr.csr,good);failures+=!good;}bool released=VirtualFree(base,0,MEM_RELEASE)!=0;PPCFPSCRRegister::Platform::setcsr(saved);std::printf("FLOAT_MEMORY pages=2 released=%d failures=%u\\n",released,failures);return failures||!released?1:0;}\n'
    return text

def fp_flags(optimization='Od',fp_strict=False):
    if optimization not in ('Od','O2') or type(fp_strict) is not bool:raise ValueError('unsupported floating compile flags')
    return ['/'+optimization]+(['/fp:strict'] if fp_strict else [])

def run_differential(args):
    from tools.research.compile_module import digest,inventory,vc_environment
    from tools.research.probe_route_a import CLANG_CL_SHA256
    if os.name!='nt' or digest(args.compiler)!=CLANG_CL_SHA256:raise ValueError('unsupported compiler/platform')
    output=args.output.resolve().parent/(args.output.stem+'-harness')
    roots=[p.resolve() for p in (args.generated,args.sdk,args.compiler.parent,args.xex,args.loader_source)]
    if any(output==p or p in output.parents for p in roots):raise ValueError('harness output aliases input')
    output.mkdir(parents=True,exist_ok=False)
    report={'success':False,'oracle_policy':'quiet NaNs, IEEE RNE gradual; modes preserved, lfs requires disableFlushMode; strict expected fixed before executing generated code','limits':'No hardware/FPSCR guest exception equivalence, invalid memory not tested','optimization':args.optimization,'fp_strict':args.fp_strict}
    try:
        trees=[args.generated,args.sdk/'include',args.compiler.resolve().parent.parent/'lib/clang/20/include'];before=[inventory(t) for t in trees];tool_hash={str(q):digest(q) for q in (args.compiler,args.vcvars)}
        body=extract_body(args.generated);cases=differential_fixtures();source=output/'float-leaf.cpp';source.write_text(harness(body,cases),encoding='utf-8');exe=output/'float-leaf.exe'
        cmd=[str(args.compiler.resolve()),'/nologo','/Brepro','/std:c++latest','/utf-8',*fp_flags(args.optimization,args.fp_strict),'/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/EHa','/arch:AVX2','/bigobj','/MD','/I'+str((args.sdk/'include').resolve()),'/I'+str(args.generated.resolve()),str(source),'/Fo'+str(output/'float-leaf.obj'),'/Fe'+str(exe),'/link','/Brepro']
        process=subprocess.run(cmd,cwd=output,env=vc_environment(args.vcvars.resolve()),capture_output=True,text=True,timeout=600);(output/'compile.txt').write_text(process.stdout+process.stderr,encoding='utf-8')
        report.update(body=body,compile_command=cmd,compile_exit=process.returncode,cases=len(cases),harness_sha256=digest(source),trees_before=before,toolchain_sha256=tool_hash)
        if process.returncode==0:
            v=subprocess.run([str(exe)],cwd=output,capture_output=True,text=True,timeout=60);(output/'run.txt').write_text(v.stdout+v.stderr,encoding='utf-8')
            lines=v.stdout.splitlines();rows=[line for line in lines if line.startswith('FLOAT_CASE ')];report.update(run_exit=v.returncode,literal_output=v.stdout,stderr=v.stderr,executable_sha256=digest(exe),success=v.returncode==0 and len(rows)==len(cases) and all(line.endswith('success=1') for line in rows) and lines[-1]=='FLOAT_MEMORY pages=2 released=1 failures=0' and not v.stderr)
        report['inputs_unchanged']=all(inventory(t)==b for t,b in zip(trees,before)) and all(digest(Path(q))==v for q,v in tool_hash.items())
        if not report['inputs_unchanged']:raise ValueError('input tree/toolchain changed')
    except Exception as e:report.update(error=f'{type(e).__name__}: {e}',success=False);raise
    finally:(output/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return {'path':str(output/'verification.json'),'success':report['success'],'compile_exit':report.get('compile_exit'),'run_exit':report.get('run_exit')}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--optimization',choices=('Od','O2'),default='Od')
    p.add_argument('--fp-strict',action='store_true')
    for n in ('xex','loader-source','output'):p.add_argument('--'+n,type=Path,required=True)
    for n in ('generated','sdk','compiler','vcvars'):p.add_argument('--'+n,type=Path)
    a=p.parse_args(argv)
    bundle=(a.generated,a.sdk,a.compiler,a.vcvars)
    if any(bundle) and not all(bundle):raise ValueError('all toolchain options required')
    if a.output.exists() or a.output.resolve() in (a.xex.resolve(),a.loader_source.resolve()):raise ValueError('output must be a new non-input path')
    from tools.research.verify_branch_ranges import image_from_xex
    data=a.xex.read_bytes();image=image_from_xex(data,a.loader_source)
    proof=verify_original(image)
    words=[0,0x80000000,1,0x007fffff,0x00800000,0x3f800000,0x7f7fffff,0x7f800000,0xff800000,0x7fc12345,0x7f812345,0xff812345]
    cases=[{'input32':f'{w:08X}','policy':n,'fpr64':f'{widen32(w,n):016X}','stored32':f'{narrow64(widen32(w,n),n):08X}'} for w in words for n in ('preserve','quiet')]
    result={'schema_version':1,'original':proof,'inputs':{str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in (a.xex,a.loader_source)},'oracle_cases':cases,'oracle_contract':'Integer IEEE RNE gradual-underflow model; explicit preserve/quiet NaN policy, not Xenon hardware/FPSCR equivalence','title_runtime_execution':'NOT-TESTED','generated_execution':'not-requested'}
    if a.generated:
        result['differential']=run_differential(a)
        result['generated_execution']='actual isolated generated-body differential; see compile/run status' 
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    d=result.get('differential',{})
    print('FLOAT_LEAF original_bytes=verified boundary=conservative20 oracle_cases=24 title_runtime=NOT-TESTED generated_compile='+str(d.get('compile_exit','not-requested'))+' generated_run='+str(d.get('run_exit','not-requested'))+' success='+str(d.get('success',True)))
    return 0 if d.get('success',True) else 1

if __name__=='__main__':raise SystemExit(main())
