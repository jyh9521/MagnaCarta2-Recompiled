// External, read-only crash capture for the independent input probe.
// Does not insert breakpoints, change registers, or consume native exceptions.
#include <Windows.h>
#include <DbgHelp.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#pragma comment(lib,"dbghelp.lib")
struct Thread { DWORD id; HANDLE handle; };
struct Module { DWORD64 base; DWORD size; std::vector<RUNTIME_FUNCTION> functions; };
static std::vector<Module> modules;
static void AddModule(HANDLE process, void* address) {
 const auto base=reinterpret_cast<DWORD64>(address);IMAGE_DOS_HEADER dos{};IMAGE_NT_HEADERS64 nt{};SIZE_T got=0;
 if(!ReadProcessMemory(process,address,&dos,sizeof(dos),&got)||got!=sizeof(dos)||dos.e_magic!=IMAGE_DOS_SIGNATURE)return;
 if(!ReadProcessMemory(process,reinterpret_cast<void*>(base+dos.e_lfanew),&nt,sizeof(nt),&got)||got!=sizeof(nt)||nt.Signature!=IMAGE_NT_SIGNATURE)return;
 Module m{base,nt.OptionalHeader.SizeOfImage,{}};auto dir=nt.OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXCEPTION];
 if(dir.Size && dir.Size<64*1024*1024 && dir.Size%sizeof(RUNTIME_FUNCTION)==0 && uint64_t(dir.VirtualAddress)+dir.Size<=m.size) {
  m.functions.resize(dir.Size/sizeof(RUNTIME_FUNCTION));
  if(!ReadProcessMemory(process,reinterpret_cast<void*>(base+dir.VirtualAddress),m.functions.data(),dir.Size,&got)||got!=dir.Size)m.functions.clear();
 }
 std::printf("UNWIND_MODULE base=%llX size=%lu functions=%zu\n",m.base,m.size,m.functions.size());modules.push_back(std::move(m));
}
static DWORD64 CALLBACK ModuleBase(HANDLE,DWORD64 pc) {for(auto& m:modules)if(pc>=m.base && pc-m.base<m.size)return m.base;return 0;}
static PVOID CALLBACK FunctionTable(HANDLE,DWORD64 pc) {
 for(auto& m:modules)if(pc>=m.base && pc-m.base<m.size){auto rva=pc-m.base;for(auto& f:m.functions)if(rva>=f.BeginAddress && rva<f.EndAddress)return &f;return nullptr;}return nullptr;
}

static void Stack(HANDLE process, Thread t) {
 CONTEXT c{};c.ContextFlags=CONTEXT_ALL;
 if(!GetThreadContext(t.handle,&c)){std::printf("CONTEXT_FAILED tid=%lu error=%lu\n",t.id,GetLastError());return;}
 std::printf("CONTEXT tid=%lu rip=%llX rcx=%llX rdi=%llX rsp=%llX\n",t.id,c.Rip,c.Rcx,c.Rdi,c.Rsp);
 STACKFRAME64 f{};f.AddrPC.Offset=c.Rip;f.AddrPC.Mode=AddrModeFlat;
 f.AddrStack.Offset=c.Rsp;f.AddrStack.Mode=AddrModeFlat;f.AddrFrame.Offset=c.Rbp;f.AddrFrame.Mode=AddrModeFlat;
 for(unsigned n=0;n<32 && f.AddrPC.Offset;n++) {
  const auto base=ModuleBase(process,f.AddrPC.Offset);
  std::printf("FRAME tid=%lu n=%u pc=%llX base=%llX rva=%llX\n",t.id,n,f.AddrPC.Offset,base,f.AddrPC.Offset-base);
  if(!base)break;
  if(!StackWalk64(IMAGE_FILE_MACHINE_AMD64,process,t.handle,&f,&c,nullptr,FunctionTable,ModuleBase,nullptr))break;
 }
}
int main(int argc,char** argv) {
 if(argc!=4)return 2;
 std::string line='"'+std::string(argv[1])+"\" "+argv[2]+" 10000 8192";
 STARTUPINFOA si{sizeof(si)};PROCESS_INFORMATION pi{};
 if(!CreateProcessA(nullptr,line.data(),nullptr,nullptr,FALSE,DEBUG_ONLY_THIS_PROCESS,nullptr,nullptr,&si,&pi)){std::printf("CREATE_FAILED %lu\n",GetLastError());return 3;}
 CloseHandle(pi.hThread);CloseHandle(pi.hProcess);
 HANDLE process=nullptr;std::vector<Thread> threads;
 const auto start=GetTickCount64();bool timeout=false,exit=false,initial_breakpoint=false;unsigned captures=0;
 while(!exit) {
  if(!timeout && GetTickCount64()-start>60000){timeout=true;std::puts("HOST_TIMEOUT seconds=60 not_AV=1");if(process)TerminateProcess(process,124);}
  DEBUG_EVENT e{};if(!WaitForDebugEvent(&e,100))continue;
  DWORD action=DBG_CONTINUE;
  switch(e.dwDebugEventCode) {
   case CREATE_PROCESS_DEBUG_EVENT: {
    process=OpenProcess(PROCESS_ALL_ACCESS,FALSE,e.dwProcessId);
    if(!process)process=e.u.CreateProcessInfo.hProcess;else CloseHandle(e.u.CreateProcessInfo.hProcess);
    threads.push_back({e.dwThreadId,e.u.CreateProcessInfo.hThread});

    if(e.u.CreateProcessInfo.hFile)CloseHandle(e.u.CreateProcessInfo.hFile);
    std::printf("MODULE main base=%p\n",e.u.CreateProcessInfo.lpBaseOfImage);AddModule(process,e.u.CreateProcessInfo.lpBaseOfImage);break;
   }
   case CREATE_THREAD_DEBUG_EVENT:threads.push_back({e.dwThreadId,e.u.CreateThread.hThread});break;
   case EXIT_THREAD_DEBUG_EVENT:
    for(auto it=threads.begin();it!=threads.end();++it)if(it->id==e.dwThreadId){CloseHandle(it->handle);threads.erase(it);break;}break;
   case LOAD_DLL_DEBUG_EVENT: {
    char path[32768]{};if(e.u.LoadDll.hFile)GetFinalPathNameByHandleA(e.u.LoadDll.hFile,path,sizeof(path),0);
    std::printf("MODULE base=%p path=%s\n",e.u.LoadDll.lpBaseOfDll,path);
    AddModule(process,e.u.LoadDll.lpBaseOfDll);
    if(e.u.LoadDll.hFile)CloseHandle(e.u.LoadDll.hFile);break;
   }
   case EXCEPTION_DEBUG_EVENT: {
    auto& x=e.u.Exception.ExceptionRecord;const auto code=x.ExceptionCode;
    if(code==EXCEPTION_BREAKPOINT && e.u.Exception.dwFirstChance && !initial_breakpoint){initial_breakpoint=true;break;}
    std::printf("EXCEPTION code=%08lX tid=%lu first=%lu ip=%p parameters=%lu arg0=%llX arg1=%llX\n",code,e.dwThreadId,e.u.Exception.dwFirstChance,x.ExceptionAddress,x.NumberParameters,x.NumberParameters?x.ExceptionInformation[0]:0,x.NumberParameters>1?x.ExceptionInformation[1]:0);
    if((code==EXCEPTION_ACCESS_VIOLATION || code==0xC0000374 || code==0xC0000409 || code==EXCEPTION_ILLEGAL_INSTRUCTION) && captures++<32) {
     for(auto t:threads)Stack(process,t);
     if(!e.u.Exception.dwFirstChance || code==0xC0000409) {
      std::string path=std::string(argv[3])+"-"+std::to_string(code)+".dmp";
      HANDLE dump=CreateFileA(path.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
      if(dump!=INVALID_HANDLE_VALUE){const auto ok=MiniDumpWriteDump(process,pi.dwProcessId,dump,MiniDumpNormal,nullptr,nullptr,nullptr);const auto error=ok?0:GetLastError();std::printf("MINIDUMP success=%u error=%lu path=%s\n",unsigned(ok),error,path.c_str());CloseHandle(dump);}
     }
    }
    action=DBG_EXCEPTION_NOT_HANDLED;break;
   }
   case EXIT_PROCESS_DEBUG_EVENT:
    std::printf("PROCESS_EXIT native=%lu timeout=%u\n",e.u.ExitProcess.dwExitCode,unsigned(timeout));exit=true;break;
  }
  std::fflush(stdout);ContinueDebugEvent(e.dwProcessId,e.dwThreadId,action);
 }
 if(process){for(auto t:threads)CloseHandle(t.handle);CloseHandle(process);}return 0;
}
