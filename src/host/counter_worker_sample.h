#pragma once
// Boundary-only native consumer sample. Native suspension is paired, never a
// guest register repair. Formatting/symbol lookup occurs only after resume.
#include "counter_observation.h"
namespace mc2::host {
inline bool SampleCounterWorkers(uint8_t* base) {
 unsigned index=0;bool paired=true;
 for(const auto& w:counter_observation::workers){
  if(w.ready.load(std::memory_order_acquire)!=2)continue;
  if(w.thread==GetCurrentThreadId()){std::printf("COUNTER_WORKER sample=%u thread=%u status=self-not-suspended\n",index++,w.thread);continue;}
  HANDLE thread=OpenThread(THREAD_SUSPEND_RESUME|THREAD_GET_CONTEXT|THREAD_QUERY_INFORMATION,FALSE,w.thread);
  if(!thread){std::printf("COUNTER_WORKER sample=%u thread=%u status=open-failed\n",index++,w.thread);continue;}
  FILETIME created{},ended{},kernel{},user{};
  const bool same=GetThreadTimes(thread,&created,&ended,&kernel,&user) &&
   ((uint64_t(created.dwHighDateTime)<<32)|created.dwLowDateTime)==w.creation;
  if(!same){CloseHandle(thread);std::printf("COUNTER_WORKER sample=%u thread=%u status=identity-mismatch\n",index++,w.thread);continue;}
  const DWORD prior=SuspendThread(thread);
  if(prior==DWORD(-1)){CloseHandle(thread);std::printf("COUNTER_WORKER sample=%u thread=%u status=suspend-failed\n",index++,w.thread);continue;}
  CONTEXT native{};native.ContextFlags=CONTEXT_FULL;PPCContext guest{};SIZE_T count=0;
  std::array<uint8_t,512> stack{};SIZE_T stack_count=0;
  const bool cpu=GetThreadContext(thread,&native)!=FALSE;
  const bool context=w.context<=UINTPTR_MAX-sizeof(guest) && panic_observation::detail::Preflight(uintptr_t(w.context),sizeof(guest))==panic_observation::Status::ok &&
   ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(uintptr_t(w.context)),&guest,sizeof(guest),&count) && count==sizeof(guest);
  const bool native_stack=cpu && native.Rsp<=UINTPTR_MAX-stack.size() && panic_observation::detail::Preflight(uintptr_t(native.Rsp),stack.size())==panic_observation::Status::ok &&
   ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(uintptr_t(native.Rsp)),stack.data(),stack.size(),&stack_count) && stack_count==stack.size();
  panic_observation::Result guest_stack{};
  if(context && schedule_observation::DataRange(guest.r1.u32,256))guest_stack=panic_observation::ReadBytes({base,0x100001000ULL},guest.r1.u32,256);
  const DWORD resumed=ResumeThread(thread);paired=paired && resumed==prior+1;CloseHandle(thread);
  std::printf("COUNTER_WORKER sample=%u thread=%u status=%s identity_match=1 prior_suspend=%lu resume_result=%lu context=%llX pc=%llX r1=%08X r3=%08X r4=%08X r11=%08X r29=%08X r30=%08X r31=%08X lr=%08X ctr=%08X tick_ms=%llu\n",index,w.thread,
   cpu&&context&&resumed!=DWORD(-1)?"observed":"unavailable",prior,resumed,(unsigned long long)w.context,(unsigned long long)native.Rip,guest.r1.u32,guest.r3.u32,guest.r4.u32,guest.r11.u32,guest.r29.u32,guest.r30.u32,guest.r31.u32,unsigned(guest.lr),guest.ctr.u32,(unsigned long long)GetTickCount64());
  if(cpu){HMODULE module=nullptr;char path[MAX_PATH]{};
   GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,reinterpret_cast<LPCSTR>(uintptr_t(native.Rip)),&module);
   if(module)GetModuleFileNameA(module,path,MAX_PATH);
   std::printf("COUNTER_WORKER_PC sample=%u rva=%llX module=%s\n",index,(unsigned long long)(native.Rip-reinterpret_cast<uintptr_t>(module)),path);}
  std::printf("COUNTER_WORKER_NATIVE_STACK sample=%u sp=%llX captured=%zu hex=",index,(unsigned long long)native.Rsp,native_stack?stack.size():size_t(0));
  if(native_stack)for(auto b:stack)std::printf("%02X",unsigned(b));std::printf("\n");
  std::printf("COUNTER_WORKER_GUEST_STACK sample=%u sp=%08X captured=%zu hex=",index,guest.r1.u32,guest_stack.captured);
  if(guest_stack.status==panic_observation::Status::ok)for(size_t i=0;i<guest_stack.captured;++i)std::printf("%02X",unsigned(guest_stack.bytes[i]));std::printf("\n");++index;
 }
 std::printf("COUNTER_WORKER_SCOPE captured=%u unavailable=%llu native_suspension_paired=%u scheduling_perturbed=1 guest_register_writes=0\n",index,(unsigned long long)counter_observation::workers_unavailable.load(),unsigned(paired));
 return paired;
}
} // namespace mc2::host
