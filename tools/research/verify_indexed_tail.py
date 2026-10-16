"""Hash-locked indexed conditional tail with exact integer/memory oracle."""
from __future__ import annotations
import argparse,hashlib,json,os,re,struct,subprocess
from pathlib import Path
BASE=0x82000000
ENTRY=0x82A3DEA0
EXPECTED=bytes.fromhex('8943003c548b063e7ca92b787cc533787f0b5040419800103c608007606300574e80002081430024556b18387ce63b787d244b787c6b502e81630000814b00107d4903a64e800420')
EXPECTED_SHA256='da78cc530445e6be3717bc6cec9e6cf949e163d65dc481ee5d6f63d4648b708a'
IMAGE_SHA256='d18d49fb2960426715ba17d61d069cce42b1eadac153af13c9395cd42b1773e9'
SDK_RUNTIME_SHA256='e359209fb2b0570e693c966d4c1d99a82465d36ef70d033833fae56adb2f1b7a'

def sha(data):return hashlib.sha256(data).hexdigest()
def unsigned(value,bits):
    if type(value)is not int or not 0<=value<1<<bits:raise ValueError('invalid unsigned field')
    return value

def put32(memory,address,value):
    unsigned(address,32);unsigned(value,32)
    if type(memory)is not dict:raise ValueError('expected sparse memory dictionary')
    if address>0xfffffffc:raise ValueError('word crosses guest boundary')
    for i,b in enumerate(value.to_bytes(4,'big')):memory[address+i]=b

def execute(code,registers,cr6,xer_so,memory,ctr):
    if type(code)is not bytes or code!=EXPECTED:raise ValueError('unknown indexed-tail instruction template')
    if type(registers)is not list or len(registers)!=32:raise ValueError('expected32 GPRs')
    regs=[unsigned(v,64) for v in registers];unsigned(cr6,4);unsigned(xer_so,1);unsigned(ctr,64)
    if type(memory)is not dict or len(memory)>65536 or any(type(k)is not int or not 0<=k<1<<32 or type(v)is not int or not 0<=v<=255 for k,v in memory.items()):raise ValueError('invalid sparse byte memory')
    reads=[]
    def read(a,n):
        a&=0xffffffff
        if a+n>0x100000000 or any(a+i not in memory for i in range(n)):raise ValueError('read outside explicit fixture')
        reads.append({'address':a,'size':n});return int.from_bytes(bytes(memory[a+i] for i in range(n)),'big')
    regs[10]=read(regs[3]+0x3c,1);regs[11]=regs[4]&255;regs[9]=regs[5];regs[5]=regs[6]
    cr=(8 if regs[11]<regs[10] else 2 if regs[11]==regs[10] else 4)|xer_so
    if regs[11]>=regs[10]:
        regs[3]=0xffffffff80070057
        return {'registers':regs,'cr6':cr,'ctr':ctr,'path':'invalid-return','tail_target':None,'reads':reads,'stores':[]}
    regs[10]=read(regs[3]+0x24,4);regs[11]=(regs[11]<<3)&0xfffffff8;regs[6]=regs[7];regs[4]=regs[9]
    regs[3]=read(regs[11]+regs[10],4);regs[11]=read(regs[3],4);regs[10]=read(regs[11]+0x10,4)
    return {'registers':regs,'cr6':cr,'ctr':regs[10],'path':'indexed-tail-boundary','tail_target':regs[10],'reads':reads,'stores':[]}

def verify_original(image):
    if type(image)is not bytes or sha(image)!=IMAGE_SHA256:raise ValueError('unsupported original image hash')
    o=ENTRY-BASE
    if image[o:o+72]!=EXPECTED or sha(image[o:o+72])!=EXPECTED_SHA256:raise ValueError('original indexed-tail bytes mismatch')
    if image[o-4:o]!=bytes.fromhex('4e800420') or image[o+72:o+76]!=bytes.fromhex('8943003c'):raise ValueError('original indexed-tail boundary mismatch')
    pe=struct.unpack_from('<I',image,0x3c)[0];pd,size=struct.unpack_from('<II',image,pe+24+96+24)
    if size%8 or pd+size>len(image):raise ValueError('invalid original PDATA')
    containing=[]
    for pos in range(pd,pd+size,8):
        a,f=struct.unpack_from('>II',image,pos);end=a+((f>>8)&0x3fffff)*4
        if a<=ENTRY<end:containing.append([a,end])
    if containing:raise ValueError('unexpected containing PDATA')
    return {'entry':ENTRY,'size':72,'bytes_hex':EXPECTED.hex(),'sha256':EXPECTED_SHA256,'before':'4e800420','after':'8943003c','containing_pdata':containing,'boundary':'conservative72bytes includes invalid BLR and valid terminal BCTR; no PDATA','selector':'low8bits of raw64r4','invalid_raw_r3':'FFFFFFFF80070057','valid':'table at object+24, entries stride8, selected pointer->vtable+10->CTR; nonlink BCTR preserves LR','callee_execution':'NOT-TESTED'}

def exhaustive_matrix():
    valid=invalid=0;regs=[0xabcdef0000000000+i for i in range(32)];regs[3]=0x1000;regs[5]=0x123456789abcdef0;regs[6]=0xfedcba9876543210;regs[7]=0x1111222233334444
    for count in range(256):
        for selector in range(256):
            regs[4]=0xfedcba9876540000|selector;mem={0x103c:count};put32(mem,0x1024,0x2000);put32(mem,0x2000+selector*8,0x3000);put32(mem,0x3000,0x4000);put32(mem,0x4010,0x82010100)
            out=execute(EXPECTED,regs,15,1,mem,0xaaaabbbbccccdddd)
            if selector<count:
                valid+=1
                if out['tail_target']!=0x82010100 or out['registers'][4:7]!=[regs[5],regs[6],regs[7]]:raise AssertionError('indexed path mismatch')
            else:
                invalid+=1
                if out['registers'][3]!=0xffffffff80070057 or out['ctr']!=0xaaaabbbbccccdddd or out['registers'][4]!=regs[4] or out['registers'][6]!=regs[6]:raise AssertionError('invalid path mismatch')
    return {'count_values':256,'selector_values':256,'cases':65536,'valid':valid,'invalid':invalid,'success':True}


CODE_BASE=0x822D0000

def extract_body(directory):
    found=[]
    for p in sorted(Path(directory).glob('*.cpp')):
        text=p.read_text(encoding='utf-8-sig')
        for m in re.finditer(r'DEFINE_REX_FUNC\(sub_82A3DEA0\) \{(.*?)\n\}',text,re.S):
            body=m[0]
            if 'REX_FATAL' in body or 'REX_STORE_' in body or body.count('REX_CALL_INDIRECT_FUNC(')!=1 or body.count('return;')!=2:
                raise ValueError('unexpected indexed-tail generated shape')
            found.append({'source':str(p.resolve()),'source_sha256':sha(p.read_bytes()),'body':body,'body_sha256':sha(body.encode()),'line':text.count('\n',0,m.start())+1})
    if len(found)!=1:raise ValueError('expected one complete indexed-tail body')
    for f,pattern in [('mc2_probe_init.cpp',r'\{\s*0x82A3DEA0,\s*(\w+)\s*\}'),('mc2_probe_register.cpp',r'registrar->SetFunction\(0x82A3DEA0,\s*(\w+)\);')]:
        if re.findall(pattern,(Path(directory)/f).read_text(encoding='utf-8-sig'))!=['sub_82A3DEA0']:raise ValueError('expected one-to-one indexed-tail mapping')
    pch=Path(directory)/'mc2_probe_pch.h';text=pch.read_text(encoding='utf-8-sig')
    constants={}
    for key in ('REX_CODE_BASE','REX_CODE_SIZE','REX_IMAGE_BASE','REX_IMAGE_SIZE'):
        matches=re.findall(r'^#define '+key+r' (0x[0-9A-Fa-f]+)ull$',text,re.M)
        if len(matches)!=1:raise ValueError('missing/ambiguous module constant')
        constants[key]=int(matches[0],16)
    if constants!={'REX_CODE_BASE':CODE_BASE,'REX_CODE_SIZE':0xBCE5A4,'REX_IMAGE_BASE':BASE,'REX_IMAGE_SIZE':0x1330000}:raise ValueError('unsupported dispatch layout')
    found[0].update(pch_sha256=sha(pch.read_bytes()),module_constants=constants)
    return found[0]

def fixtures():
    rows=[]
    for count in (0,1,2,127,128,254,255):
        for selector in (0,1,2,126,127,128,253,254,255):
            for so in (0,1):
                for high in (0,0xabcdef0000000000,0xffffffff00000000,0x8000000000000000):
                    for upper in (False,True):
                        n=len(rows);obj,table,selected,vtable=(0xfffee000,0xfffec000,0xfffea000,0xfffe8000) if upper else (0x2000,0x4000,0x6000,0x8000);target=CODE_BASE+0x100+(n%4)*0x100;regs=[0xabcdef0100000000+(i<<20)+n for i in range(32)];regs[3]=(0x1234000000000000 if not upper else 0xffffeeee00000000)|obj;regs[4]=high|0xa5a5a500|selector
                        mem={obj+0x3c:count};put32(mem,obj+0x24,table);put32(mem,table+selector*8,selected);put32(mem,selected,vtable);put32(mem,vtable+0x10,target);cr=n%16;ctr=0xddddeeeeffff0000+n
                        rows.append({'index':n,'count':count,'selector':selector,'raw_r4':regs[4],'so':so,'cr6':cr,'obj':obj,'table':table,'selected':selected,'vtable':vtable,'target':target,'registers':regs,'ctr':ctr,'memory':mem,'oracle':execute(EXPECTED,regs,cr,so,mem,ctr)})
    return rows

def harness(body,cases):
    text='#include "mc2_probe_pch.h"\n#include <windows.h>\n#include <cstdio>\n#include <cstring>\nstatic PPCContext boundary;static unsigned calls;static bool boundary_memory;static unsigned pages[9];static unsigned char before[9][4096];\n'
    text+='// Synthetic mapped dispatch observer ONLY; original callee never executes.\nstatic void Observe(PPCContext& ctx,uint8_t* base){calls++;std::memcpy(&boundary,&ctx,sizeof(ctx));boundary_memory=true;for(unsigned i=0;i<9;i++)boundary_memory=boundary_memory&&std::memcmp(before[i],base+pages[i],4096)==0;}\n'+body['body']+'\n'
    text+='struct Case{unsigned count,selector,so,cr,obj,table,selected,vtable,target;uint64_t raw4,r3,r4,r5,r6,r9,r10,r11,ctr;unsigned cr_after;};static const Case cases[]={\n'
    text+=',\n'.join('{'+','.join(f'0x{c[k]:X}u' for k in ('count','selector','so','cr6','obj','table','selected','vtable','target'))+','+','.join(f'0x{x:016X}ull' for x in (c['raw_r4'],*(c['oracle']['registers'][i] for i in (3,4,5,6,9,10,11)),c['oracle']['ctr']))+f',0x{c["oracle"]["cr6"]:X}u'+'}' for c in cases)+'};\n'
    text+='int main(){char dll[2048];wchar_t wide[1024];auto module=GetModuleHandleW(L"rexruntime.dll");if(!module||!GetModuleFileNameW(module,wide,1024)||!WideCharToMultiByte(CP_UTF8,0,wide,-1,dll,sizeof(dll),nullptr,nullptr))return 4;std::printf("INDEXED_RUNTIME path=%s\\n",dll);uint8_t* base=(uint8_t*)VirtualAlloc(nullptr,0x100000000ull,MEM_RESERVE,PAGE_NOACCESS);if(!base)return 2;unsigned guests[]={0x2000u,0x4000u,0x6000u,0x8000u,0xFFFEE000u,0xFFFEC000u,0xFFFEA000u,0xFFFE8000u};for(unsigned i=0;i<8;i++)pages[i]=guests[i]+REX_PHYS_HOST_OFFSET(guests[i]);pages[8]=(REX_IMAGE_BASE+REX_IMAGE_SIZE)&~4095ull;for(auto page:pages)if(VirtualAlloc(base+page,4096,MEM_COMMIT,PAGE_READWRITE)!=base+page){VirtualFree(base,0,MEM_RELEASE);return 3;}for(unsigned i=1;i<=4;i++)REX_LOOKUP_FUNC(base,REX_CODE_BASE+i*0x100)=&Observe;auto saved=PPCFPSCRRegister::Platform::getcsr();unsigned failures=0,invalid=0,tails=0;\n'
    text+='for(unsigned n=0;n<sizeof(cases)/sizeof(cases[0]);n++){auto c=cases[n];PPCContext ctx{};for(unsigned j=0;j<sizeof(ctx);j++)((unsigned char*)&ctx)[j]=(j*7+n+13)%256;'
    for i in range(32):text+=f'ctx.r{i}.u64=0xABCDEF0100000000ull+({i}ull<<20)+n;'
    text+='ctx.r3.u64=(c.obj==0x2000?0x1234000000000000ull:0xFFFFEEEE00000000ull)|c.obj;ctx.r4.u64=c.raw4;ctx.ctr.u64=0xDDDDEEEEFFFF0000ull+n;ctx.xer.so=c.so;ctx.cr6.set_raw(c.cr);unsigned csr=0x1F80u|((n%4)<<13)|(n%2?0x8040u:0u);PPCFPSCRRegister::Platform::setcsr(csr);ctx.fpscr.InitHost();PPCContext expected;std::memcpy(&expected,&ctx,sizeof(ctx));expected.r3.u64=c.r3;expected.r4.u64=c.r4;expected.r5.u64=c.r5;expected.r6.u64=c.r6;expected.r9.u64=c.r9;expected.r10.u64=c.r10;expected.r11.u64=c.r11;expected.ctr.u64=c.ctr;expected.cr6.set_raw(c.cr_after);for(unsigned i=0;i<8;i++)for(unsigned j=0;j<4096;j++)base[pages[i]+j]=(j*17+n+i)%256;REX_STORE_U8(c.obj+0x3C,c.count);REX_STORE_U32(c.obj+0x24,c.table);REX_STORE_U32(c.table+c.selector*8,c.selected);REX_STORE_U32(c.selected,c.vtable);REX_STORE_U32(c.vtable+0x10,c.target);for(unsigned i=0;i<9;i++)std::memcpy(before[i],base+pages[i],4096);calls=0;boundary_memory=false;sub_82A3DEA0(ctx,base);auto actual=PPCFPSCRRegister::Platform::getcsr();PPCFPSCRRegister::Platform::setcsr(saved);bool memory=true;for(unsigned i=0;i<9;i++)memory=memory&&std::memcmp(before[i],base+pages[i],4096)==0;bool context=std::memcmp(&ctx,&expected,sizeof(ctx))==0;bool valid=c.selector<c.count;bool abi=valid?calls==1&&boundary_memory&&std::memcmp(&boundary,&expected,sizeof(ctx))==0:calls==0;bool good=memory&&context&&abi&&actual==csr;if(valid)tails++;else invalid++;std::printf("INDEXED_CASE %u valid=%d raw4=%016llX r3=%016llX ctr=%016llX calls=%u memory=%d context=%d abi=%d host=%d success=%d\\n",n,valid,(unsigned long long)c.raw4,(unsigned long long)ctx.r3.u64,(unsigned long long)ctx.ctr.u64,calls,memory,context,abi,actual==csr,good);failures+=!good;}bool released=VirtualFree(base,0,MEM_RELEASE)!=0;PPCFPSCRRegister::Platform::setcsr(saved);std::printf("INDEXED_MEMORY pages=9 invalid=%u tail_boundary=%u released=%d failures=%u\\n",invalid,tails,released,failures);return failures||!released?1:0;}\n'
    return text

def run_differential(a):
    from tools.research.compile_module import digest,inventory,vc_environment
    from tools.research.probe_route_a import CLANG_CL_SHA256
    runtime=a.sdk/'bin/rexruntime.dll';library=a.sdk/'lib/rexruntime.lib';tracy=a.sdk/'bin/TracyClient.dll'
    if os.name!='nt' or digest(a.compiler)!=CLANG_CL_SHA256 or digest(runtime)!=SDK_RUNTIME_SHA256:raise ValueError('unsupported compiler/runtime/platform')
    output=a.output.resolve().parent/(a.output.stem+'-harness')
    if any(output==p.resolve() or p.resolve() in output.parents for p in (a.generated,a.sdk,a.compiler.parent,a.xex,a.loader_source)):raise ValueError('harness output aliases input')
    output.mkdir(parents=True,exist_ok=False);report={'success':False,'scope':'Actual unchanged entry and dispatch macro, full invalid return; valid synthetic mapped dispatch observer records complete boundary context/memory ONLY. No original callee execution.','title_execution':'NOT-TESTED','callee_execution':'NOT-TESTED'}
    try:
        trees=[a.generated,a.sdk/'include',a.compiler.resolve().parent.parent/'lib/clang/20/include'];before=[inventory(p) for p in trees];tools={str(p):digest(p) for p in (a.compiler,a.vcvars,runtime,library,tracy)};body=extract_body(a.generated);cases=fixtures();source=output/'indexed-tail.cpp';source.write_text(harness(body,cases),encoding='utf-8');exe=output/'indexed-tail.exe'
        command=[str(a.compiler.resolve()),'/nologo','/Brepro','/std:c++latest','/utf-8','/Od','/fp:strict','/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/EHa','/arch:AVX2','/bigobj','/MD','/I'+str((a.sdk/'include').resolve()),'/I'+str(a.generated.resolve()),str(source),'/Fo'+str(output/'indexed-tail.obj'),'/Fe'+str(exe),'/link','/Brepro',str(library.resolve())]
        env=vc_environment(a.vcvars.resolve());v=subprocess.run(command,cwd=output,env=env,capture_output=True,text=True,timeout=600);(output/'compile.txt').write_text(v.stdout+v.stderr,encoding='utf-8');report.update(body=body,fixtures=cases,compile_command=command,compile_exit=v.returncode,trees_before=before,toolchain_runtime_sha256=tools,harness_sha256=digest(source),macro_replacements=False)
        if v.returncode==0:
            key=next((k for k in env if k.upper()=='PATH'),'PATH');env[key]=str((a.sdk/'bin').resolve())+os.pathsep+env.get(key,'');run=subprocess.run([str(exe)],cwd=output,env=env,capture_output=True,text=True,encoding='utf-8',timeout=60);(output/'run.txt').write_text(run.stdout+run.stderr,encoding='utf-8');lines=run.stdout.splitlines();rows=[line for line in lines if line.startswith('INDEXED_CASE ')];tails=sum(c['selector']<c['count'] for c in cases);last=f'INDEXED_MEMORY pages=9 invalid={len(cases)-tails} tail_boundary={tails} released=1 failures=0';dllpaths=re.findall(r'^INDEXED_RUNTIME path=(.+)$',run.stdout,re.M);identity=len(dllpaths)==1 and Path(dllpaths[0]).resolve()==runtime.resolve() and digest(runtime)==SDK_RUNTIME_SHA256;report.update(run_exit=run.returncode,literal_output=run.stdout,stderr=run.stderr,executable_sha256=digest(exe),loaded_runtime_path_verified=identity,success=run.returncode==0 and len(rows)==len(cases) and all(line.endswith('success=1') for line in rows) and lines[-1]==last and identity and not run.stderr)
        report['inputs_unchanged']=all(inventory(p)==old for p,old in zip(trees,before)) and all(digest(Path(p))==v for p,v in tools.items())
        if not report['inputs_unchanged']:raise ValueError('source/header/toolchain/runtime changed')
    except Exception as error:report.update(error=f'{type(error).__name__}: {error}',success=False);raise
    finally:(output/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return {'path':str(output/'verification.json'),'success':report['success'],'compile_exit':report.get('compile_exit'),'run_exit':report.get('run_exit')}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('xex','loader-source','output'):p.add_argument('--'+n,type=Path,required=True)
    for n in ('generated','sdk','compiler','vcvars'):p.add_argument('--'+n,type=Path)
    a=p.parse_args(argv)
    if any((a.generated,a.sdk,a.compiler,a.vcvars)) and not all((a.generated,a.sdk,a.compiler,a.vcvars)):raise ValueError('all toolchain options required')
    if a.output.exists() or a.output.resolve() in (a.xex.resolve(),a.loader_source.resolve()):raise ValueError('output must be new non-input path')
    from tools.research.verify_branch_ranges import image_from_xex
    hashes={str(q):sha(q.read_bytes()) for q in (a.xex,a.loader_source)};original=verify_original(image_from_xex(a.xex.read_bytes(),a.loader_source));report={'schema_version':1,'original':original,'inputs':hashes,'exhaustive':exhaustive_matrix(),'title_runtime_execution':'NOT-TESTED','callee_execution':'NOT-TESTED','generated_execution':'not-requested'}
    if a.generated:report['differential']=run_differential(a);report['generated_execution']='actual body, full invalid return or observed mapped synthetic tail boundary; callee not executed'
    report['inputs_unchanged']=all(sha(Path(q).read_bytes())==h for q,h in hashes.items())
    if not report['inputs_unchanged']:raise ValueError('original input changed')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2);f.write('\n')
    success=report.get('differential',{}).get('success',True);print(f'INDEXED_TAIL original=verified exhaustive=65536 success={success} callee=NOT-TESTED title=NOT-TESTED');return 0 if success else 1

if __name__=='__main__':raise SystemExit(main())
