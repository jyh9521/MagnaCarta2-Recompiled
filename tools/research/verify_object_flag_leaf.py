"""Hash-locked original object high-bit flag leaf; bounded original-body differential."""
from __future__ import annotations
import argparse,hashlib,json,os,random,re,struct,subprocess
from pathlib import Path
BASE=0x82000000
ENTRY=0x8233D3D8
EXPECTED=bytes.fromhex('816301bc55630ffe4e800020')
EXPECTED_SHA256='503327950481e96a1cd186562cf11bc48315b21d3b6aeae17d94b7ddd908dd30'
IMAGE_SHA256='d18d49fb2960426715ba17d61d069cce42b1eadac153af13c9395cd42b1773e9'
CONTEXT_SHA256='5f84d78c38cf626cf4c8107293cd9824f6e8cf81225f201b608505698273dc36'
FPSCR_SHA256='e1f98e71630e8dc9efaae4db831679c64273419d612256d76193fb5bd8930adb'
ADDRESSES=(0x21bc,0x2ffc,0x3000,0xfffee1bc,0xffffeffc,0xfffffffc,0,4,0x1b8,0xdffffffc,0xe0000000,0xe0000ffc)

def sha(data):return hashlib.sha256(data).hexdigest()
def uint(value,bits):
    if type(value)is not int or not 0<=value<1<<bits:raise ValueError('invalid unsigned field')
    return value

def execute(code,registers,memory):
    """Exact three-instruction leaf; ordinary aligned mapped BE32 fixture only."""
    if type(code)is not bytes or code!=EXPECTED:raise ValueError('unknown object-flag-leaf instruction template')
    if type(registers)is not list or len(registers)!=32:raise ValueError('expected32 GPRs')
    regs=[uint(v,64) for v in registers]
    if type(memory)is not dict or len(memory)>65536 or any(type(k)is not int or not 0<=k<1<<32 or type(v)is not int or not 0<=v<=255 for k,v in memory.items()):raise ValueError('invalid sparse byte memory')
    ea=((regs[3]&0xffffffff)+0x1bc)&0xffffffff
    if ea%4 or ea+4>0x100000000 or any(ea+i not in memory for i in range(4)):raise ValueError('read outside aligned explicit fixture')
    regs[11]=int.from_bytes(bytes(memory[ea+i] for i in range(4)),'big')
    regs[3]=regs[11]>>31
    return {'registers':regs,'effective_address':ea,'reads':[{'address':ea,'size':4}],'stores':[],
            'unchanged':['LR','CTR','allCR','XER','allFPR','FPSCR','vectors','memory'],
            'limits':'No fault/MMIO/unaligned/hardware-title execution model; BLR returns with LR/CTR registers unmodified'}

def verify_original(image):
    if type(image)is not bytes or sha(image)!=IMAGE_SHA256:raise ValueError('unsupported original image hash')
    off=ENTRY-BASE
    if image[off:off+12]!=EXPECTED or sha(image[off:off+12])!=EXPECTED_SHA256:raise ValueError('original object-flag-leaf bytes mismatch')
    before=image[off-16:off];after=image[off+12:off+28]
    if before.hex()!='81630000814b03207d4903a64e800420' or after.hex()!='0000000082a55aa88224cf287d8802a6':raise ValueError('original object-flag-leaf neighbor mismatch')
    pe=struct.unpack_from('<I',image,0x3c)[0];pd,size=struct.unpack_from('<II',image,pe+24+96+24)
    if size%8 or pd+size>len(image):raise ValueError('invalid original PDATA')
    containing=[]
    for pos in range(pd,pd+size,8):
        a,f=struct.unpack_from('>II',image,pos);end=a+((f>>8)&0x3fffff)*4
        if a<ENTRY+len(EXPECTED) and ENTRY<end:containing.append([a,end])
    if containing:raise ValueError('unexpected containing PDATA')
    return {'entry':ENTRY,'size':12,'bytes_hex':EXPECTED.hex(),'sha256':EXPECTED_SHA256,'containing_pdata':containing,
            'before':{'start':ENTRY-16,'bytes_hex':before.hex(),'sha256':sha(before)},'after':{'start':ENTRY+12,'bytes_hex':after.hex(),'sha256':sha(after)},
            'boundary':'conservative complete12byte leaf: LWZ/SRWI31/BLR, preceding BCTR and following zero then two address-like words before next PDATA body; no containing PDATA',
            'semantics':'EA=(rawR3.low32+0x1BC) mod2^32; BE32 zero-extends to full64r11; full64r3=word>>31; all other context and memory unchanged',
            'hardware_or_title_execution':'NOT-TESTED'}

def fixtures():
    rng=random.Random(2801)
    payloads=[0,1,0x7fffffff,0x80000000,0xffffffff,0x12345678,0x87654321,0x01020304,0xff000000,0x000000ff,0x55555555,0xaaaaaaaa]+[rng.getrandbits(32) for _ in range(116)]
    result=[]
    for payload in payloads:
        for ea in ADDRESSES:
            n=len(result);regs=[rng.getrandbits(64) for _ in range(32)];upper=0 if n==0 else 0xffffffff if n==1 else rng.getrandbits(32);regs[3]=(upper<<32)|((ea-0x1bc)&0xffffffff);memory={ea+i:b for i,b in enumerate(payload.to_bytes(4,'big'))}
            result.append({'index':n,'payload':payload,'ea':ea,'registers':regs,'memory':memory,'oracle':execute(EXPECTED,regs,memory)})
    return result


def extract_body(directory):
    found=[]
    expected='DEFINE_REX_FUNC(sub_8233D3D8){REX_FUNC_PROLOGUE();ctx.r11.u64=REX_LOAD_U32(ctx.r3.u32+444);ctx.r3.u64=__builtin_rotateleft64(ctx.r11.u32|(ctx.r11.u64<<32),1)&0x1;return;}'
    for path in sorted(Path(directory).glob('*.cpp')):
        text=path.read_text(encoding='utf-8-sig')
        for m in re.finditer(r'DEFINE_REX_FUNC\(sub_8233D3D8\) \{(.*?)\n\}',text,re.S):
            body=m[0];normalized=re.sub(r'\s+','',re.sub(r'//[^\n]*','',body))
            if normalized!=expected:raise ValueError('unexpected generated object-flag-leaf template')
            found.append({'source':str(path.resolve()),'source_sha256':sha(path.read_bytes()),'body':body,'body_sha256':sha(body.encode()),'line':text.count('\n',0,m.start())+1})
    if len(found)!=1:raise ValueError('expected one complete generated object high-bit flag leaf')
    for filename,pattern in [('mc2_probe_init.cpp',r'\{\s*0x8233D3D8,\s*(\w+)\s*\}'),('mc2_probe_register.cpp',r'registrar->SetFunction\(0x8233D3D8,\s*(\w+)\);')]:
        if re.findall(pattern,(Path(directory)/filename).read_text(encoding='utf-8-sig'))!=['sub_8233D3D8']:raise ValueError('expected unique object-flag-leaf mapping')
    pch=Path(directory)/'mc2_probe_pch.h';data=pch.read_text(encoding='utf-8-sig')
    required=('#define REX_PHYS_HOST_OFFSET(addr) (((u32)(addr) >= 0xE0000000u) ? 0x1000u : 0u)', '#define REX_LOAD_U32(x) __builtin_bswap32(*(volatile u32*)(base + (u32)(x) + REX_PHYS_HOST_OFFSET(x)))')
    if any(value not in data for value in required):raise ValueError('unsupported guest load/address mapping macro')
    found[0]['pch_sha256']=sha(pch.read_bytes());found[0]['macro_replacements']=False
    return found[0]

def harness(body,cases):
    guests=sorted({c['ea']&~4095 for c in cases});count=len(guests)
    text='#include "mc2_probe_pch.h"\n#include <windows.h>\n#include <cstdio>\n#include <cstring>\n'+body['body']+'\n'
    text+='struct Case{uint32_t ea,payload;uint64_t regs[32];};static const Case cases[]={\n'+',\n'.join('{'+f'0x{c["ea"]:08X}u,0x{c["payload"]:08X}u,'+'{'+','.join(f'0x{x:016X}ull' for x in c['registers'])+'}}' for c in cases)+'};\n'
    text+='int main(){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);constexpr uint64_t reserve=0x100001000ull;uint8_t* base=(uint8_t*)VirtualAlloc(nullptr,reserve,MEM_RESERVE,PAGE_NOACCESS);if(!base)return 2;unsigned guests[]={'+','.join(f'0x{x:08X}u' for x in guests)+'};uint64_t pages['+str(count)+'];unsigned char before['+str(count)+'][4096];for(unsigned i=0;i<'+str(count)+';i++){uint64_t expected_bias=guests[i]>=0xE0000000u?0x1000ull:0ull;if(REX_PHYS_HOST_OFFSET(guests[i])!=expected_bias){VirtualFree(base,0,MEM_RELEASE);return 5;}pages[i]=uint64_t(guests[i])+expected_bias;if(pages[i]+4096>reserve||VirtualAlloc(base+pages[i],4096,MEM_COMMIT,PAGE_READWRITE)!=base+pages[i]){VirtualFree(base,0,MEM_RELEASE);return 3;}}auto saved=PPCFPSCRRegister::Platform::getcsr();unsigned failures=0;\n'
    text+='for(unsigned n=0;n<sizeof(cases)/sizeof(cases[0]);n++){auto c=cases[n];PPCContext ctx{};for(unsigned j=0;j<sizeof(ctx);j++)((unsigned char*)&ctx)[j]=(j*7+n*13+17)%256;'
    for i in range(32):text+=f'ctx.r{i}.u64=c.regs[{i}];'
    text+='ctx.f0.u64=0x7FF0000000000001ull^n;ctx.f1.u64=0x8000000000000000ull;ctx.f2.u64=0x7FF800000000DEADull;ctx.f31.u64=0xFFF0000000000000ull;unsigned csr=0x1F80u|((n%4)<<13)|(n%2?0x8040u:0u)|(n&0x3Fu);PPCFPSCRRegister::Platform::setcsr(csr);ctx.fpscr.InitHost();PPCContext expected;std::memcpy(&expected,&ctx,sizeof(ctx));expected.r3.u64=c.payload>>31;expected.r11.u64=c.payload;for(unsigned i=0;i<'+str(count)+';i++)for(unsigned j=0;j<4096;j++)base[pages[i]+j]=(j*17+n+i)%256;auto target=base+uint64_t(c.ea)+(c.ea>=0xE0000000u?0x1000ull:0ull);for(unsigned j=0;j<4;j++)target[j]=(c.payload>>(24-j*8))&255;for(unsigned i=0;i<'+str(count)+';i++)std::memcpy(before[i],base+pages[i],4096);sub_8233D3D8(ctx,base);auto actual=PPCFPSCRRegister::Platform::getcsr();PPCFPSCRRegister::Platform::setcsr(saved);bool memory=true;for(unsigned i=0;i<'+str(count)+';i++)memory=memory&&std::memcmp(before[i],base+pages[i],4096)==0;bool context=std::memcmp(&ctx,&expected,sizeof(ctx))==0;bool good=memory&&context&&actual==csr;std::printf("OBJECT_FLAG_CASE %u raw3=%016llX ea=%08X payload=%08X r3=%016llX r11=%016llX memory=%d context=%d mxcsr=%d success=%d\\n",n,(unsigned long long)c.regs[3],c.ea,c.payload,(unsigned long long)ctx.r3.u64,(unsigned long long)ctx.r11.u64,memory,context,actual==csr,good);failures+=!good;}bool released=VirtualFree(base,0,MEM_RELEASE)!=0;PPCFPSCRRegister::Platform::setcsr(saved);std::printf("OBJECT_FLAG_MEMORY pages='+str(count)+' cases=%u released=%d failures=%u\\n",unsigned(sizeof(cases)/sizeof(cases[0])),released,failures);return failures||!released?1:0;}\n'
    return text


def assess_run(stdout,stderr,exit_status,count,pages):
    """Never infer no-fault completion from a partial stream or before exit."""
    if type(stdout)is not str or type(stderr)is not str or type(exit_status)is not int or type(count)is not int or count<=0 or type(pages)is not int or pages<=0:raise ValueError('invalid process evidence')
    lines=stdout.splitlines();pattern=r'OBJECT_FLAG_CASE (\d+) raw3=([0-9A-F]{16}) ea=([0-9A-F]{8}) payload=([0-9A-F]{8}) r3=([0-9A-F]{16}) r11=([0-9A-F]{16}) memory=([01]) context=([01]) mxcsr=([01]) success=([01])'
    rows=[re.fullmatch(pattern,line) for line in lines[:-1]] if lines else []
    expected=f'OBJECT_FLAG_MEMORY pages={pages} cases={count} released=1 failures=0'
    complete=exit_status==0 and not stderr and len(lines)==count+1 and all(rows) and [int(m[1]) for m in rows]==list(range(count)) and lines[-1]==expected
    success=complete and all(tuple(m[i] for i in (7,8,9,10))==('1','1','1','1') and int(m[4],16)<=0xffffffff and (int(m[4],16)>>31)==int(m[5],16) and int(m[4],16)==int(m[6],16) for m in rows)
    return {'completed_without_fault':bool(complete),'success':bool(success)}

def run_differential(a):
    from tools.research.compile_module import digest,inventory,vc_environment
    from tools.research.probe_route_a import CLANG_CL_SHA256
    if os.name!='nt' or digest(a.compiler)!=CLANG_CL_SHA256:raise ValueError('unsupported compiler/platform')
    context=a.sdk/'include/rex/ppc/context.h';fpscr=a.sdk/'include/rex/platform/fpscr.h'
    if digest(context)!=CONTEXT_SHA256 or digest(fpscr)!=FPSCR_SHA256:raise ValueError('unsupported SDK context/FP contract')
    output=a.output.resolve().parent/(a.output.stem+'-harness')
    if any(output==p.resolve() or p.resolve() in output.parents for p in (a.generated,a.sdk,a.compiler.parent,a.xex,a.loader_source)):raise ValueError('harness output aliases input')
    output.mkdir(parents=True,exist_ok=False);report={'success':False,'completed_without_fault':False,'scope':'Unchanged original generated leaf; aligned mapped synthetic words only, full bounded context/memory comparison; no title or hardware acceptance','title_execution':'NOT-TESTED'}
    try:
        trees=[a.generated,a.sdk/'include',a.compiler.resolve().parent.parent/'lib/clang/20/include'];before=[inventory(p) for p in trees];tools={str(p):digest(p) for p in (a.compiler,a.vcvars)};body=extract_body(a.generated);cases=fixtures();source=output/'object-flag-leaf.cpp';source.write_text(harness(body,cases),encoding='utf-8');exe=output/'object-flag-leaf.exe'
        command=[str(a.compiler.resolve()),'/nologo','/Brepro','/std:c++latest','/utf-8','/'+a.optimization,'/fp:strict','/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/EHa','/arch:AVX2','/bigobj','/MD','/I'+str((a.sdk/'include').resolve()),'/I'+str(a.generated.resolve()),str(source),'/Fo'+str(output/'object-flag-leaf.obj'),'/Fe'+str(exe),'/link','/Brepro']
        v=subprocess.run(command,cwd=output,env=vc_environment(a.vcvars.resolve()),capture_output=True,text=True,timeout=600);(output/'compile.txt').write_text(v.stdout+v.stderr,encoding='utf-8');report.update(body=body,fixtures=cases,cases=len(cases),compile_command=command,compile_exit=v.returncode,trees_before=before,toolchain_sha256=tools,harness_sha256=digest(source),macro_replacements=False,optimization=a.optimization)
        if v.returncode==0:
            run=subprocess.run([str(exe)],cwd=output,capture_output=True,text=True,timeout=60);(output/'run.txt').write_text(run.stdout+run.stderr,encoding='utf-8');pages=len({c['ea']&~4095 for c in cases});report.update(run_exit=run.returncode,literal_output=run.stdout,stderr=run.stderr,executable_sha256=digest(exe),**assess_run(run.stdout,run.stderr,run.returncode,len(cases),pages))
        report['inputs_unchanged']=all(inventory(p)==old for p,old in zip(trees,before)) and all(digest(Path(p))==value for p,value in tools.items())
        if not report['inputs_unchanged']:raise ValueError('source/header/toolchain changed')
    except Exception as error:report.update(error=f'{type(error).__name__}: {error}',success=False,completed_without_fault=False);raise
    finally:(output/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return {'path':str(output/'verification.json'),'success':report['success'],'compile_exit':report.get('compile_exit'),'run_exit':report.get('run_exit'),'completed_without_fault':report['completed_without_fault']}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('xex','loader-source','output'):p.add_argument('--'+n,type=Path,required=True)
    for n in ('generated','sdk','compiler','vcvars'):p.add_argument('--'+n,type=Path)
    p.add_argument('--optimization',choices=('Od','O2'),default='Od')
    a=p.parse_args(argv)
    if any((a.generated,a.sdk,a.compiler,a.vcvars)) and not all((a.generated,a.sdk,a.compiler,a.vcvars)):raise ValueError('all toolchain options required')
    if a.output.exists() or a.output.resolve() in (a.xex.resolve(),a.loader_source.resolve()):raise ValueError('output must be new non-input path')
    from tools.research.verify_branch_ranges import image_from_xex
    hashes={str(q):sha(q.read_bytes()) for q in (a.xex,a.loader_source)};original=verify_original(image_from_xex(a.xex.read_bytes(),a.loader_source));cases=fixtures()
    report={'schema_version':1,'original':original,'inputs':hashes,'oracle_cases':len(cases),'oracle_success':all(c['oracle']['registers'][3]==(c['payload']>>31) and c['oracle']['registers'][11]==c['payload'] for c in cases),'title_runtime_execution':'NOT-TESTED','generated_execution':'not-requested'}
    if a.generated:report['differential']=run_differential(a);report['generated_execution']='actual unchanged generated body, valid bounded memory only; process result required before PASS'
    report['inputs_unchanged']=all(sha(Path(q).read_bytes())==v for q,v in hashes.items())
    if not report['inputs_unchanged']:raise ValueError('original input changed')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2);f.write('\n')
    success=report.get('differential',{}).get('success',True);print(f'OBJECT_FLAG_LEAF original=verified cases={len(cases)} success={success} title=NOT-TESTED');return 0 if success else 1

if __name__=='__main__':raise SystemExit(main())
