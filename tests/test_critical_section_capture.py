import unittest
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from tools.research.critical_section_capture_report import parse_critical_section_capture


def fixture():
    word='00430032'; prefix='11'*8+word+'22'*52
    return ('CRITICAL_GATE requested=1 matched=1 sdk_pc=1 sdk_bytes=1 caller_bytes=1 host_fault=1 host_rcx=1 lr=823BF2B8\n'
      'CRITICAL_PPC r3=0000000000430036 r11=0000000000430032 r29=0000000040001000 r30=0000000000430036\n'
      'CRITICAL_READ tag=entry_word guest=40001008 requested=4 status=ok captured=4 word_known=1 word=00430032 hex=00430032\n'
      f'CRITICAL_READ tag=entry_prefix guest=40001000 requested=64 status=ok captured=64 word_known=0 word=00000000 hex={prefix}\n'
      'CRITICAL_READ tag=critical_prefix guest=00430036 requested=32 status=unreadable captured=0 word_known=0 word=00000000 hex=\n'
      'CRITICAL_CAPTURE_END context_unchanged=1 host_context_unchanged=1 resumes_guest=0\n')


class CriticalSectionCaptureTests(unittest.TestCase):
    def test_default_disabled(self):
        self.assertEqual(parse_critical_section_capture('')['status'],'disabled')
    def test_requested_but_not_observed(self):
        value=parse_critical_section_capture('TITLE_EXCEPTION code=80000003',requested=True)
        self.assertTrue(value['requested']);self.assertEqual(value['status'],'not_observed');self.assertFalse(value['success'])
    def test_valid_failed_cs_read_has_no_prefix(self):
        value=parse_critical_section_capture(fixture())
        self.assertTrue(value['success']);self.assertEqual(value['status'],'captured')
        self.assertEqual(value['reads']['entry_word']['word'],0x430032)
        self.assertEqual(value['relations']['field_plus4'],0x430036)
        self.assertTrue(value['relations']['r3_matches'])
    def test_partial_failure_leaks_prefix_rejected(self):
        for old,new in [('status=unreadable captured=0','status=unreadable captured=1'),('word_known=0 word=00000000 hex=\n','word_known=0 word=00000000 hex=AA\n')]:
            self.assertFalse(parse_critical_section_capture(fixture().replace(old,new))['success'])
    def test_changed_or_resumed_context_rejected(self):
        for before,after in [('context_unchanged=1','context_unchanged=0'),('host_context_unchanged=1','host_context_unchanged=0'),('resumes_guest=0','resumes_guest=1')]:
            self.assertFalse(parse_critical_section_capture(fixture().replace(before,after))['success'])
    def test_incomplete_duplicate_and_malformed_rows(self):
        for text in [fixture().replace('CRITICAL_CAPTURE_END','BAD_END'),fixture()+fixture().splitlines()[0]+'\n',fixture()+'CRITICAL_READ malformed\n']:
            self.assertFalse(parse_critical_section_capture(text)['success'])
    def test_wrong_lr_or_gate_bit_rejected(self):
        for old,new in [('lr=823BF2B8','lr=823BF2BC'),('sdk_pc=1','sdk_pc=0'),('host_fault=1','host_fault=0'),('host_rcx=1','host_rcx=0')]:
            self.assertFalse(parse_critical_section_capture(fixture().replace(old,new))['success'])
    def test_guest_addresses_and_word_hex_correspond(self):
        for old,new in [('guest=40001008','guest=4000100C'),('word=00430032','word=00430033'),('requested=64','requested=8192')]:
            self.assertFalse(parse_critical_section_capture(fixture().replace(old,new))['success'])
    def test_post_fault_field_difference_not_hidden(self):
        text=fixture().replace('00430032','12345678')
        value=parse_critical_section_capture(text)
        self.assertTrue(value['success']);self.assertFalse(value['relations']['r3_matches'])
    def test_mismatched_snapshot_prefix_is_reported(self):
        value=parse_critical_section_capture(fixture().replace('111111111111111100430032','111111111111111100430033'))
        self.assertTrue(value['success']);self.assertFalse(value['relations']['prefix_word_matches'])
    def test_source_opt_in_readonly_and_continue_search(self):
        source=Path('src/host/title_probe.cpp').read_text(encoding='utf-8-sig')
        self.assertIn('MC2_CAPTURE_CRITICAL_SECTION',source)
        self.assertIn('ObserveCriticalSectionFault(*record,*c,pointers->ContextRecord);',source)
        self.assertIn('return EXCEPTION_CONTINUE_SEARCH; // Record only:',source)
        start=source.index('void ObserveCriticalSectionFault(');end=source.index('LONG CALLBACK RecordException',start)
        observer=source[start:end]
        for forbidden in ['REX_STORE','WriteProcessMemory','EXCEPTION_CONTINUE_EXECUTION','VirtualProtect','->r29 =']:
            self.assertNotIn(forbidden,observer)

    @unittest.skipUnless(os.name=='nt','Windows private-page fixture')
    def test_actual_observer_private_pages(self):
        root=Path(__file__).resolve().parents[1]
        compiler=root/'local/upstream/llvm/unpacked/bin/clang-cl.exe'
        sdk=root/'local/upstream/rexglue/sdk/win-amd64'
        vcvars=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
        if not compiler.is_file() or not vcvars.is_file() or not (sdk/'include/rex/ppc/context.h').is_file():
            self.skipTest('optional pinned local compiler and SDK absent')
        digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        self.assertEqual(digest(compiler),'57e32b1ea2456f12f97bf802453171bbff12d56b2c486b4eca0c75343c0cda2c')
        title=root/'src/host/title_probe.cpp'; header=root/'src/host/panic_observation.h'
        text=title.read_text(encoding='utf-8-sig')
        body=text[text.index('// Opt-in post-fault observation only.'):text.index('LONG CALLBACK RecordException')]
        caller=re.search(r'bool CriticalCallerMatches.*?expected\[\]=\{([^}]+)\}',body,re.S)[1]
        sdk_bytes=re.search(r'bool CriticalSdkBytes.*?expected\[\]=\{([^}]+)\}',body,re.S)[1]
        source=r"""
#include <Windows.h>
#include <rex/ppc/context.h>
#include "panic_observation.h"
#include <atomic>
#include <cstdio>
#include <cstring>
#include <cstdlib>
static uint8_t* guest_base=nullptr;
static uint8_t* fake_module=nullptr;
static bool wait_sdk_verified=true;
static thread_local bool critical_capture_active=false;
static std::atomic<unsigned> critical_capture_count{0};
namespace po=mc2::host::panic_observation;
static HMODULE FixtureGetModuleHandleA(const char*){return reinterpret_cast<HMODULE>(fake_module);}
static FARPROC FixtureGetProcAddress(HMODULE module,const char*){return reinterpret_cast<FARPROC>(reinterpret_cast<uintptr_t>(module)+0x408F80);}
#define GetModuleHandleA FixtureGetModuleHandleA
#define GetProcAddress FixtureGetProcAddress
OBSERVER
int main(int argc,char** argv){
 if(argc!=2)return 2;const char* mode=argv[1];
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
 guest_base=static_cast<uint8_t*>(VirtualAlloc(nullptr,0x100001000ULL,MEM_RESERVE,PAGE_NOACCESS));
 fake_module=static_cast<uint8_t*>(VirtualAlloc(nullptr,0x409000,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));
 if(!guest_base||!fake_module)return 3;
 const uint32_t pages[]={0x823BF000,0x40001000,0x00430000};
 for(auto page:pages)if(!VirtualAlloc(guest_base+page,4096,MEM_COMMIT,PAGE_READWRITE))return 4;
 const uint8_t caller[]={CALLER};const uint8_t sdk_guard[]={SDK_GUARD};
 std::memcpy(guest_base+0x823BF278,caller,sizeof(caller));std::memcpy(fake_module+0x408F80,sdk_guard,sizeof(sdk_guard));
 std::memset(guest_base+0x40001000,0x11,64);const uint8_t field[]={0,0x43,0,0x32};std::memcpy(guest_base+0x40001008,field,4);
 if(std::strcmp(mode,"caller_bytes")==0)guest_base[0x823BF278]^=1;
 if(std::strcmp(mode,"sdk_bytes")==0)fake_module[0x408F80]^=1;
 uint8_t object_before[64],caller_before[128],sdk_before[24];
 std::memcpy(object_before,guest_base+0x40001000,64);std::memcpy(caller_before,guest_base+0x823BF278,128);std::memcpy(sdk_before,fake_module+0x408F80,24);
 DWORD old=0;if(!VirtualProtect(guest_base+0x823BF000,4096,PAGE_READONLY,&old)||!VirtualProtect(guest_base+0x40001000,4096,PAGE_READONLY,&old)||!VirtualProtect(guest_base+0x00430000,4096,PAGE_READWRITE|PAGE_GUARD,&old))return 5;
 PPCContext c{};c.lr=0x823BF2B8;c.r3.u32=0x00430036;c.r11.u32=0x00430032;c.r29.u32=0x40001000;c.r30.u32=0x00430036;
 if(std::strcmp(mode,"mmio")==0)c.r29.u32=0x7FC80000;
 if(std::strcmp(mode,"overflow")==0)c.r29.u32=0xFFFFFFFC;
 if(std::strcmp(mode,"lr")==0)c.lr+=4;
 EXCEPTION_RECORD record{};record.ExceptionCode=EXCEPTION_ACCESS_VIOLATION;record.NumberParameters=2;record.ExceptionAddress=fake_module+0x408F95;record.ExceptionInformation[0]=0;record.ExceptionInformation[1]=reinterpret_cast<uintptr_t>(guest_base)+c.r3.u32+0x18;
 if(std::strcmp(mode,"write")==0)record.ExceptionInformation[0]=1;
 if(std::strcmp(mode,"parameters")==0)record.NumberParameters=1;
 if(std::strcmp(mode,"breakpoint")==0)record.ExceptionCode=EXCEPTION_BREAKPOINT;
 CONTEXT host{};host.ContextFlags=CONTEXT_FULL;host.Rcx=reinterpret_cast<uintptr_t>(guest_base)+c.r3.u32;
 if(std::strcmp(mode,"sdk_pc")==0)record.ExceptionAddress=fake_module+0x408F96;
 if(std::strcmp(mode,"host_fault")==0)record.ExceptionInformation[1]++;
 if(std::strcmp(mode,"host_rcx")==0)host.Rcx++;
 if(std::strcmp(mode,"sdk_identity")==0)wait_sdk_verified=false;
 _putenv_s("MC2_CAPTURE_CRITICAL_SECTION",std::strcmp(mode,"default_off")==0?"":"1");
 PPCContext before;CONTEXT host_before;std::memcpy(&before,&c,sizeof(c));std::memcpy(&host_before,&host,sizeof(host));
 ObserveCriticalSectionFault(record,c,&host);
 MEMORY_BASIC_INFORMATION guard{};VirtualQuery(guest_base+0x00430000,&guard,sizeof(guard));
 const bool okay=std::memcmp(&before,&c,sizeof(c))==0&&std::memcmp(&host_before,&host,sizeof(host))==0&&std::memcmp(object_before,guest_base+0x40001000,64)==0&&std::memcmp(caller_before,guest_base+0x823BF278,128)==0&&std::memcmp(sdk_before,fake_module+0x408F80,24)==0&&(guard.Protect&PAGE_GUARD);
 std::printf("CRITICAL_FIXTURE_END mode=%s unchanged=%u guard_preserved=%u attempts=%u\n",mode,unsigned(okay),unsigned((guard.Protect&PAGE_GUARD)!=0),unsigned(critical_capture_count.load()));
 VirtualFree(guest_base,0,MEM_RELEASE);VirtualFree(fake_module,0,MEM_RELEASE);return okay?0:6;
}
""".replace('OBSERVER',body).replace('CALLER',caller).replace('SDK_GUARD',sdk_bytes)
        parent=root/'local/analysis/phase20';parent.mkdir(parents=True,exist_ok=True)
        output=Path(tempfile.mkdtemp(prefix='critical-observer-fixture-',dir=parent))
        cpp=output/'observer.cpp';cpp.write_text(source,encoding='utf-8');exe=output/'observer.exe'
        inputs={str(p):digest(p) for p in (title,header,compiler,vcvars)}
        report={'scope':'owned synthetic private pages, actual observer functions; mocked SDK export resolver, no title or SDK critical-section execution','inputs':inputs,'success':False,'runs':[]}
        from tools.research.compile_module import vc_environment
        command=[str(compiler),'/nologo','/Brepro','/std:c++latest','/utf-8','/O2','/MD','/EHa','/arch:AVX2','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/I'+str(header.parent),'/I'+str(sdk/'include'),str(cpp),'/Fo'+str(output/'observer.obj'),'/Fe'+str(exe),'/link','/Brepro']
        try:
            process=subprocess.run(command,cwd=output,env=vc_environment(vcvars),capture_output=True,text=True,timeout=120)
            (output/'compile.txt').write_text(process.stdout+process.stderr,encoding='utf-8');report.update(compile_command=command,compile_exit=process.returncode)
            self.assertEqual(process.returncode,0,str(output))
            for mode in ('matched','sdk_pc','sdk_bytes','caller_bytes','host_fault','host_rcx','lr','sdk_identity','mmio','overflow','default_off','write','parameters','breakpoint'):
                run=subprocess.run([str(exe),mode],cwd=output,capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
                (output/(mode+'.txt')).write_text(run.stdout+run.stderr,encoding='utf-8')
                protocol='\n'.join(line for line in run.stdout.splitlines() if not line.startswith('CRITICAL_FIXTURE_END'))
                parsed=parse_critical_section_capture(protocol,requested=mode!='default_off')
                report['runs'].append({'mode':mode,'exit':run.returncode,'stdout':run.stdout,'stderr':run.stderr,'parsed':parsed})
                self.assertEqual(run.returncode,0,str(output));self.assertFalse(run.stderr)
                self.assertIn(f'CRITICAL_FIXTURE_END mode={mode} unchanged=1 guard_preserved=1',run.stdout)
                if mode in ('matched','mmio','overflow'):
                    self.assertTrue(parsed['success'],str(parsed))
                    self.assertEqual(parsed['reads']['critical_prefix']['captured'],0)
                    if mode!='matched':
                        self.assertEqual(parsed['reads']['entry_prefix']['captured'],0)
                        self.assertEqual(parsed['reads']['entry_prefix']['status'],'outside-span')
                elif mode=='default_off':self.assertEqual(parsed['status'],'disabled')
                elif mode in ('lr','write','parameters','breakpoint'):self.assertEqual(parsed['status'],'not_observed')
                else:self.assertEqual(parsed['status'],'gate_rejected')
                self.assertIn('attempts='+('0' if mode in ('default_off','lr','write','parameters','breakpoint') else '1'),run.stdout)
            report['inputs_unchanged']=all(digest(Path(path))==value for path,value in inputs.items())
            report['executable_sha256']=digest(exe);report['success']=report['inputs_unchanged']
            self.assertTrue(report['success'])
        finally:
            (output/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':unittest.main()
