"""Original conditional-return/direct-tail verifier with explicit tail boundary."""
from __future__ import annotations
import argparse,hashlib,json,os,re,struct,subprocess
from pathlib import Path
BASE=0x82000000
ENTRY=0x826A9EC8
TAIL=0x826C9920
EXPECTED=bytes.fromhex('814301087c6b1b7880630080554900c22b030000912b01084d9a00204801fa3c')
EXPECTED_SHA256='8b4df364b42994f970049966b3a8c5db4528bc3c6a18c3f7cd2a78b35d0501a7'
IMAGE_SHA256='d18d49fb2960426715ba17d61d069cce42b1eadac153af13c9395cd42b1773e9'

def sha(data):return hashlib.sha256(data).hexdigest()
def unsigned(value,bits):
    if type(value)is not int or not 0<=value<1<<bits:raise ValueError('invalid unsigned field')
    return value

def rotate_mask(word):
    """PPC64 ROTL32(word,0) & MASK(35,33), not zero-extended MASK32."""
    unsigned(word,32)
    repeated=(word<<32)|word
    mask=sum(1<<(63-i) for i in range(64) if i>=35 or i<=33)
    return repeated&mask

def execute(code,registers,cr6,xer_so,flags,member):
    if type(code)is not bytes or code!=EXPECTED:raise ValueError('unknown original instruction template')
    if type(registers)is not list or len(registers)!=32:raise ValueError('expected32 GPRs')
    regs=[unsigned(v,64) for v in registers];unsigned(cr6,4);unsigned(xer_so,1);unsigned(flags,32);unsigned(member,32)
    original_object=regs[3];regs[10]=flags;regs[11]=regs[3];regs[3]=member;regs[9]=rotate_mask(regs[10]);comparison=(2 if regs[3]==0 else 4)|xer_so
    store={'address':((original_object&0xffffffff)+0x108)&0xffffffff,'value':regs[9]&0xffffffff}
    return {'registers':regs,'cr6':comparison,'stores':[store],'return_path':'beqlr' if member==0 else 'direct-tail','tail_target':None if member==0 else TAIL,'unchanged':['LR','CTR','XER','otherCR','allFPR','FPSCR','vectors'],'ordering':['read flags object+108','copy full64 object to r11','read member object+80 to r3','rotate/mask64 into r9','unsigned compare member in CR6','store low32 r9 to object+108','beqlr if null else direct nonlink tail']}

def verify_original(image):
    if type(image)is not bytes or sha(image)!=IMAGE_SHA256:raise ValueError('unsupported original image hash')
    off=ENTRY-BASE
    if image[off:off+32]!=EXPECTED or sha(image[off:off+32])!=EXPECTED_SHA256:raise ValueError('original conditional-tail bytes mismatch')
    if image[off-4:off]!=bytes.fromhex('4e800420') or image[off+32:off+36]!=bytes.fromhex('4e800020'):raise ValueError('original conditional-tail boundary mismatch')
    branch=struct.unpack_from('>I',image,off+28)[0];disp=branch&0x3fffffc
    if disp&0x2000000:disp-=0x4000000
    if branch>>26!=18 or branch&3 or ENTRY+28+disp!=TAIL:raise ValueError('expected terminal direct nonlink branch')
    pe=struct.unpack_from('<I',image,0x3c)[0];pdata,size=struct.unpack_from('<II',image,pe+24+96+24)
    if size%8 or pdata+size>len(image):raise ValueError('invalid original PDATA')
    containing=[];tail=[]
    for p in range(pdata,pdata+size,8):
        a,f=struct.unpack_from('>II',image,p);end=a+((f>>8)&0x3fffff)*4
        if a<=ENTRY<end:containing.append([a,end])
        if a<=TAIL<end:tail.append([a,end])
    if containing:raise ValueError('unexpected containing PDATA')
    return {'entry':ENTRY,'size':32,'bytes_hex':EXPECTED.hex(),'sha256':EXPECTED_SHA256,'before_word':'4e800420','after_word':'4e800020','containing_pdata':containing,'terminal_tail':TAIL,'tail_containing_pdata':tail,'boundary':'conservative32bytes through terminal nonlink branch; not PDATA-derived','full64_mask':'FFFFFFFFDFFFFFFF','conditional':'4D9A0020 beqlr cr6 (BO12 BI26 LK0), not bnelr','tail_execution':'NOT-TESTED'}


def extract_body(directory):
    found=[]
    for path in sorted(Path(directory).glob('*.cpp')):
        text=path.read_text(encoding='utf-8-sig')
        for match in re.finditer(r'DEFINE_REX_FUNC\(sub_826A9EC8\) \{(.*?)\n\}',text,re.S):
            body=match[0]
            if 'REX_FATAL' in body or body.count('REX_LOAD_U32(')!=2 or body.count('REX_STORE_U32(')!=1 or body.count('sub_826C9920(ctx, base);')!=1 or body.count('return;')!=2 or 'REX_CALL_INDIRECT_FUNC' in body:
                raise ValueError('unexpected conditional-tail generated shape')
            found.append({'source':str(path.resolve()),'source_sha256':sha(path.read_bytes()),'body':body,'body_sha256':sha(body.encode()),'line':text.count('\n',0,match.start())+1})
    if len(found)!=1:raise ValueError('expected one complete conditional-tail body')
    for filename,pattern in [('mc2_probe_init.cpp',r'\{\s*0x{address},\s*(\w+)\s*\}'),('mc2_probe_register.cpp',r'registrar->SetFunction\(0x{address},\s*(\w+)\);')]:
        text=(Path(directory)/filename).read_text(encoding='utf-8-sig')
        for address in (ENTRY,TAIL):
            if re.findall(pattern.replace('{address}',f'{address:08X}'),text)!=[f'sub_{address:08X}']:raise ValueError('expected unique entry and mapped tail registration')
    found[0]['tail_mapped_but_not_executed']=True
    return found[0]

def fixtures():
    rows=[]
    for flags in (0,1,0xffffffff,0xaaaaaaaa,0x55555555,0x20000000,0xdfffffff,0x80000000):
        for member in (0,1,0x2000,0xfffee000,0xffffffff):
            for so in (0,1):
                for cr in range(16):
                    for guest in (0x2000,0xfffee000):
                        n=len(rows);regs=[0xabcdef0100000000+(i<<20)+n for i in range(32)];regs[3]=(0xffffffff00000000 if n%2 else 0x1234000000000000)|guest
                        rows.append({'index':n,'flags':flags,'member':member,'so':so,'cr6':cr,'guest':guest,'registers':regs,'oracle':execute(EXPECTED,regs,cr,so,flags,member)})
    return rows

def harness(body,cases):
    text='#include "mc2_probe_pch.h"\n#include <windows.h>\n#include <cstdio>\n#include <cstring>\nstatic PPCContext boundary;static unsigned calls,object_guest,observed_flags;\n'
    text+='// External tail ABI observer ONLY: no original tail body execution or emulation.\nDEFINE_REX_FUNC(sub_826C9920){calls++;std::memcpy(&boundary,&ctx,sizeof(ctx));observed_flags=REX_LOAD_U32(object_guest+0x108);}\n'+body['body']+'\n'
    text+='struct Case{unsigned flags,member,so,cr,guest;uint64_t r9;unsigned cr_after;};static const Case cases[]={\n'+',\n'.join('{'+','.join(f'0x{x:X}u' for x in (c['flags'],c['member'],c['so'],c['cr6'],c['guest']))+f',0x{c["oracle"]["registers"][9]:016X}ull,0x{c["oracle"]["cr6"]:X}u'+'}' for c in cases)+'};\n'
    text+='int main(){uint8_t* base=(uint8_t*)VirtualAlloc(nullptr,0x100000000ull,MEM_RESERVE,PAGE_NOACCESS);if(!base)return 2;unsigned guests[]={0x2000u,0xFFFEE000u},pages[2];unsigned char before[2][4096];for(unsigned i=0;i<2;i++){pages[i]=guests[i]+REX_PHYS_HOST_OFFSET(guests[i]);if(VirtualAlloc(base+pages[i],4096,MEM_COMMIT,PAGE_READWRITE)!=base+pages[i]){VirtualFree(base,0,MEM_RELEASE);return 3;}}auto saved=PPCFPSCRRegister::Platform::getcsr();unsigned failures=0,nulls=0,tails=0;\n'
    text+='for(unsigned n=0;n<sizeof(cases)/sizeof(cases[0]);n++){auto c=cases[n];PPCContext ctx{};for(unsigned j=0;j<sizeof(ctx);j++)((unsigned char*)&ctx)[j]=(j*7+n+13)%256;'
    for i in range(32):text+=f'ctx.r{i}.u64=0xABCDEF0100000000ull+({i}ull<<20)+n;'
    text+='ctx.r3.u64=(n%2?0xFFFFFFFF00000000ull:0x1234000000000000ull)|c.guest;ctx.xer.so=c.so;ctx.cr6.set_raw(c.cr);unsigned csr=0x1F80u|((n%4)<<13)|(n%2?0x8040u:0u);PPCFPSCRRegister::Platform::setcsr(csr);ctx.fpscr.InitHost();PPCContext expected;std::memcpy(&expected,&ctx,sizeof(ctx));expected.r11.u64=ctx.r3.u64;expected.r3.u64=c.member;expected.r10.u64=c.flags;expected.r9.u64=c.r9;expected.cr6.set_raw(c.cr_after);for(unsigned i=0;i<2;i++)for(unsigned j=0;j<4096;j++)base[pages[i]+j]=(j*17+n+i)%256;REX_STORE_U32(c.guest+0x108,c.flags);REX_STORE_U32(c.guest+0x80,c.member);for(unsigned i=0;i<2;i++)std::memcpy(before[i],base+pages[i],4096);for(unsigned j=0;j<4;j++)before[c.guest==0x2000?0:1][0x108+j]=(c.r9>>(24-j*8))&255;calls=0;object_guest=c.guest;observed_flags=0;sub_826A9EC8(ctx,base);auto actual=PPCFPSCRRegister::Platform::getcsr();PPCFPSCRRegister::Platform::setcsr(saved);bool memory=true;for(unsigned i=0;i<2;i++)memory=memory&&std::memcmp(before[i],base+pages[i],4096)==0;bool context=std::memcmp(&ctx,&expected,sizeof(ctx))==0;bool abi=c.member?calls==1&&std::memcmp(&boundary,&expected,sizeof(ctx))==0&&observed_flags==(uint32_t)c.r9:calls==0;bool good=memory&&context&&abi&&actual==csr;if(c.member)tails++;else nulls++;std::printf("CONDITIONAL_CASE %u null=%d r3=%016llX r9=%016llX r10=%016llX r11=%016llX cr6=%X calls=%u flags=%08X memory=%d context=%d abi=%d host=%d success=%d\\n",n,c.member==0,(unsigned long long)ctx.r3.u64,(unsigned long long)ctx.r9.u64,(unsigned long long)ctx.r10.u64,(unsigned long long)ctx.r11.u64,ctx.cr6.raw(),calls,REX_LOAD_U32(c.guest+0x108),memory,context,abi,actual==csr,good);failures+=!good;}bool released=VirtualFree(base,0,MEM_RELEASE)!=0;PPCFPSCRRegister::Platform::setcsr(saved);std::printf("CONDITIONAL_MEMORY pages=2 null=%u tail_boundary=%u released=%d failures=%u\\n",nulls,tails,released,failures);return failures||!released?1:0;}\n'
    return text

def run_differential(a):
    from tools.research.compile_module import digest,inventory,vc_environment
    from tools.research.probe_route_a import CLANG_CL_SHA256
    if os.name!='nt' or digest(a.compiler)!=CLANG_CL_SHA256:raise ValueError('unsupported compiler/platform')
    output=a.output.resolve().parent/(a.output.stem+'-harness')
    if any(output==p.resolve() or p.resolve() in output.parents for p in (a.generated,a.sdk,a.compiler.parent,a.xex,a.loader_source)):raise ValueError('harness output aliases input')
    output.mkdir(parents=True,exist_ok=False);report={'success':False,'scope':'Unchanged generated entry, null full return; nonnull external direct-tail ABI boundary RECORDED ONLY. Original tail body not executed.','title_execution':'NOT-TESTED','tail_callee_execution':'NOT-TESTED'}
    try:
        trees=[a.generated,a.sdk/'include',a.compiler.resolve().parent.parent/'lib/clang/20/include'];before=[inventory(p) for p in trees];tools={str(p):digest(p) for p in (a.compiler,a.vcvars)};body=extract_body(a.generated);cases=fixtures();source=output/'conditional-tail.cpp';source.write_text(harness(body,cases),encoding='utf-8');exe=output/'conditional-tail.exe'
        command=[str(a.compiler.resolve()),'/nologo','/Brepro','/std:c++latest','/utf-8','/Od','/fp:strict','/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/EHa','/arch:AVX2','/bigobj','/MD','/I'+str((a.sdk/'include').resolve()),'/I'+str(a.generated.resolve()),str(source),'/Fo'+str(output/'conditional-tail.obj'),'/Fe'+str(exe),'/link','/Brepro']
        v=subprocess.run(command,cwd=output,env=vc_environment(a.vcvars.resolve()),capture_output=True,text=True,timeout=600);(output/'compile.txt').write_text(v.stdout+v.stderr,encoding='utf-8');report.update(body=body,fixtures=cases,compile_command=command,compile_exit=v.returncode,trees_before=before,toolchain_sha256=tools,harness_sha256=digest(source))
        if v.returncode==0:
            run=subprocess.run([str(exe)],cwd=output,capture_output=True,text=True,timeout=60);(output/'run.txt').write_text(run.stdout+run.stderr,encoding='utf-8');lines=run.stdout.splitlines();rows=[line for line in lines if line.startswith('CONDITIONAL_CASE ')];nulls=sum(c['member']==0 for c in cases);last=f'CONDITIONAL_MEMORY pages=2 null={nulls} tail_boundary={len(cases)-nulls} released=1 failures=0';report.update(run_exit=run.returncode,literal_output=run.stdout,stderr=run.stderr,executable_sha256=digest(exe),success=run.returncode==0 and len(rows)==len(cases) and all(line.endswith('success=1') for line in rows) and lines[-1]==last and not run.stderr)
        report['inputs_unchanged']=all(inventory(p)==old for p,old in zip(trees,before)) and all(digest(Path(p))==v for p,v in tools.items())
        if not report['inputs_unchanged']:raise ValueError('source/header/toolchain changed')
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
    input_hashes={str(q):sha(q.read_bytes()) for q in (a.xex,a.loader_source)}
    original=verify_original(image_from_xex(a.xex.read_bytes(),a.loader_source))
    report={'schema_version':1,'original':original,'inputs':input_hashes,'title_runtime_execution':'NOT-TESTED','generated_execution':'not-requested','tail_callee_execution':'NOT-TESTED'}
    if a.generated:report['differential']=run_differential(a);report['generated_execution']='actual generated entry, null return or explicitly RECORDED external tail boundary; callee not executed'
    report['inputs_unchanged']=all(sha(Path(q).read_bytes())==h for q,h in input_hashes.items())
    if not report['inputs_unchanged']:raise ValueError('original input changed')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2);f.write('\n')
    success=report.get('differential',{}).get('success',True);print(f'CONDITIONAL_TAIL original=verified mask64=FFFFFFFFDFFFFFFF success={success} tail_callee=NOT-TESTED title=NOT-TESTED');return 0 if success else 1

if __name__=='__main__':raise SystemExit(main())
