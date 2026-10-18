// Bounded Windows hardware-watch experiment for the pinned SDK, not game code.
// Reuse the existing PE unwind reader and exception stack recorder unchanged.
#define main mc2_read_only_capture_main
#include "input_probe_capture.cpp"
#undef main
#include <array>

static DWORD64 sdk_base=0, object=0, buffer=0;
static std::array<DWORD64,3> previous{};
static unsigned generation=0;
static bool watches=true;
static bool vector_layout=false;
static bool Read(HANDLE p,DWORD64 a,void* out,SIZE_T size) {
 SIZE_T got=0;return ReadProcessMemory(p,reinterpret_cast<void*>(a),out,size,&got)&&got==size;
}
static DWORD64 Word(HANDLE p,DWORD64 a) {
 DWORD64 v=0;if(!Read(p,a,&v,8))std::printf("READ_FAILED address=%llX error=%lu\n",a,GetLastError());return v;
}
static bool Arm(Thread t,bool clear_status=false) {
 CONTEXT c{};c.ContextFlags=CONTEXT_DEBUG_REGISTERS;
 if(!GetThreadContext(t.handle,&c))return false;
 c.Dr0=c.Dr1=c.Dr2=c.Dr3=c.Dr7=0;
 // Another stopped thread may already have a queued #DB. Preserve its DR6.
 if(clear_status)c.Dr6=0;
 if(watches && sdk_base) {
  if(!object){c.Dr0=sdk_base+0x1147C0;c.Dr7=1;}
  else {
   c.Dr0=object+0x50;c.Dr7=1|(DWORD64(9)<<16); // write, 8-byte vector begin
   if(vector_layout) {
    c.Dr1=object+0x58;c.Dr2=object+0x60;
    c.Dr7|=0x14|(DWORD64(9)<<20)|(DWORD64(9)<<24);
    if(buffer){c.Dr3=buffer+0x30;c.Dr7|=0x40|(DWORD64(9)<<28);}
   } else if(buffer) {
    c.Dr1=buffer+0x30;c.Dr2=buffer+0x40;c.Dr3=buffer+0x48;
    c.Dr7|=0x54|(DWORD64(9)<<20)|(DWORD64(9)<<24)|(DWORD64(9)<<28);
   }
  }
 }
 const bool ok=SetThreadContext(t.handle,&c)!=FALSE;
 std::printf("ARM tid=%lu generation=%u object=%llX buffer=%llX dr0=%llX dr1=%llX dr2=%llX dr3=%llX dr7=%llX ok=%u\n",t.id,generation,object,buffer,c.Dr0,c.Dr1,c.Dr2,c.Dr3,c.Dr7,unsigned(ok));return ok;
}
int main(int argc,char** argv) {
 if(argc!=4 && !(argc==5 && !std::strcmp(argv[4],"vector")))return 2;
 vector_layout=argc==5;
 std::printf("WATCH_CONFIG layout=%s limit=2048 timeout=60 instruction_mutation=0\n",vector_layout?"vector":"string");
 std::string line='"'+std::string(argv[1])+"\" "+argv[2]+" 10000 8192";
 STARTUPINFOA si{sizeof(si)};PROCESS_INFORMATION pi{};
 if(!CreateProcessA(nullptr,line.data(),nullptr,nullptr,FALSE,DEBUG_ONLY_THIS_PROCESS,nullptr,nullptr,&si,&pi))return 3;
 CloseHandle(pi.hThread);CloseHandle(pi.hProcess);
 HANDLE process=nullptr;std::vector<Thread> threads;unsigned hits=0;
 const auto start=GetTickCount64();bool timeout=false,exit=false,initial=false,failed=false;
 while(!exit) {
  if(!timeout&&GetTickCount64()-start>60000){timeout=true;std::puts("HOST_TIMEOUT seconds=60 not_AV=1");if(process)TerminateProcess(process,124);}
  DEBUG_EVENT e{};if(!WaitForDebugEvent(&e,100))continue;
  DWORD action=DBG_CONTINUE;
  if(e.dwDebugEventCode==CREATE_PROCESS_DEBUG_EVENT) {
   process=e.u.CreateProcessInfo.hProcess;threads.push_back({e.dwThreadId,e.u.CreateProcessInfo.hThread});
   if(e.u.CreateProcessInfo.hFile)CloseHandle(e.u.CreateProcessInfo.hFile);
   AddModule(process,e.u.CreateProcessInfo.lpBaseOfImage);
  } else if(e.dwDebugEventCode==CREATE_THREAD_DEBUG_EVENT) {
   threads.push_back({e.dwThreadId,e.u.CreateThread.hThread});if(!Arm(threads.back()))failed=true;
  } else if(e.dwDebugEventCode==EXIT_THREAD_DEBUG_EVENT) {
   for(auto it=threads.begin();it!=threads.end();++it)if(it->id==e.dwThreadId){CloseHandle(it->handle);threads.erase(it);break;}
  } else if(e.dwDebugEventCode==LOAD_DLL_DEBUG_EVENT) {
   char path[32768]{};if(e.u.LoadDll.hFile)GetFinalPathNameByHandleA(e.u.LoadDll.hFile,path,sizeof(path),0);
   std::printf("MODULE base=%p path=%s\n",e.u.LoadDll.lpBaseOfDll,path);AddModule(process,e.u.LoadDll.lpBaseOfDll);
   if(std::string(path).ends_with("\\rexruntime.dll")) {
    sdk_base=reinterpret_cast<DWORD64>(e.u.LoadDll.lpBaseOfDll);
    unsigned char a[4]{},b[4]{};const unsigned char expected_a[]={0x55,0x41,0x57,0x41},expected_b[]={0x4c,0x8b,0x41,0xf8};
    if(!Read(process,sdk_base+0x1147C0,a,4)||!Read(process,sdk_base+0x117F11,b,4)||std::memcmp(a,expected_a,4)||std::memcmp(b,expected_b,4))failed=true;
    for(auto t:threads)if(!Arm(t))failed=true;
   }
   if(e.u.LoadDll.hFile)CloseHandle(e.u.LoadDll.hFile);
  } else if(e.dwDebugEventCode==EXCEPTION_DEBUG_EVENT) {
   auto& x=e.u.Exception.ExceptionRecord;Thread t{};for(auto v:threads)if(v.id==e.dwThreadId)t=v;
   CONTEXT c{};c.ContextFlags=CONTEXT_ALL;if(!t.handle||!GetThreadContext(t.handle,&c))failed=true;
   if(x.ExceptionCode==EXCEPTION_BREAKPOINT&&e.u.Exception.dwFirstChance&&!initial){initial=true;}
   else if(x.ExceptionCode==EXCEPTION_SINGLE_STEP&&e.u.Exception.dwFirstChance&&(c.Dr6&15)&&!watches) {
    std::printf("WATCH_PENDING_AFTER_LIMIT tid=%lu dr6=%llX not_write_evidence=1\n",t.id,c.Dr6);
    if(!Arm(t,true))failed=true;
   }
   else if(x.ExceptionCode==EXCEPTION_SINGLE_STEP&&e.u.Exception.dwFirstChance&&(c.Dr6&15)&&watches) {
    ++hits;
    std::printf("WATCH hit=%u generation=%u tid=%lu dr6=%llX post_rip=%llX rva=%llX object=%llX buffer=%llX rcx=%llX rdx=%llX rdi=%llX rax=%llX\n",hits,generation,t.id,c.Dr6,c.Rip,c.Rip-sdk_base,object,buffer,c.Rcx,c.Rdx,c.Rdi,c.Rax);
    bool rebind=!object;
    if(!object){object=c.Rcx;std::printf("BIND object=%llX vector=%llX begin=%llX end=%llX capacity=%llX\n",object,object+0x50,Word(process,object+0x50),Word(process,object+0x58),Word(process,object+0x60));}
    const auto next=Word(process,object+0x50);
    if(next!=buffer){buffer=next;++generation;previous={};rebind=true;std::printf("BUFFER generation=%u address=%llX\n",generation,buffer);}
    if(buffer) {
     std::array<DWORD64,3> values{Word(process,buffer+0x30),Word(process,buffer+0x40),Word(process,buffer+0x48)};
     std::printf("FIELDS sampled_before=%llX,%llX,%llX sampled_after=%llX,%llX,%llX begin=%llX end=%llX capacity=%llX\n",previous[0],previous[1],previous[2],values[0],values[1],values[2],buffer,Word(process,object+0x58),Word(process,object+0x60));previous=values;
    }
    Stack(process,t); // Only the writing thread unwinds at every data trap.
    if(hits>=2048){watches=false;rebind=true;std::puts("WATCH_LIMIT coverage_ended=1");}
    // All threads are stopped at a debug event; use the same generation on each.
    for(auto v:threads)if((rebind||v.id==t.id)&&!Arm(v,v.id==t.id))failed=true;
    c.ContextFlags=CONTEXT_CONTROL;c.EFlags|=0x10000; // RF resumes execution breakpoint once
    if(!SetThreadContext(t.handle,&c))failed=true;
   } else {
    std::printf("EXCEPTION code=%08lX tid=%lu first=%lu ip=%p rva=%llX arg0=%llX arg1=%llX\n",x.ExceptionCode,e.dwThreadId,e.u.Exception.dwFirstChance,x.ExceptionAddress,reinterpret_cast<DWORD64>(x.ExceptionAddress)-sdk_base,x.NumberParameters?x.ExceptionInformation[0]:0,x.NumberParameters>1?x.ExceptionInformation[1]:0);
    for(auto v:threads)Stack(process,v);
    if(!e.u.Exception.dwFirstChance) {
     const std::string path=std::string(argv[3])+".dmp";HANDLE f=CreateFileA(path.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
     if(f!=INVALID_HANDLE_VALUE){const auto ok=MiniDumpWriteDump(process,pi.dwProcessId,f,MiniDumpNormal,nullptr,nullptr,nullptr);std::printf("MINIDUMP success=%u error=%lu\n",unsigned(ok),ok?0:GetLastError());CloseHandle(f);}
    }
    action=DBG_EXCEPTION_NOT_HANDLED;
   }
  } else if(e.dwDebugEventCode==EXIT_PROCESS_DEBUG_EVENT) {
   std::printf("PROCESS_EXIT native=%lu timeout=%u watch_hits=%u capture_failed=%u\n",e.u.ExitProcess.dwExitCode,unsigned(timeout),hits,unsigned(failed));exit=true;
  }
  if(failed&&!exit){std::puts("WATCH_FAILED terminating=1");TerminateProcess(process,125);}
  std::fflush(stdout);if(!ContinueDebugEvent(e.dwProcessId,e.dwThreadId,action))return 5;
 }
 for(auto t:threads)CloseHandle(t.handle);if(process)CloseHandle(process);return failed?4:0;
}
