"""Read-only guest capture contract and optional pinned Windows real-memory proof."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
HEADER=ROOT/'src/host/panic_observation.h'
COMPILER_SHA256='57e32b1ea2456f12f97bf802453171bbff12d56b2c486b4eca0c75343c0cda2c'

def model_offset(guest,count,span=0x100001000):
    if type(guest)is not int or not 0<guest<1<<32 or type(count)is not int or not 0<count<=8192:raise ValueError('invalid fields')
    if guest+count>1<<32:raise ValueError('guest overflow')
    last=guest+count-1;end=last+(0x1000 if last>=0xe0000000 else 0)+1
    if end>span:raise ValueError('span')
    segments=[];done=0
    while done<count:
        at=guest+done;n=count-done
        if at<0xe0000000<at+n:n=0xe0000000-at
        segments.append((at+(0x1000 if at>=0xe0000000 else 0),n));done+=n
    return segments

def model_utf16(data,units):
    if type(data)is not bytes or type(units)is not int or not 1<=units<=4096:raise ValueError('invalid fields')
    result=bytearray()
    for i in range(units):
        part=data[i*2:i*2+2]
        if len(part)!=2:return {'captured':b'','readable':False,'terminated':False,'truncated':False}
        result+=part
        if part==b'\0\0':return {'captured':bytes(result),'readable':True,'terminated':True,'truncated':False}
    return {'captured':bytes(result),'readable':True,'terminated':False,'truncated':True}

NATIVE_SOURCE=r'''
#include "panic_observation.h"
#include <cstdio>
#include <cstring>
#include <array>
#include <cstdint>
using namespace mc2::host::panic_observation;
static unsigned checks=0,failures=0;
#define CHECK(x) do{checks++;if(!(x)){failures++;std::fprintf(stderr,"CHECK_FAILED line=%u expression=%s\n",unsigned(__LINE__),#x);}}while(0)
static bool Empty(const Result& r){for(auto b:r.bytes)if(b)return false;return r.captured==0&&!r.readable&&!r.terminated&&!r.truncated&&!r.word_known&&r.word==0;}
static uint64_t Hash(const uint8_t* base,const uint64_t* pages,unsigned n){uint64_t h=1469598103934665603ull;for(unsigned p=0;p<n;p++)for(unsigned j=0;j<4096;j++){h^=base[pages[p]+j];h*=1099511628211ull;}return h;}
int main(){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);auto base=(uint8_t*)VirtualAlloc(nullptr,kMaxSpan,MEM_RESERVE,PAGE_NOACCESS);if(!base)return 2;
const uint64_t pages[]={0x2000,0x3000,0x4000,0x5000,0x6000,0x7000,0xA000,0xB000,0xDFFFF000,0xE0001000,0x100000000ull};constexpr unsigned n=sizeof(pages)/sizeof(pages[0]);std::array<std::array<unsigned char,4096>,n> snapshot{};
for(auto p:pages)if(VirtualAlloc(base+p,4096,MEM_COMMIT,PAGE_READWRITE)!=base+p){VirtualFree(base,0,MEM_RELEASE);return 3;}
for(unsigned i=0;i<n;i++)for(unsigned j=0;j<4096;j++)base[pages[i]+j]=(i*17+j*7)%256;
const unsigned char word[]={0x12,0x34,0x56,0x78};std::memcpy(base+0x2100,word,4);
const unsigned char text[]={0,0x41,0,0x0A,0xD8,0,0,0x25,0,0x73,0,0,0,0x58};std::memcpy(base+0x2200,text,sizeof(text));
for(unsigned i=0;i<8192;i++)base[0x4000+i]=i%2?0x41:0;
base[0x6FFE]=base[0x6FFF]=0;const unsigned char last[]={0xDE,0xAD,0xBE,0xEF};std::memcpy(base+0x100000FFCull,last,4);
base[0xDFFFFFFEull]=0xAA;base[0xDFFFFFFFull]=0xBB;base[0xE0001000ull]=0xCC;base[0xE0001001ull]=0xDD;
for(unsigned i=0;i<n;i++)std::memcpy(snapshot[i].data(),base+pages[i],4096);auto before=Hash(base,pages,n);
DWORD old=0;CHECK(VirtualProtect(base+0x2000,4096,PAGE_READONLY,&old));CHECK(VirtualProtect(base+0x7000,4096,PAGE_READWRITE|PAGE_GUARD,&old));CHECK(VirtualProtect(base+0xB000,4096,PAGE_NOACCESS,&old));
MEMORY_BASIC_INFORMATION guard_before{},guard_after{};CHECK(VirtualQuery(base+0x7000,&guard_before,sizeof(guard_before))==sizeof(guard_before));GuestView view{base,kMaxSpan};
{auto r=ReadWord(view,0x2100);CHECK(r.status==Status::ok&&r.readable&&r.word_known&&r.word==0x12345678&&r.captured==4&&r.requested==4);CHECK(std::memcmp(r.bytes.data(),word,4)==0);}
{auto r=ReadBytes(view,0x2100,4);CHECK(r.status==Status::ok&&r.captured==4&&!r.word_known&&std::memcmp(r.bytes.data(),word,4)==0);}
{auto r=ReadUtf16(view,0x2200,64);CHECK(r.status==Status::ok&&r.terminated&&!r.truncated&&r.captured==12&&r.requested==128);CHECK(std::memcmp(r.bytes.data(),text,12)==0);}
{auto r=ReadBytes(view,0x4000,8192);CHECK(r.status==Status::ok&&r.readable&&r.captured==8192&&r.bytes[8191]==0x41);}
{auto r=ReadUtf16(view,0x4000,4096);CHECK(r.status==Status::ok&&r.truncated&&!r.terminated&&r.captured==8192&&r.bytes[8191]==0x41);}
{auto r=ReadUtf16(view,0x6FFE,2);CHECK(r.status==Status::ok&&r.terminated&&r.captured==2);}
{auto r=ReadBytes(view,0x6FFC,8);CHECK(r.status==Status::unreadable&&Empty(r));}
{auto r=ReadWord(view,0x6FFE);CHECK(r.status==Status::unreadable&&Empty(r));}
CHECK(VirtualQuery(base+0x7000,&guard_after,sizeof(guard_after))==sizeof(guard_after));CHECK(guard_before.Protect==guard_after.Protect&&(guard_after.Protect&PAGE_GUARD));
{auto r=ReadBytes(view,0x9000,4);CHECK(r.status==Status::unreadable&&Empty(r));}
{auto r=ReadBytes({nullptr,kMaxSpan},0x2100,4);CHECK(r.status==Status::invalid_view&&Empty(r));}
{auto r=ReadBytes({base,0},0x2100,4);CHECK(r.status==Status::invalid_view&&Empty(r));}
{auto r=ReadBytes({base,kMaxSpan+1},0x2100,4);CHECK(r.status==Status::invalid_view&&Empty(r));}
{auto r=ReadBytes(view,0,4);CHECK(r.status==Status::null_guest&&Empty(r));}
{auto r=ReadBytes(view,0x2100,0);CHECK(r.status==Status::invalid_count&&Empty(r));}
{auto r=ReadBytes(view,0x2100,8193);CHECK(r.status==Status::invalid_count&&Empty(r));}
{auto r=ReadUtf16(view,0x2100,0);CHECK(r.status==Status::invalid_count&&Empty(r));}
{auto r=ReadUtf16(view,0x2100,4097);CHECK(r.status==Status::invalid_count&&Empty(r));}
{auto r=ReadBytes(view,0xFFFFFFFE,4);CHECK(r.status==Status::guest_overflow&&Empty(r));}
{auto r=ReadBytes({base,0x2102},0x2100,4);CHECK(r.status==Status::outside_span&&Empty(r));}
{auto r=ReadBytes({reinterpret_cast<void*>(~uintptr_t(0)-3),kMaxSpan},0x2100,4);CHECK(r.status==Status::host_overflow&&Empty(r));}
{auto r=ReadWord(view,0xFFFFFFFC);CHECK(r.status==Status::ok&&r.word_known&&r.word==0xDEADBEEF&&r.captured==4);}
{auto r=ReadUtf16(view,0xFFFFFFFE,1);CHECK(r.status==Status::ok&&r.truncated&&r.captured==2&&r.bytes[0]==0xBE&&r.bytes[1]==0xEF);}
{auto r=ReadUtf16(view,0xFFFFFFFE,2);CHECK(r.status==Status::guest_overflow&&Empty(r));}
{auto r=ReadBytes(view,0xDFFFFFFE,4);const unsigned char expected[]={0xAA,0xBB,0xCC,0xDD};CHECK(r.status==Status::ok&&r.captured==4&&std::memcmp(r.bytes.data(),expected,4)==0);}
{auto r=ReadWord(view,0xDFFFFFFE);CHECK(r.status==Status::ok&&r.word_known&&r.word==0xAABBCCDD);}
{auto r=ReadUtf16(view,0xDFFFFFFE,2);CHECK(r.status==Status::ok&&r.truncated&&r.captured==4);}
unsigned char partial[8]{};SIZE_T received=0;BOOL copied=ReadProcessMemory(GetCurrentProcess(),base+0xAFFC,partial,8,&received);CHECK(!copied&&received<8);
{auto r=ReadBytes(view,0xAFFC,8);CHECK(r.status==Status::unreadable&&Empty(r));}
{auto r=ReadUtf16(view,0xAFFE,2);CHECK(r.status==Status::unreadable&&Empty(r));}
CHECK(detail::CopyStatus(FALSE,2,4)==Status::partial_read);CHECK(detail::CopyStatus(TRUE,2,4)==Status::partial_read);CHECK(detail::CopyStatus(FALSE,4,4)==Status::read_failed);CHECK(detail::CopyStatus(TRUE,0,4)==Status::read_failed);CHECK(detail::CopyStatus(TRUE,4,4)==Status::ok);
{Result r{};r.bytes.fill(0xAA);r.captured=4;r.readable=r.word_known=true;r.word=7;detail::Fail(r,Status::partial_read);CHECK(r.status==Status::partial_read&&Empty(r));}
CHECK(std::strcmp(StatusName(Status::partial_read),"partial-read")==0);
MEMORY_BASIC_INFORMATION noaccess{};CHECK(VirtualQuery(base+0xB000,&noaccess,sizeof(noaccess))==sizeof(noaccess));CHECK(noaccess.Protect==PAGE_NOACCESS);
CHECK(VirtualProtect(base+0x2000,4096,PAGE_READWRITE,&old));CHECK(VirtualProtect(base+0x7000,4096,PAGE_READWRITE,&old));CHECK(VirtualProtect(base+0xB000,4096,PAGE_READWRITE,&old));
bool exact=true;for(unsigned i=0;i<n;i++)exact=exact&&std::memcmp(snapshot[i].data(),base+pages[i],4096)==0;auto after=Hash(base,pages,n);CHECK(exact&&before==after);CHECK(VirtualFree(base,0,MEM_RELEASE));
std::printf("PANIC_NATIVE checks=%u failures=%u hash_before=%016llX hash_after=%016llX exact_bytes=%u guard_preserved=%u raw_partial_copied=%llu\n",checks,failures,(unsigned long long)before,(unsigned long long)after,exact?1:0,guard_before.Protect==guard_after.Protect?1:0,(unsigned long long)received);return failures?1:0;}
'''

class PanicObservationContractTests(unittest.TestCase):
    def test_public_api_bounded_and_no_target_constants(self):
        s=HEADER.read_text(encoding='utf-8-sig')
        for value in ('kMaxUtf16Units = 4096','kMaxBytes = kMaxUtf16Units * 2','struct GuestView','struct Result','ReadBytes(','ReadWord(','ReadUtf16(','StatusName('):self.assertIn(value,s)
        for address in ('8327C318','82390A6C','824844F4'):self.assertNotIn(address,s.upper())
    def test_only_public_read_apis_no_guest_dereference_or_writes(self):
        s=HEADER.read_text(encoding='utf-8-sig');self.assertIn('ReadProcessMemory(GetCurrentProcess()',s);self.assertIn('VirtualQuery(',s)
        for value in ('WriteProcessMemory','VirtualProtect(','PPCContext','std::printf','std::fprintf','reinterpret_cast<const std::uint32_t*>'):self.assertNotIn(value,s)
        self.assertNotRegex(s,r'\*\s*reinterpret_cast')
    def test_guard_preflight_and_copy_status_contract(self):
        s=HEADER.read_text(encoding='utf-8-sig');self.assertIn('PAGE_GUARD | PAGE_NOACCESS',s);self.assertIn('pass < 2',s);self.assertLess(s.index('status = Preflight'),s.index('ReadProcessMemory(GetCurrentProcess()'));self.assertIn('status = CopyStatus(copied, received, segment)',s);self.assertIn('result.bytes.fill(0)',s)
    def test_utf16_stops_after_exact_zero_unit(self):
        s=HEADER.read_text(encoding='utf-8-sig');self.assertIn('result.bytes[position] == 0 && result.bytes[position + 1] == 0',s);self.assertIn('result.captured += 2',s);self.assertNotIn('WideCharToMultiByte',s)
    def test_independent_span_and_bias_model(self):
        self.assertEqual(model_offset(0xdffffffe,4),[(0xdffffffe,2),(0xe0001000,2)]);self.assertEqual(model_offset(0xfffffffc,4),[(0x100000ffc,4)])
        for guest,count,span in ((0,4,0x100001000),(0xfffffffe,4,0x100001000),(0xfffffffc,4,0x100000000),(0x2000,8193,0x100001000)):
            with self.assertRaises(ValueError):model_offset(guest,count,span)
    def test_independent_raw_utf16_semantics(self):
        raw=bytes.fromhex('0041000ad8000025007300000058');v=model_utf16(raw,7);self.assertEqual(v,{'captured':raw[:12],'readable':True,'terminated':True,'truncated':False})
        self.assertEqual(model_utf16(b'\0A'*4096,4096)['captured'],b'\0A'*4096);self.assertTrue(model_utf16(b'\0A'*4096,4096)['truncated']);self.assertEqual(model_utf16(b'\0A\0',2)['captured'],b'')
        for n in (0,4097,True):
            with self.assertRaises(ValueError):model_utf16(b'',n)
    @unittest.skipUnless(os.name=='nt','Windows public memory APIs required')
    def test_pinned_windows_real_memory(self):
        compiler=Path(os.environ.get('MC2_CAPTURE_COMPILER',ROOT/'local/upstream/llvm/unpacked/bin/clang-cl.exe'))
        vcvars=Path(os.environ.get('MC2_CAPTURE_VCVARS','C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat'))
        if not compiler.is_file() or not vcvars.is_file():self.skipTest('optional pinned Windows compiler/vcvars not present')
        digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        self.assertEqual(digest(compiler),COMPILER_SHA256,'unsupported compiler hash')
        from tools.research.compile_module import vc_environment
        parent=ROOT/'local/analysis/phase18';parent.mkdir(parents=True,exist_ok=True);output=Path(tempfile.mkdtemp(prefix='panic-observation-',dir=parent));source=output/'capture.cpp';source.write_text(NATIVE_SOURCE,encoding='utf-8');exe=output/'capture.exe'
        hashes={str(p):digest(p) for p in (HEADER,compiler,vcvars)};report={'scope':'owned synthetic private pages; no title execution or arbitrary guest-memory scan','success':False,'inputs':hashes}
        command=[str(compiler.resolve()),'/nologo','/Brepro','/std:c++latest','/utf-8','/O2','/MD','/EHa','/DNOMINMAX','/DWIN32_LEAN_AND_MEAN','/I'+str(HEADER.parent.resolve()),str(source),'/Fo'+str(output/'capture.obj'),'/Fe'+str(exe),'/link','/Brepro']
        try:
            report['compile_command']=command;v=subprocess.run(command,cwd=output,env=vc_environment(vcvars.resolve()),capture_output=True,text=True,timeout=120);(output/'compile.txt').write_text(v.stdout+v.stderr,encoding='utf-8');report['compile_exit']=v.returncode
            if v.returncode==0:
                run=subprocess.run([str(exe)],cwd=output,capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW);(output/'run.txt').write_text(run.stdout+run.stderr,encoding='utf-8');report.update(run_command=[str(exe)],run_exit=run.returncode,literal_output=run.stdout,stderr=run.stderr,executable_sha256=digest(exe));m=re.fullmatch(r'PANIC_NATIVE checks=(\d+) failures=0 hash_before=([0-9A-F]{16}) hash_after=\2 exact_bytes=1 guard_preserved=1 raw_partial_copied=(\d+)\n',run.stdout);report['success']=run.returncode==0 and not run.stderr and m is not None and int(m[1])>=40
            report['inputs_unchanged']=all(digest(Path(p))==h for p,h in hashes.items());report['success']=report['success'] and report['inputs_unchanged']
        except Exception as error:
            report['error']=f'{type(error).__name__}: {error}'
            if isinstance(error,subprocess.TimeoutExpired):report['timeout_stdout']=repr(error.stdout);report['timeout_stderr']=repr(error.stderr)
            raise
        finally:(output/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        self.assertTrue(report['success'],f'real capture proof failed; preserved at {output}')

if __name__=='__main__':unittest.main()
