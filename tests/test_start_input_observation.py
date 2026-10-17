"""Full pinned-original range gates, tested on synthetic private pages."""
import hashlib,json,os,re,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];HEADER=ROOT/'src/host/start_input_observation.h'
class StartInputObservationTests(unittest.TestCase):
    def test_ranges_complete(self):
        pairs=re.findall(r'\{0x([0-9A-F]{8}),0x([0-9A-F]{8})\}',HEADER.read_text(encoding='utf-8'))
        self.assertEqual(len(pairs),456);addresses=[int(x,16)for x,_ in pairs];self.assertEqual(len(set(addresses)),456)
        for start,size in [(0x827B4B40,0x50C),(0x827B4938,0x208),(0x82868178,0xC)]:
            self.assertTrue(set(range(start,start+size,4))<=set(addresses))
    def test_readonly_guard(self):
        s=HEADER.read_text(encoding='utf-8');self.assertIn('schedule_observation::Read',s);self.assertIn('word!=g[1]',s);self.assertNotIn('REX_STORE',s);self.assertNotIn('WriteProcessMemory',s)
    def test_integration_inputs_hashed(self):
        s=(ROOT/'tools/research/probe_title_entry.py').read_text(encoding='utf-8');self.assertIn("['input_state_trace.h','start_event_trace.h','start_input_observation.h','scripted_controller_probe.h']",s);self.assertIn("input_observer_headers(args.source)",s);self.assertIn("dependencies.extend(input_headers)",s);self.assertIn("dependencies.append(args.source.parent/'guest_output_capture.h')",s)
    @unittest.skipUnless(os.name=='nt'and(ROOT/'local/upstream/rexglue/sdk/win-amd64/include').exists(),'local Windows SDK fixture')
    def test_native_guard_pages(self):
        from tools.research.compile_module import vc_environment
        from tools.research.probe_route_a import CLANG_CL_SHA256
        cc=ROOT/'local/upstream/llvm/unpacked/bin/clang-cl.exe';self.assertEqual(hashlib.sha256(cc.read_bytes()).hexdigest(),CLANG_CL_SHA256)
        parent=ROOT/'local/analysis/phase26';parent.mkdir(parents=True,exist_ok=True);out=Path(tempfile.mkdtemp(prefix='input-read-',dir=parent));g=HEADER.read_text(encoding='utf-8').split('guards[][2]={',1)[1].split(' };',1)[0];source=out/'fixture.cpp';source.write_text(CPP.replace('GUARDS_HERE',g),encoding='utf-8')
        cmd=[str(cc),'/nologo','/std:c++latest','/EHa','/MD','/O2','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/DSPDLOG_FMT_EXTERNAL','/DSPDLOG_COMPILED_LIB','/I'+str(ROOT/'local/upstream/rexglue/sdk/win-amd64/include'),'/I'+str(HEADER.parent),str(source),'/Fe'+str(out/'fixture.exe'),'/Fo'+str(out/'fixture.obj')];env=vc_environment(Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat'));rows=[]
        for command,timeout in [(cmd,120),([str(out/'fixture.exe')],30)]:
            p=subprocess.run(command,env=env,capture_output=True,text=True,timeout=timeout);rows.append(dict(command=command,exit=p.returncode,output=p.stdout+p.stderr));(out/'results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8');self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertIn('INPUT_GUARDS readonly=1 guards=456 mismatch=closed noaccess=closed',p.stdout)
CPP=r'''
#include "start_input_observation.h"
#include <cassert>
#include <set>
#include <vector>
REX_EXTERN(__imp__sub_82868178){}
REX_EXTERN(__imp__sub_827B4938){}
int main(){auto* base=(uint8_t*)VirtualAlloc(nullptr,0x84000000ULL,MEM_RESERVE,PAGE_NOACCESS);assert(base);uint32_t guards[][2]={GUARDS_HERE};std::set<uint32_t> pages;for(auto& g:guards)pages.insert(g[0]&~4095u);for(auto p:pages)assert(VirtualAlloc(base+p,4096,MEM_COMMIT,PAGE_READWRITE));for(auto& g:guards)for(unsigned i=0;i<4;++i)base[g[0]+i]=uint8_t(g[1]>>(24-i*8));std::vector<uint8_t> before;for(auto p:pages)before.insert(before.end(),base+p,base+p+4096);using namespace mc2::host::start_input_observation;assert(OriginalBytes({base,0x100001000ULL}));size_t n=0;for(auto p:pages){assert(!std::memcmp(before.data()+n,base+p,4096));n+=4096;}base[guards[0][0]]^=1;assert(!OriginalBytes({base,0x100001000ULL}));base[guards[0][0]]^=1;DWORD old=0;assert(VirtualProtect(base+*pages.begin(),4096,PAGE_NOACCESS,&old));assert(!OriginalBytes({base,0x100001000ULL}));assert(VirtualFree(base,0,MEM_RELEASE));std::puts("INPUT_GUARDS readonly=1 guards=456 mismatch=closed noaccess=closed");}
'''

