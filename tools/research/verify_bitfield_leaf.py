"""Guarded original dual-return bitfield leaf and real generated differential."""
from __future__ import annotations
import argparse,hashlib,json,os,re,struct,subprocess
from pathlib import Path
BASE=0x82000000
ENTRY=0x82AC2810
EXPECTED=bytes.fromhex('81630020556abffe556bc7fe2b0a0000616300024c9a0020556307fa4e800020')
EXPECTED_SHA256='9174c77a101ea25e91a9fb0f1b8c9c7e512c4b7fdc7d80af0ce39fbfbe311f6a'
IMAGE_SHA256='d18d49fb2960426715ba17d61d069cce42b1eadac153af13c9395cd42b1773e9'

def sha(data):return hashlib.sha256(data).hexdigest()
def unsigned(value,bits):
    if type(value)is not int or not 0<=value<1<<bits:raise ValueError('invalid unsigned field')
    return value

def rotate_mask(word,shift,begin,end):
    unsigned(word,32)
    if any(type(v)is not int or not 0<=v<32 for v in (shift,begin,end)):raise ValueError('invalid rotate/mask')
    # PPC64 ROTL32 duplicates the low word, then applies MASK(MB+32,ME+32).
    repeated=(word<<32)|word
    rotated=((repeated<<shift)|(repeated>>(64-shift if shift else 64)))&0xffffffffffffffff
    begin+=32;end+=32
    mask=sum(1<<(63-i) for i in range(64) if (begin<=i<=end if begin<=end else i>=begin or i<=end))
    return rotated&mask

def execute(code,registers,cr6,xer_so,loaded_word):
    """Exact eight-word template; BE word already supplied from valid fixture."""
    if type(code)is not bytes or code!=EXPECTED:raise ValueError('unknown original instruction template')
    if type(registers)is not list or len(registers)!=32:raise ValueError('expected32 GPRs')
    regs=[unsigned(v,64) for v in registers];unsigned(cr6,4);unsigned(xer_so,1);unsigned(loaded_word,32)
    regs[11]=loaded_word
    regs[10]=rotate_mask(regs[11],23,31,31)
    regs[11]=rotate_mask(regs[11],24,31,31)
    comparison=(2 if regs[10]==0 else 4)|xer_so
    regs[3]=regs[11]|2
    early=regs[10]!=0  # Original4C9A0020: bnelr cr6, BO4/BI26.
    if not early:regs[3]=rotate_mask(regs[11],0,31,29)
    return {'registers':regs,'cr6':comparison,'return_path':'bnelr' if early else 'blr','stores':[],'unchanged':['memory','LR','CTR','XER','CR0..5/7','allFPR','FPSCR','vectors']}

def verify_original(image):
    if type(image)is not bytes or sha(image)!=IMAGE_SHA256:raise ValueError('unsupported original image hash')
    o=ENTRY-BASE
    if image[o:o+32]!=EXPECTED or sha(image[o:o+32])!=EXPECTED_SHA256:raise ValueError('original bitfield bytes mismatch')
    if image[o-4:o]!=bytes.fromhex('4e800420') or image[o+32:o+36]!=bytes.fromhex('9083003c'):raise ValueError('original bitfield boundary mismatch')
    pe=struct.unpack_from('<I',image,0x3c)[0];off,size=struct.unpack_from('<II',image,pe+24+96+24)
    if size%8 or off+size>len(image):raise ValueError('invalid original PDATA')
    containing=[]
    for pos in range(off,off+size,8):
        start,flags=struct.unpack_from('>II',image,pos);end=start+((flags>>8)&0x3fffff)*4
        if start<=ENTRY<end:containing.append([start,end])
    if containing:raise ValueError('unexpected containing PDATA')
    return {'entry':ENTRY,'size':32,'sha256':EXPECTED_SHA256,'bytes_hex':EXPECTED.hex(),'before':'4e800420','after':'9083003c','containing_pdata':containing,'boundary':'conservative dual-return32bytes, no PDATA; previous sibling bctr, next sibling stw','instructions':['lwz r11,0x20(r3)','rlwinm r10,r11,23,31,31','rlwinm r11,r11,24,31,31','cmplwi cr6,r10,0','ori r3,r11,2','bnelr cr6','rlwinm r3,r11,0,31,29','blr']}


def extract_body(directory):
    found=[]
    for p in sorted(Path(directory).glob('*.cpp')):
        text=p.read_text(encoding='utf-8-sig')
        for m in re.finditer(r'DEFINE_REX_FUNC\(sub_82AC2810\) \{(.*?)\n\}',text,re.S):
            body=m[0]
            if 'REX_FATAL' in body or 'REX_CALL' in body or 'REX_STORE_' in body or body.count('REX_LOAD_U32(')!=1 or body.count('return;')!=2:
                raise ValueError('unexpected dual-return generated shape')
            found.append({'source':str(p.resolve()),'source_sha256':sha(p.read_bytes()),'body':body,'body_sha256':sha(body.encode()),'line':text.count('\n',0,m.start())+1})
    if len(found)!=1:raise ValueError('expected one complete bitfield body')
    for filename,pattern in [('mc2_probe_init.cpp',r'\{\s*0x82AC2810,\s*(\w+)\s*\}'),('mc2_probe_register.cpp',r'registrar->SetFunction\(0x82AC2810,\s*(\w+)\);')]:
        if re.findall(pattern,(Path(directory)/filename).read_text(encoding='utf-8-sig'))!=['sub_82AC2810']:raise ValueError('expected one-to-one bitfield mapping and registration')
    return found[0]

def fixtures():
    result=[]
    for bits in range(4):
        for pattern in (0,0xffffffff,0xaaaaaaaa,0x55555555,0x80000000,0x7fffffff,0xffff,0xffff0000):
            word=(pattern&~0x300)|(bits<<8)
            for so in (0,1):
                for cr in range(16):
                    for guest in (0x2000,0xfffee000):
                        n=len(result);regs=[(0xabcdef0100000000+(j<<20)+n) &0xffffffffffffffff for j in range(32)];regs[3]=((0xffffffff00000000 if n%2 else 0x1234000000000000)|guest)
                        result.append({'index':n,'word':word,'so':so,'cr6':cr,'guest':guest,'registers':regs,'oracle':execute(EXPECTED,regs,cr,so,word)})
    return result

def harness(body,cases):
    text='#include "mc2_probe_pch.h"\n#include <windows.h>\n#include <cstdio>\n#include <cstring>\n'+body['body']+'\n'
    text+='struct Case{unsigned word,so,cr,guest;uint64_t r3;unsigned r10,r11,cr_after;};static const Case cases[]={\n'+',\n'.join('{'+','.join(f'0x{x:X}u' for x in (c['word'],c['so'],c['cr6'],c['guest'],c['oracle']['registers'][3],c['oracle']['registers'][10],c['oracle']['registers'][11],c['oracle']['cr6']))+'}' for c in cases)+'};\n'
    text+='int main(){uint8_t* base=(uint8_t*)VirtualAlloc(nullptr,0x100000000ull,MEM_RESERVE,PAGE_NOACCESS);if(!base)return 2;unsigned guests[]={0x2000u,0xFFFEE000u};unsigned pages[2];unsigned char before[2][4096];for(unsigned i=0;i<2;i++){pages[i]=guests[i]+REX_PHYS_HOST_OFFSET(guests[i]);if(VirtualAlloc(base+pages[i],4096,MEM_COMMIT,PAGE_READWRITE)!=base+pages[i]){VirtualFree(base,0,MEM_RELEASE);return 3;}}auto saved=PPCFPSCRRegister::Platform::getcsr();unsigned failures=0,early=0,late=0;\n'
    text+='for(unsigned n=0;n<sizeof(cases)/sizeof(cases[0]);n++){auto c=cases[n];PPCContext ctx{};for(unsigned j=0;j<sizeof(ctx);j++)((unsigned char*)&ctx)[j]=(j*7+n+13)%256;'
    for j in range(32):text+=f'ctx.r{j}.u64=0xABCDEF0100000000ull+({j}ull<<20)+n;'
    text+='ctx.r3.u64=(n%2?0xFFFFFFFF00000000ull:0x1234000000000000ull)|c.guest;ctx.xer.so=c.so;ctx.cr6.set_raw(c.cr);unsigned csr=0x1F80u|((n%4)<<13)|(n%2?0x8040u:0u);PPCFPSCRRegister::Platform::setcsr(csr);ctx.fpscr.InitHost();PPCContext expected;std::memcpy(&expected,&ctx,sizeof(ctx));expected.r3.u64=c.r3;expected.r10.u64=c.r10;expected.r11.u64=c.r11;expected.cr6.set_raw(c.cr_after);for(unsigned i=0;i<2;i++)for(unsigned j=0;j<4096;j++)base[pages[i]+j]=(j*17+n+i)%256;REX_STORE_U32(c.guest+0x20,c.word);for(unsigned i=0;i<2;i++)std::memcpy(before[i],base+pages[i],4096);sub_82AC2810(ctx,base);auto actual=PPCFPSCRRegister::Platform::getcsr();PPCFPSCRRegister::Platform::setcsr(saved);bool memory=true;for(unsigned i=0;i<2;i++)memory=memory&&std::memcmp(before[i],base+pages[i],4096)==0;bool context=std::memcmp(&ctx,&expected,sizeof(ctx))==0;bool good=memory&&context&&actual==csr;if(c.r10)early++;else late++;std::printf("BITFIELD_CASE %u word=%08X r3=%016llX r10=%016llX r11=%016llX cr6=%X memory=%d context=%d host=%d success=%d\\n",n,c.word,(unsigned long long)ctx.r3.u64,(unsigned long long)ctx.r10.u64,(unsigned long long)ctx.r11.u64,ctx.cr6.raw(),memory,context,actual==csr,good);failures+=!good;}bool released=VirtualFree(base,0,MEM_RELEASE)!=0;PPCFPSCRRegister::Platform::setcsr(saved);std::printf("BITFIELD_MEMORY pages=2 early=%u late=%u released=%d failures=%u\\n",early,late,released,failures);return failures||!released?1:0;}\n'
    return text

def run_differential(a):
    from tools.research.compile_module import digest,inventory,vc_environment
    from tools.research.probe_route_a import CLANG_CL_SHA256
    if os.name!='nt' or digest(a.compiler)!=CLANG_CL_SHA256:raise ValueError('unsupported compiler/platform')
    output=a.output.resolve().parent/(a.output.stem+'-harness')
    if any(output==p.resolve() or p.resolve() in output.parents for p in (a.generated,a.sdk,a.compiler.parent,a.xex,a.loader_source)):raise ValueError('harness output aliases input')
    output.mkdir(parents=True,exist_ok=False);report={'success':False,'contract':'exact32byte integer oracle, unchanged actual body and SDK macros; strict FP only preserves unrelated full-context state','title_execution':'NOT-TESTED'}
    try:
        trees=[a.generated,a.sdk/'include',a.compiler.resolve().parent.parent/'lib/clang/20/include'];before=[inventory(t) for t in trees];tools={str(p):digest(p) for p in (a.compiler,a.vcvars)}
        body=extract_body(a.generated);cases=fixtures();source=output/'bitfield.cpp';source.write_text(harness(body,cases),encoding='utf-8');exe=output/'bitfield.exe'
        command=[str(a.compiler.resolve()),'/nologo','/Brepro','/std:c++latest','/utf-8','/Od','/fp:strict','/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/EHa','/arch:AVX2','/bigobj','/MD','/I'+str((a.sdk/'include').resolve()),'/I'+str(a.generated.resolve()),str(source),'/Fo'+str(output/'bitfield.obj'),'/Fe'+str(exe),'/link','/Brepro']
        process=subprocess.run(command,cwd=output,env=vc_environment(a.vcvars.resolve()),capture_output=True,text=True,timeout=600);(output/'compile.txt').write_text(process.stdout+process.stderr,encoding='utf-8');report.update(body=body,fixtures=cases,compile_command=command,compile_exit=process.returncode,trees_before=before,toolchain_sha256=tools,harness_sha256=digest(source))
        if process.returncode==0:
            run=subprocess.run([str(exe)],cwd=output,capture_output=True,text=True,timeout=60);(output/'run.txt').write_text(run.stdout+run.stderr,encoding='utf-8');lines=run.stdout.splitlines();rows=[l for l in lines if l.startswith('BITFIELD_CASE ')];last=f'BITFIELD_MEMORY pages=2 early={len(cases)//2} late={len(cases)//2} released=1 failures=0';report.update(run_exit=run.returncode,literal_output=run.stdout,stderr=run.stderr,executable_sha256=digest(exe),success=run.returncode==0 and len(rows)==len(cases) and all(l.endswith('success=1') for l in rows) and lines[-1]==last and not run.stderr)
        report['inputs_unchanged']=all(inventory(p)==old for p,old in zip(trees,before)) and all(digest(Path(p))==h for p,h in tools.items())
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
    original=verify_original(image_from_xex(a.xex.read_bytes(),a.loader_source))
    report={'schema_version':1,'original':original,'inputs':{str(q):sha(q.read_bytes()) for q in (a.xex,a.loader_source)},'title_runtime_execution':'NOT-TESTED','generated_execution':'not-requested','oracle_cases':[execute(EXPECTED,[0xabcdef0000000000+i for i in range(32)],15,so,value<<8) for value in range(4) for so in range(2)]}
    if a.generated:
        report['differential']=run_differential(a);report['generated_execution']='actual isolated generated body differential'
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2);f.write('\n')
    success=report.get('differential',{}).get('success',True);print(f'BITFIELD_LEAF original=verified dual_return=bnelr/blr success={success} title=NOT-TESTED');return 0 if success else 1

if __name__=='__main__':raise SystemExit(main())
