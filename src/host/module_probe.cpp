// SDK initialization probe; no guest entrypoint, GPU or title launch.
#include "mc2_probe_init.h"
#include <rex/runtime.h>
#include <rex/system/function_dispatcher.h>
#include <rex/system/xmemory.h>
#include <cstdio>
#include <cstring>
#include <exception>
#include <Windows.h>
extern void mc2_probe_RegisterFunctions(rex::runtime::IModuleRegistrar*);
#ifdef MC2_NATIVE_PROBE
int RunNativeAddProbe(rex::Runtime&);
#endif
int main() {
  try {
    char loaded_dll[MAX_PATH]{};
    auto module=GetModuleHandleA("rexruntime.dll");
    if(!module || !GetModuleFileNameA(module,loaded_dll,MAX_PATH))return 8;
    std::printf("RUNTIME_DLL %s\n",loaded_dll);
    rex::Runtime runtime(".", "./user", {}, "./cache");
    rex::RuntimeConfig config; config.tool_mode=true;
    auto status=runtime.Setup(PPCImageConfig,std::move(config));
    std::printf("SETUP status=%08X\n",unsigned(status)); std::fflush(stdout);
    if(status != 0) return 2;
    auto* dispatcher=runtime.function_dispatcher();
    if(!dispatcher || !runtime.virtual_membase() || !runtime.memory() || !runtime.kernel_state()) return 3;
    mc2_probe_RegisterFunctions(dispatcher);
    size_t total=0;
    for(auto* m=PPCFuncMappings;m->host;++m){
      if(dispatcher->GetFunction(uint32_t(m->guest))!=m->host)return 4;
      ++total;
    }
    std::printf("REGISTRATION count=%zu base=mapped\n",total);
    auto address=runtime.memory()->SystemHeapAlloc(0x1000);
    if(!address)return 5;
    const unsigned char expected[4]={0x12,0x34,0x56,0x78};
    std::memcpy(runtime.virtual_membase()+address,expected,4);
    if(std::memcmp(runtime.virtual_membase()+address,expected,4))return 6;
    runtime.memory()->SystemHeapFree(address);
    std::puts("MEMORY roundtrip=12345678"); std::fflush(stdout);
#ifdef MC2_NATIVE_PROBE
    auto native_result=RunNativeAddProbe(runtime);
    std::printf("NATIVE_PROBE status=%d\n",native_result);
    if(native_result)return native_result;
#endif
    runtime.Shutdown(); std::puts("SHUTDOWN complete");
  } catch(const std::exception& error) {
    std::fprintf(stderr,"HOST_EXCEPTION %s\n",error.what()); return 7;
  }
}
