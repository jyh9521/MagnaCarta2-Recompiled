"""Actual SDK movie hooks and synthetic mapped-page observations, never a title boot."""
import hashlib,json,os,re,runpy,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TRACE=ROOT/'src/host/movie_trace.h'
GUARD=ROOT/'src/host/movie_observation.h'
RANGES=[('8248FED8', 92, '4a7f4cd2d6a9f8fc71a953fee35500a38db0254a26347f8030af00a379757329'), ('82490CF0', 1708, '6e7c5b5f129520c840466fe3d7d5feb78a70b2302fb1da915197eb2bb752997b'), ('827B6148', 1780, 'ae60342fe0d36fb334c2e368d95d2f6b2d946eb15b6c10896107ee0b7e65bab0'), ('82490708', 440, '4d33acd389ee44d971ed8ba5baba665331a4cce030a4ce9b82b6f6abdc630d1a'), ('824909B8', 540, 'eb0b735269ce2e83191a34608516beb2ed9a08b4cb9d4c1ff88f24e7916d7d53'), ('82490C78', 112, 'a321e6d50740930007f9cfb6c133bce5be0f4dd665e8d3aa0d02c81a6e08fd45'), ('82491630', 648, '7d7ba336c45bb85caa99bb209085c24142f0a466d5f1d550cd3cf9a4d0af9795'), ('82491930', 668, 'fc58d69137eea7b927d5dcb29b4a2d7f63cba473aad7df656c8d58319add8b5e'), ('82491BD8', 776, '4135021e1e4702b3d2186fdb4c71fffe0acdb81c230357a20c1956debe26d690')]
TARGETS=[a for a,_,_ in RANGES]

def bodies():
    s=GUARD.read_text(encoding='utf-8')
    return [bytes(int(n,16)for n in re.findall(r'0x([0-9A-F]{2})',chunk))for chunk in re.findall(r'body\d+\[\]=\{(.*?)\};',s)]

def native_fixture(source,weak='',label='fixture'):
    from tools.research.compile_module import vc_environment
    from tools.research.probe_route_a import CLANG_CL_SHA256
    cc=ROOT/'local/upstream/llvm/unpacked/bin/clang-cl.exe';sdk=ROOT/'local/upstream/rexglue/sdk/win-amd64';pch=ROOT/'local/analysis/phase20/strict-codegen/project/generated/default-disc1'
    if os.name!='nt' or not cc.exists() or not sdk.exists() or not pch.exists():raise unittest.SkipTest('optional Windows compiler/SDK/generated PCH absent')
    assert hashlib.sha256(cc.read_bytes()).hexdigest()==CLANG_CL_SHA256
    parent=ROOT/'local/analysis/phase29';parent.mkdir(parents=True,exist_ok=True);out=Path(tempfile.mkdtemp(prefix='movie-'+label+'-',dir=parent));src=out/'main.cpp';src.write_text(source,encoding='utf-8');inputs=[TRACE,GUARD,sdk/'include/rex/hook.h',pch/'mc2_probe_pch.h'];hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in inputs}
    cmd=[str(cc),'/nologo','/std:c++latest','/EHa','/MD','/O2','/fp:strict','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/I'+str(sdk/'include'),'/I'+str(TRACE.parent),'/I'+str(pch),str(src)]
    if weak:
        p=out/'weak.cpp';p.write_text(weak,encoding='utf-8');cmd.append(str(p))
    cmd+=['/Fe'+str(out/'fixture.exe'),'/Fo'+str(out)+'\\','/link','/MAP:'+str(out/'fixture.map')]
    env=vc_environment(Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat'));rows=[]
    for command,timeout in [(cmd,120),([str(out/'fixture.exe')],40)]:
        p=subprocess.run(command,cwd=out,env=env,capture_output=True,text=True,timeout=timeout);rows.append(dict(command=command,exit=p.returncode,output=p.stdout+p.stderr));(out/'results.json').write_text(json.dumps(dict(rows=rows,inputs=hashes,inputs_unchanged=all(hashlib.sha256(Path(k).read_bytes()).hexdigest()==v for k,v in hashes.items())),indent=2),encoding='utf-8')
        if p.returncode:raise AssertionError(str(out)+'\n'+p.stdout+p.stderr)
    assert all(hashlib.sha256(Path(k).read_bytes()).hexdigest()==v for k,v in hashes.items())
    return p.stdout

class MovieTraceNativeTests(unittest.TestCase):
    def test_complete_pinned_original_hashes(self):
        bb=bodies();self.assertEqual(len(bb),9);self.assertEqual(sum(map(len,bb)),6764)
        for (a,n,h),b in zip(RANGES,bb):self.assertEqual(len(b),n);self.assertEqual(hashlib.sha256(b).hexdigest(),h);self.assertIn('ReadWord(view,0x'+a+'+uint32_t(off))',GUARD.read_text(encoding='utf-8'))
    def test_exact_targets_delegation(self):
        s=TRACE.read_text(encoding='utf-8');self.assertEqual(re.findall(r'REX_HOOK_RAW\(sub_([A-F0-9]+)\)',s),TARGETS)
        for i,a in enumerate(TARGETS):self.assertIn('Invoke<'+str(i)+'>(ctx,base,&__imp__sub_'+a+')',s)
    def test_default_off_bounded_publication(self):
        s=TRACE.read_text(encoding='utf-8')
        for token in ['active{false}','enabled&&!codeverified','configured.exchange(true)','kCount=9,kCapacity=4096','memory_order_release','memory_order_acquire','MOVIE_PENDING','fetch_or(kFrozen','suppressed.fetch_add','previous_depth','part.unwound.fetch_add','weak_snapshot=1']:self.assertIn(token,s)
    def test_readonly_no_fault_suppression(self):
        s=TRACE.read_text(encoding='utf-8')+GUARD.read_text(encoding='utf-8')
        for token in ['REX_STORE','WriteProcessMemory','VirtualProtect','SetThreadContext','catch(']:self.assertNotIn(token,s)
        self.assertIn('errno=result_errno;SetLastError(result_error)',s);self.assertIn('if(kind!=0 && kind!=2)',s)
    def test_native_actual_sdk_transparency(self):
        template=runpy.run_path(str(ROOT/'tests/test_frame_timeline_trace.py'))['MOCK'];template=template.replace('frame_timeline_trace.h','movie_trace.h').replace('frame_timeline','movie_trace').replace('FrameTimeline','MovieTrace').replace('TIMELINE','MOVIE')
        old=['8277B6D8','8244A360','8286E618','82E20568','82399778']
        for a,b in zip(old,TARGETS):template=template.replace(a,b)
        for var in ['originals','wrappers']:
            prefix='&__imp__sub_' if var=='originals' else '&sub_'
            template=re.sub(r'PPCFunc\* '+var+r'\[\]=\{.*?\};','PPCFunc* '+var+'[]={'+','.join(prefix+a for a in TARGETS)+'};',template)
        template=template.replace('kind<4','kind<8').replace('kind<5','kind<9').replace('(n+t)%5','(n+t)%9').replace('calls==5','calls==9').replace('posts==5','posts==9').replace('unwound==5','unwound==9').replace('equivalence=5 nested=5','equivalence=9 nested=9')
        extra=''.join('extern "C" void TestOriginal'+str(i)+'(PPCContext&c,uint8_t*b){Common('+str(i)+',c,b);}'for i in range(5,9));template=template.replace('void Reset(){',extra+'\nvoid Reset(){')
        weak='#include "mc2_probe_pch.h"\n'+''.join('extern "C" void TestOriginal'+str(i)+'(PPCContext&,uint8_t*);\nDEFINE_REX_FUNC(sub_'+a+'){REX_FUNC_PROLOGUE();TestOriginal'+str(i)+'(ctx,base);}\n'for i,a in enumerate(TARGETS))
        self.assertIn('MOVIE_MOCK equivalence=9 nested=9 tls=1 mxcsr=1 throw=1 concurrent=1 drop=1 suppressed=1 pending=1',native_fixture(template,weak,'transparency'))
    def test_native_pages_full_guard_and_mapping(self):
        source=PAGE_CPP
        for i,((a,n,h),b)in enumerate(zip(RANGES,bodies())):
            source=source.replace('BODY_'+str(i)+';', 'static const uint8_t body'+str(i)+'[]={'+','.join(str(x)for x in b)+'};put(0x'+a+',body'+str(i)+',sizeof(body'+str(i)+'));')
        self.assertIn('MOVIE_PAGES bytes=6764 readonly=1 fields=1 fstring=1 unknown=1 protected=1 mismatch=closed noaccess=closed',native_fixture(source,label='pages'))

PAGE_CPP=r'''
#include "movie_observation.h"
#include <cassert>
#include <cstring>
#include <set>
#include <vector>
using namespace mc2::host;
using namespace mc2::host::movie_trace;
STUBS
int main(){auto*base=(uint8_t*)VirtualAlloc(nullptr,0x84000000ULL,MEM_RESERVE,PAGE_NOACCESS);assert(base);std::set<uint32_t> pages;auto put=[&](uint32_t a,const uint8_t*b,size_t n){for(uint32_t p=a&~4095u;p<((uint64_t(a)+n+4095)&~4095ULL);p+=4096)if(pages.insert(p).second)assert(VirtualAlloc(base+p,4096,MEM_COMMIT,PAGE_READWRITE));std::memcpy(base+a,b,n);};
BODY_0;BODY_1;BODY_2;BODY_3;BODY_4;BODY_5;BODY_6;BODY_7;BODY_8;
assert(movie_observation::OriginalBytes({base,0x100001000ULL}));std::vector<uint8_t> before;for(auto p:pages)before.insert(before.end(),base+p,base+p+4096);const uint32_t sizes[]={92,1708,1780,440,540,112,648,668,776};for(size_t i=0;i<kCount;++i)for(uint32_t off:{0u,sizes[i]-1}){auto a=kTargets[i]+off;base[a]^=1;assert(!movie_observation::OriginalBytes({base,0x100001000ULL}));base[a]^=1;}size_t at=0;for(auto p:pages){assert(!std::memcmp(before.data()+at,base+p,4096));at+=4096;}
uint8_t z[4096]{};put(0x10000,z,sizeof(z));auto word=[&](uint32_t a,uint32_t v){for(unsigned i=0;i<4;++i)base[a+i]=uint8_t(v>>(24-8*i));};word(0x10038,0x81);word(0x10050,0x12345678);word(0x10058,0x55);word(0x100B8,0x10200);word(0x10204,7);word(0x10300,0x10400);base[0x10400]=0;base[0x10401]='A';base[0x10402]=0;base[0x10403]='B';base[0x10404]=0;base[0x10405]=0;std::vector<uint8_t> ram(base+0x10000,base+0x11000);
PPCContext c{};c.r3.u64=0x10000;std::array<uint64_t,8> args{};args[0]=0x10000;args[2]=0x10400;auto ctx=c;Record(1,0,1,0,1,c,base,args);auto&e=partitions[1].entries[0];assert(e.known==15&&e.words[0]==0x81&&e.words[1]==0x12345678&&e.words[2]==0x55&&e.words[3]==0x10200&&e.text_known&&e.text_count==7&&std::strcmp(e.name_status,"ok")==0&&std::strcmp(e.name_hex.data(),"004100420000")==0);assert(!std::memcmp(&ctx,&c,sizeof(c)));
args[0]=0x10200;args[1]=0x10300;Record(2,0,2,0,1,c,base,args);auto&f=partitions[2].entries[0];assert(f.known==0&&f.obj==0&&f.text_known&&f.text_count==7&&!std::strcmp(f.name_hex.data(),"004100420000"));assert(!std::memcmp(ram.data(),base+0x10000,4096));
args[0]=0x20000;args[1]=0x20000;args[2]=0x20000;Record(1,0,3,0,1,c,base,args);assert(partitions[1].entries[1].known==0&&!partitions[1].entries[1].text_known);Record(2,0,4,0,1,c,base,args);assert(!partitions[2].entries[1].text_known&&std::strcmp(partitions[2].entries[1].name_status,"not-read")!=0);
DWORD old=0;assert(VirtualProtect(base+0x10000,4096,PAGE_NOACCESS,&old));args[0]=0x10000;args[1]=0x10300;args[2]=0x10400;Record(1,0,5,0,1,c,base,args);assert(partitions[1].entries[2].known==0);Record(2,0,6,0,1,c,base,args);assert(!partitions[2].entries[2].text_known);assert(VirtualProtect(base+0x10000,4096,PAGE_READWRITE,&old));assert(!std::memcmp(ram.data(),base+0x10000,4096));
// Equivalence with actual successful mapped reads, including both result channels.
auto delegate=+[](PPCContext&x,uint8_t*b){assert(errno==EAGAIN&&GetLastError()==0x1234);x.r3.u64=0xFEDCBA9876543210ULL;x.r11.u64^=0x1234;b[0x10500]^=0x5A;errno=ERANGE;SetLastError(0x5678);};
for(unsigned mode=0;mode<2;++mode){PPCContext direct{},hooked{};for(size_t j=0;j<sizeof(direct);++j)((uint8_t*)&direct)[j]=uint8_t(j*7+3);direct.r3.u64=0x10000;direct.r5.u64=0x10400;std::memcpy(&hooked,&direct,sizeof(direct));std::memcpy(base+0x10000,ram.data(),4096);errno=EAGAIN;SetLastError(0x1234);auto csr=PPCFPSCRRegister::Platform::getcsr();delegate(direct,base);std::vector<uint8_t>expected(base+0x10000,base+0x11000);std::memcpy(base+0x10000,ram.data(),4096);active=bool(mode);errno=EAGAIN;SetLastError(0x1234);Invoke<1>(hooked,base,delegate);assert(errno==ERANGE&&GetLastError()==0x5678&&PPCFPSCRRegister::Platform::getcsr()==csr);assert(!std::memcmp(&direct,&hooked,sizeof(direct))&&!std::memcmp(expected.data(),base+0x10000,4096));}active=false;
assert(VirtualProtect(base+(kTargets[0]&~4095u),4096,PAGE_NOACCESS,&old));assert(!movie_observation::OriginalBytes({base,0x100001000ULL}));assert(VirtualFree(base,0,MEM_RELEASE));std::puts("MOVIE_PAGES bytes=6764 readonly=1 fields=1 fstring=1 unknown=1 protected=1 mismatch=closed noaccess=closed");}
'''
PAGE_CPP=PAGE_CPP.replace('STUBS','\n'.join('REX_EXTERN(__imp__sub_'+a+'){}'for a in TARGETS))
